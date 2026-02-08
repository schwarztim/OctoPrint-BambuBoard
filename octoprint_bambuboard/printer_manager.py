"""Multi-printer lifecycle management.

Manages a dict of {printer_id: ManagedPrinter} instances,
handling connect/disconnect/reconnect with thread-safe access.
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from ._vendor.bpm.bambuconfig import BambuConfig
from ._vendor.bpm.bambuprinter import BambuPrinter
from ._vendor.bpm.bambutools import ServiceState

from .state_bridge import serialize_state

_logger = logging.getLogger("octoprint.plugins.bambuboard.printer_manager")


class ConnectionState(Enum):
    PENDING = "pending"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


@dataclass
class ManagedPrinter:
    printer_id: str
    name: str
    config: BambuConfig
    instance: BambuPrinter
    connection_state: ConnectionState = ConnectionState.PENDING
    printer_model: str = "UNKNOWN"
    last_state: dict = field(default_factory=dict)
    error_message: str = ""
    _stop_event: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def connected(self):
        return self.connection_state == ConnectionState.CONNECTED


class PrinterManager:
    """Manages multiple BambuPrinter instances with independent MQTT connections."""

    def __init__(self, plugin):
        self._plugin = plugin
        self._printers = {}  # type: Dict[str, ManagedPrinter]
        self._lock = threading.Lock()

    def connect_all(self, printer_configs):
        # type: (list) -> None
        """Connect all printers marked auto_connect=True."""
        for cfg in printer_configs:
            if cfg.get("auto_connect", True):
                try:
                    self.connect_printer(cfg)
                except Exception:
                    _logger.exception(
                        "Failed to connect printer %s",
                        cfg.get("name", cfg.get("id", "unknown")),
                    )

    def connect_printer(self, printer_cfg):
        # type: (dict) -> str
        """Create a BambuPrinter from config dict and start its MQTT session.

        Launches a background thread that retries until connected (matching
        the standalone BPM behaviour).
        """
        printer_id = printer_cfg.get("id", str(uuid.uuid4()))

        bambu_config = BambuConfig(
            hostname=printer_cfg["hostname"],
            access_code=printer_cfg["access_code"],
            serial_number=printer_cfg["serial_number"],
            mqtt_port=printer_cfg.get("mqtt_port", 8883),
            external_chamber=printer_cfg.get("external_chamber", False),
        )

        # Derive model from serial number prefix — no MQTT needed
        try:
            printer_model = bambu_config.printer_model.name
        except Exception:
            printer_model = "UNKNOWN"

        bambu_printer = BambuPrinter(config=bambu_config)
        bambu_printer.on_update = self._create_on_update_callback(printer_id)

        managed = ManagedPrinter(
            printer_id=printer_id,
            name=printer_cfg.get("name", "Printer"),
            config=bambu_config,
            instance=bambu_printer,
            printer_model=printer_model,
        )

        with self._lock:
            if printer_id in self._printers:
                existing = self._printers[printer_id]
                if existing.connected:
                    _logger.info("Printer %s already connected, skipping", printer_id)
                    return printer_id
                self._disconnect_no_lock(printer_id)
            self._printers[printer_id] = managed
            managed.connection_state = ConnectionState.CONNECTING
            managed.error_message = ""

        _logger.info("Starting MQTT session for printer %s (%s) [model=%s]",
                      managed.name, printer_id, printer_model)

        # Send immediate UI update so frontend shows "Connecting..."
        self._plugin._send_printer_update(printer_id, managed.last_state)

        # Launch persistent retry loop on a daemon thread (matches BPM behaviour)
        t = threading.Thread(
            target=self._connect_loop,
            args=(printer_id,),
            name="bambuboard-connect-{}".format(printer_id[:8]),
            daemon=True,
        )
        t.start()

        return printer_id

    def _connect_loop(self, printer_id):
        # type: (str) -> None
        """Retry start_session() until connected or stopped.

        Mirrors BPM's setup_application() loop:
            while service_state != CONNECTED:
                if internalException: start_session()
                sleep(1)
        """
        while True:
            with self._lock:
                managed = self._printers.get(printer_id)
                if managed is None:
                    return
                stop_event = managed._stop_event

            if stop_event.is_set():
                return

            bp = managed.instance

            # Only call start_session if not already connected
            if bp.service_state != ServiceState.CONNECTED:
                try:
                    bp.start_session()
                except Exception as exc:
                    _logger.debug("start_session raised for %s: %s", managed.name, exc)

            # Check if connected after start_session
            if bp.service_state == ServiceState.CONNECTED:
                with self._lock:
                    managed.connection_state = ConnectionState.CONNECTED
                    managed.error_message = ""
                self._plugin._send_printer_update(printer_id, managed.last_state)
                self._plugin._send_connection_event(
                    printer_id, "connected",
                    "Connected to {}".format(managed.name))
                _logger.info("Printer %s connected", managed.name)
                return

            # Not connected yet — update error info and retry
            err = getattr(bp, '_internalException', None)
            if err:
                err_msg = str(err)
                with self._lock:
                    if self._printers.get(printer_id) is not None:
                        managed.error_message = err_msg
                _logger.debug("Retrying connection for %s — reason: %s", managed.name, err_msg)

            # Sleep 1 second (matching BPM), but check stop_event
            if stop_event.wait(timeout=1.0):
                return

    def disconnect_printer(self, printer_id):
        # type: (str) -> None
        """Stop MQTT session and remove printer from management."""
        with self._lock:
            self._disconnect_no_lock(printer_id)

    def _disconnect_no_lock(self, printer_id):
        # type: (str) -> None
        """Internal disconnect — must be called while holding self._lock."""
        managed = self._printers.pop(printer_id, None)
        if managed is None:
            return

        # Signal the connect loop to stop
        managed._stop_event.set()

        if managed.instance:
            try:
                managed.instance.quit()
            except Exception:
                _logger.exception("Error during quit for printer %s", managed.name)

        managed.connection_state = ConnectionState.DISCONNECTED
        _logger.info("Disconnected printer %s (%s)", managed.name, printer_id)

    def reconnect_printer(self, printer_id, printer_cfg):
        # type: (str, dict) -> None
        """Disconnect then reconnect a printer with (possibly updated) config."""
        with self._lock:
            self._disconnect_no_lock(printer_id)
        self.connect_printer(printer_cfg)

    def shutdown_all(self):
        # type: () -> None
        """Gracefully quit all printer sessions."""
        with self._lock:
            ids = list(self._printers.keys())

        for pid in ids:
            try:
                self.disconnect_printer(pid)
            except Exception:
                _logger.exception("Error shutting down printer %s", pid)

    def get_printer(self, printer_id):
        # type: (str) -> Optional[ManagedPrinter]
        """Get a ManagedPrinter by ID, or None."""
        with self._lock:
            return self._printers.get(printer_id)

    def get_all_states(self):
        # type: () -> dict
        """Return {printer_id: {name, connected, connection_state, printer_model, state}} for all printers."""
        with self._lock:
            result = {}
            for pid, managed in self._printers.items():
                result[pid] = {
                    "name": managed.name,
                    "connected": managed.connected,
                    "connection_state": managed.connection_state.value,
                    "printer_model": managed.printer_model,
                    "error_message": managed.error_message,
                    "state": managed.last_state,
                }
            return result

    def _create_on_update_callback(self, printer_id):
        # type: (str) -> callable
        """Create a throttled callback for a specific printer."""
        last_sent = [0.0]
        throttle_sec = (self._plugin._settings.get_int(["update_throttle_ms"]) or 1000) / 1000.0

        def callback(bambu_printer):
            now = time.monotonic()
            if now - last_sent[0] < throttle_sec:
                return
            last_sent[0] = now

            try:
                state_dict = serialize_state(bambu_printer)
            except Exception:
                _logger.exception("Error serializing state for %s", printer_id)
                return

            with self._lock:
                managed = self._printers.get(printer_id)
                if managed is None:
                    return

                prev_state = managed.connection_state
                managed.last_state = state_dict

                if bambu_printer.service_state == ServiceState.CONNECTED:
                    managed.connection_state = ConnectionState.CONNECTED
                    managed.error_message = ""
                    if prev_state != ConnectionState.CONNECTED:
                        self._plugin._send_connection_event(
                            printer_id, "connected",
                            "Connected to {}".format(managed.name))
                elif bambu_printer.service_state == ServiceState.QUIT:
                    if prev_state == ConnectionState.CONNECTED:
                        # Lost connection — schedule reconnect
                        managed.connection_state = ConnectionState.RECONNECTING
                        managed.error_message = "Connection lost"
                        self._plugin._send_connection_event(
                            printer_id, "reconnecting",
                            "Lost connection to {}, reconnecting...".format(managed.name))
                        cfg = self._config_dict_from_managed(managed)
                        # Reconnect in a background thread (don't block callback)
                        t = threading.Thread(
                            target=self._do_reconnect,
                            args=(printer_id, cfg),
                            name="bambuboard-reconnect-{}".format(printer_id[:8]),
                            daemon=True,
                        )
                        t.start()

            self._plugin._send_printer_update(printer_id, state_dict)

        return callback

    def _do_reconnect(self, printer_id, printer_cfg):
        # type: (str, dict) -> None
        """Execute a reconnection attempt after a brief delay."""
        time.sleep(5)  # Brief delay before reconnect
        _logger.info("Attempting reconnect for printer %s", printer_id)
        try:
            self.reconnect_printer(printer_id, printer_cfg)
        except Exception:
            _logger.exception("Reconnect failed for printer %s", printer_id)

    @staticmethod
    def _config_dict_from_managed(managed):
        # type: (ManagedPrinter) -> dict
        """Extract a config dict from a ManagedPrinter for reconnection."""
        cfg = managed.config
        return {
            "id": managed.printer_id,
            "name": managed.name,
            "hostname": cfg.hostname,
            "access_code": cfg.access_code,
            "serial_number": cfg.serial_number,
            "mqtt_port": cfg.mqtt_port,
            "external_chamber": cfg.external_chamber,
            "auto_connect": True,
        }

    def test_connection(self, hostname, access_code, serial_number, mqtt_port=8883):
        # type: (str, str, str, int) -> dict
        """Test MQTT connectivity to a printer without keeping the connection.

        Returns {"success": bool, "message": str, "printer_model": str}.
        """
        test_config = BambuConfig(
            hostname=hostname,
            access_code=access_code,
            serial_number=serial_number,
            mqtt_port=mqtt_port,
        )
        test_printer = BambuPrinter(config=test_config)

        connected_event = threading.Event()
        result = {"success": False, "message": "", "printer_model": ""}

        def on_update(bp):
            if bp.service_state == ServiceState.CONNECTED:
                result["success"] = True
                result["message"] = "Connected successfully"
                result["printer_model"] = bp.config.printer_model.name
                connected_event.set()

        test_printer.on_update = on_update

        try:
            test_printer.start_session()
            if not connected_event.wait(timeout=15):
                result["message"] = "Connection timed out after 15 seconds"
        except Exception as e:
            result["message"] = "Connection failed: {}".format(e)
        finally:
            try:
                test_printer.quit()
            except Exception:
                pass

        return result
