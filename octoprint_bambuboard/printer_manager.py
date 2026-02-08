"""Multi-printer lifecycle management.

Manages a dict of {printer_id: ManagedPrinter} instances,
handling connect/disconnect/reconnect with thread-safe access.
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from bpm.bambuconfig import BambuConfig
from bpm.bambuprinter import BambuPrinter
from bpm.bambutools import ServiceState

from .state_bridge import serialize_state

_logger = logging.getLogger("octoprint.plugins.bambuboard.printer_manager")

MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY_SECONDS = 10


@dataclass
class ManagedPrinter:
    printer_id: str
    name: str
    config: BambuConfig
    instance: BambuPrinter
    connected: bool = False
    last_state: dict = field(default_factory=dict)
    error_message: str = ""
    reconnect_attempts: int = 0
    _reconnect_timer: Optional[threading.Timer] = field(default=None, repr=False)


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

        Returns the printer_id. The entire check-create-insert sequence is
        performed under a single lock acquisition to prevent races.
        """
        printer_id = printer_cfg.get("id", str(uuid.uuid4()))

        # Build the BambuPrinter outside the lock (no shared state yet)
        bambu_config = BambuConfig(
            hostname=printer_cfg["hostname"],
            access_code=printer_cfg["access_code"],
            serial_number=printer_cfg["serial_number"],
            mqtt_port=printer_cfg.get("mqtt_port", 8883),
            external_chamber=printer_cfg.get("external_chamber", False),
        )
        bambu_printer = BambuPrinter(config=bambu_config)
        bambu_printer.on_update = self._create_on_update_callback(printer_id)

        managed = ManagedPrinter(
            printer_id=printer_id,
            name=printer_cfg.get("name", "Printer"),
            config=bambu_config,
            instance=bambu_printer,
        )

        with self._lock:
            # Atomically check for existing, disconnect if needed, insert new
            if printer_id in self._printers:
                existing = self._printers[printer_id]
                if existing.connected:
                    _logger.info("Printer %s already connected, skipping", printer_id)
                    # Clean up the unused instance we just created
                    return printer_id
                self._disconnect_no_lock(printer_id)
            self._printers[printer_id] = managed

        _logger.info("Starting MQTT session for printer %s (%s)", managed.name, printer_id)
        try:
            bambu_printer.start_session()
            with self._lock:
                managed.connected = True
                managed.reconnect_attempts = 0
                managed.error_message = ""
        except Exception as e:
            with self._lock:
                managed.error_message = str(e)
            _logger.exception("Failed to start session for %s", managed.name)

        return printer_id

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

        if managed._reconnect_timer:
            managed._reconnect_timer.cancel()

        if managed.instance:
            try:
                managed.instance.quit()
            except Exception:
                _logger.exception("Error during quit for printer %s", managed.name)

        managed.connected = False
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
        """Return {printer_id: {name, connected, state}} for all printers."""
        with self._lock:
            result = {}
            for pid, managed in self._printers.items():
                result[pid] = {
                    "name": managed.name,
                    "connected": managed.connected,
                    "error_message": managed.error_message,
                    "state": managed.last_state,
                }
            return result

    def _create_on_update_callback(self, printer_id):
        # type: (str) -> callable
        """Create a throttled callback for a specific printer.

        Fires from BambuPrinter's internal MQTT thread. Kept lightweight:
        serialize state, cache it, dispatch a plugin message.
        """
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

                was_connected = managed.connected
                managed.last_state = state_dict
                managed.connected = bambu_printer.service_state == ServiceState.CONNECTED

                # Detect unexpected disconnection
                if was_connected and bambu_printer.service_state == ServiceState.QUIT:
                    managed.connected = False
                    if managed.reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
                        self._schedule_reconnect(printer_id, managed)

            self._plugin._send_printer_update(printer_id, state_dict)

        return callback

    def _schedule_reconnect(self, printer_id, managed):
        # type: (str, ManagedPrinter) -> None
        """Schedule a reconnection attempt after a delay."""
        managed.reconnect_attempts += 1
        delay = RECONNECT_DELAY_SECONDS * managed.reconnect_attempts
        _logger.warning(
            "Printer %s disconnected unexpectedly, scheduling reconnect "
            "attempt %d/%d in %ds",
            managed.name, managed.reconnect_attempts, MAX_RECONNECT_ATTEMPTS, delay,
        )

        cfg = self._config_dict_from_managed(managed)

        timer = threading.Timer(delay, self._do_reconnect, args=(printer_id, cfg))
        timer.daemon = True
        managed._reconnect_timer = timer
        timer.start()

    def _do_reconnect(self, printer_id, printer_cfg):
        # type: (str, dict) -> None
        """Execute a reconnection attempt."""
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
