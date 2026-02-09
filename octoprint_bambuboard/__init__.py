"""OctoPrint-BambuBoard — Multi-printer Bambu Lab dashboard for OctoPrint."""

import atexit
import logging
import os
import posixpath
import shutil
import tempfile

import flask
import octoprint.plugin
from octoprint.util import RepeatedTimer

from .camera_proxy import CameraProxy
from .file_manager import FileManager
from .printer_manager import PrinterManager

_logger = logging.getLogger("octoprint.plugins.bambuboard")


class BambuBoardPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.BlueprintPlugin,
    octoprint.plugin.EventHandlerPlugin,
):
    NATIVE_PRINTER_ID = "__native__"
    # ── Lifecycle ──────────────────────────────────────────────────────

    def on_after_startup(self):
        _logger.info("BambuBoard starting up")
        self._printer_manager = PrinterManager(self)
        self._file_manager = FileManager(self._printer_manager)
        self._camera_proxy = CameraProxy(self)
        self._native_poll_timer = None

        printers = self._settings.get(["printers"]) or []
        if printers:
            _logger.info("Auto-connecting %d configured printer(s)", len(printers))
            self._printer_manager.connect_all(printers)

    def on_shutdown(self):
        _logger.info("BambuBoard shutting down")
        self._stop_native_poll()
        if hasattr(self, "_camera_proxy"):
            self._camera_proxy.stop_all()
        if hasattr(self, "_printer_manager"):
            self._printer_manager.shutdown_all()

    # ── Settings ───────────────────────────────────────────────────────

    def get_settings_defaults(self):
        return {
            "printers": [],
            "update_throttle_ms": 1000,
            "sidebar_show_all": True,
            "sidebar_display_mode": "all",
            "default_printer_id": "",
            "dark_mode": False,
            "show_native_printer": True,
            "native_printer_name": "",
        }

    def on_settings_save(self, data):
        old_printers = {p["id"]: p for p in (self._settings.get(["printers"]) or [])}

        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

        new_printers = {p["id"]: p for p in (self._settings.get(["printers"]) or [])}

        if not hasattr(self, "_printer_manager"):
            return

        # Detect removed printers
        for pid in old_printers:
            if pid not in new_printers:
                _logger.info("Printer %s removed from settings, disconnecting", pid)
                self._printer_manager.disconnect_printer(pid)

        # Detect added or changed printers
        for pid, cfg in new_printers.items():
            old_cfg = old_printers.get(pid)
            if old_cfg is None:
                # New printer
                if cfg.get("auto_connect", True):
                    _logger.info("New printer %s added, connecting", cfg.get("name", pid))
                    self._printer_manager.connect_printer(cfg)
            elif self._printer_config_changed(old_cfg, cfg):
                # Connection-relevant config changed
                _logger.info("Printer %s config changed, reconnecting", cfg.get("name", pid))
                self._printer_manager.reconnect_printer(pid, cfg)

    @staticmethod
    def _printer_config_changed(old, new):
        """Check if connection-relevant fields changed."""
        keys = ("hostname", "access_code", "serial_number", "mqtt_port", "external_chamber", "sign_commands")
        return any(old.get(k) != new.get(k) for k in keys)

    # ── Templates ──────────────────────────────────────────────────────

    def get_template_configs(self):
        return [
            {
                "type": "tab",
                "name": "BambuBoard",
                "template": "bambuboard_tab.jinja2",
                "custom_bindings": True,
            },
            {
                "type": "sidebar",
                "name": "Bambu Printers",
                "template": "bambuboard_sidebar.jinja2",
                "icon": "cubes",
                "custom_bindings": True,
            },
            {
                "type": "settings",
                "name": "BambuBoard",
                "template": "bambuboard_settings.jinja2",
                "custom_bindings": True,
            },
            {
                "type": "navbar",
                "template": "bambuboard_navbar.jinja2",
                "custom_bindings": True,
            },
        ]

    # ── Assets ─────────────────────────────────────────────────────────

    def get_assets(self):
        return {
            "js": ["js/bambuboard.js"],
            "css": ["css/bambuboard.css"],
        }

    # ── API: GET ───────────────────────────────────────────────────────

    def on_api_get(self, request):
        if not hasattr(self, "_printer_manager"):
            return flask.jsonify({"printers": {}})

        all_states = self._printer_manager.get_all_states()
        printer_configs = {p["id"]: p.get("name", "Printer") for p in (self._settings.get(["printers"]) or [])}

        printers = {}
        for pid, info in all_states.items():
            printers[pid] = {
                "name": info["name"],
                "connected": info["connected"],
                "connection_state": info.get("connection_state", "disconnected"),
                "printer_model": info.get("printer_model", "UNKNOWN"),
                "error_message": info.get("error_message", ""),
                "state": info["state"],
            }

        # Include configured but not-yet-connected printers
        for pid, name in printer_configs.items():
            if pid not in printers:
                printers[pid] = {
                    "name": name,
                    "connected": False,
                    "connection_state": "disconnected",
                    "printer_model": "UNKNOWN",
                    "error_message": "",
                    "state": {},
                }

        # Include native OctoPrint serial printer
        if self._settings.get_boolean(["show_native_printer"]):
            try:
                native_state = self._get_native_printer_state()
                is_connected = self._printer.is_operational()
                custom_name = self._settings.get(["native_printer_name"])
                name = custom_name if custom_name else "OctoPrint Serial"
                printers[self.NATIVE_PRINTER_ID] = {
                    "name": name,
                    "connected": is_connected,
                    "error_message": "",
                    "is_native": True,
                    "state": native_state,
                }
            except Exception:
                _logger.debug("Could not get native printer state for API response")

        return flask.jsonify({"printers": printers})

    # ── API: Commands ──────────────────────────────────────────────────

    def get_api_commands(self):
        return {
            "connect_printer": ["printer_id"],
            "disconnect_printer": ["printer_id"],
            "test_connection": ["hostname", "access_code", "serial_number"],
            "pause_printing": ["printer_id"],
            "resume_printing": ["printer_id"],
            "stop_printing": ["printer_id"],
            "set_speed_level": ["printer_id", "level"],
            "toggle_light": ["printer_id", "state"],
            "set_bed_temp": ["printer_id", "target"],
            "set_nozzle_temp": ["printer_id", "target"],
            "set_chamber_temp": ["printer_id", "target"],
            "set_part_fan": ["printer_id", "percent"],
            "set_aux_fan": ["printer_id", "percent"],
            "set_exhaust_fan": ["printer_id", "percent"],
            "send_gcode": ["printer_id", "gcode"],
            "get_files": ["printer_id"],
            "start_print": ["printer_id", "file"],
            "delete_file": ["printer_id", "path"],
            "make_directory": ["printer_id", "path"],
            "load_filament": ["printer_id", "slot_id"],
            "unload_filament": ["printer_id"],
            "start_ams_dryer": ["printer_id", "ams_id", "temp", "duration"],
            "stop_ams_dryer": ["printer_id", "ams_id"],
            "set_print_option": ["printer_id", "option", "enabled"],
            "refresh_printer": ["printer_id"],
            # Phase 1B: new commands
            "skip_objects": ["printer_id", "objects"],
            "set_spool_details": ["printer_id", "tray_id"],
            "select_extrusion_calibration_profile": ["printer_id", "tray_id", "cali_idx"],
            "set_nozzle_details": ["printer_id", "nozzle_diameter", "nozzle_type"],
            "set_active_tool": ["printer_id", "tool_id"],
            "refresh_spool_rfid": ["printer_id", "slot_id", "ams_id"],
            "send_ams_control_command": ["printer_id", "ams_command"],
            "set_ams_user_setting": ["printer_id", "setting", "enabled"],
            "set_buildplate_marker_detector": ["printer_id", "enabled"],
            "send_anything": ["printer_id", "payload"],
            "rename_file": ["printer_id", "src", "dest"],
            "pause_session": ["printer_id"],
            "resume_session": ["printer_id"],
        }

    def on_api_command(self, command, data):
        if not hasattr(self, "_printer_manager"):
            return flask.jsonify({"error": "Plugin not initialized"}), 503

        # ── Connection management ──
        if command == "test_connection":
            result = self._printer_manager.test_connection(
                hostname=data["hostname"],
                access_code=data["access_code"],
                serial_number=data["serial_number"],
                mqtt_port=data.get("mqtt_port", 8883),
            )
            return flask.jsonify(result)

        if command == "connect_printer":
            cfg = self._get_printer_config(data["printer_id"])
            if cfg is None:
                return flask.jsonify({"error": "Printer not found in settings"}), 404
            self._printer_manager.connect_printer(cfg)
            return flask.jsonify({"success": True})

        if command == "disconnect_printer":
            self._printer_manager.disconnect_printer(data["printer_id"])
            return flask.jsonify({"success": True})

        # ── All remaining commands need a connected printer ──
        printer_id = data.get("printer_id")
        managed = self._printer_manager.get_printer(printer_id)
        if managed is None or not managed.connected:
            return flask.jsonify({"error": "Printer not connected"}), 400

        instance = managed.instance

        try:
            return self._dispatch_printer_command(command, data, instance, printer_id)
        except Exception as e:
            _logger.exception("Error executing command %s on %s", command, printer_id)
            return flask.jsonify({"error": str(e)}), 500

    def _dispatch_printer_command(self, command, data, instance, printer_id):
        """Dispatch a command to the appropriate BambuPrinter method."""
        from ._vendor.bpm.bambutools import (
            AMSControlCommand,
            AMSUserSetting,
            NozzleDiameter,
            NozzleType,
            PlateType,
            PrintOption,
        )

        if command == "pause_printing":
            instance.pause_printing()

        elif command == "resume_printing":
            instance.resume_printing()

        elif command == "stop_printing":
            instance.stop_printing()

        elif command == "set_speed_level":
            instance.speed_level = str(data["level"])

        elif command == "toggle_light":
            instance.light_state = bool(data["state"])

        elif command == "set_bed_temp":
            instance.set_bed_temp_target(int(data["target"]))

        elif command == "set_nozzle_temp":
            instance.set_nozzle_temp_target(int(data["target"]))

        elif command == "set_chamber_temp":
            instance.set_chamber_temp_target(int(data["target"]))

        elif command == "set_part_fan":
            instance.set_part_cooling_fan_speed_target_percent(int(data["percent"]))

        elif command == "set_aux_fan":
            instance.set_aux_fan_speed_target_percent(int(data["percent"]))

        elif command == "set_exhaust_fan":
            instance.set_exhaust_fan_speed_target_percent(int(data["percent"]))

        elif command == "send_gcode":
            instance.send_gcode(data["gcode"])

        elif command == "get_files":
            files = self._file_manager.get_contents(printer_id)
            return flask.jsonify({"files": files})

        elif command == "start_print":
            try:
                plate_type = PlateType[data.get("bed_type", "AUTO")]
            except KeyError:
                plate_type = PlateType.AUTO
            instance.print_3mf_file(
                name=data["file"],
                plate=int(data.get("plate", 1)),
                bed=plate_type,
                use_ams=bool(data.get("use_ams", True)),
                ams_mapping=data.get("ams_mapping", ""),
            )

        elif command == "delete_file":
            self._file_manager.delete_file(printer_id, data["path"])

        elif command == "make_directory":
            self._file_manager.make_directory(printer_id, data["path"])

        elif command == "load_filament":
            instance.load_filament(
                slot_id=int(data["slot_id"]),
                ams_id=int(data.get("ams_id", 0)),
            )

        elif command == "unload_filament":
            instance.unload_filament(ams_id=int(data.get("ams_id", 0)))

        elif command == "start_ams_dryer":
            instance.turn_on_ams_dryer(
                target_temp=int(data["temp"]),
                duration=int(data["duration"]),
                ams_id=int(data["ams_id"]),
            )

        elif command == "stop_ams_dryer":
            instance.turn_off_ams_dryer(ams_id=int(data["ams_id"]))

        elif command == "set_print_option":
            option = PrintOption[data["option"]]
            instance.set_print_option(option, bool(data["enabled"]))

        elif command == "refresh_printer":
            instance.refresh()

        # ── Phase 1B: new commands ──

        elif command == "skip_objects":
            instance.skip_objects(data["objects"])

        elif command == "set_spool_details":
            instance.set_spool_details(
                tray_id=int(data["tray_id"]),
                tray_info_idx=data.get("tray_info_idx", ""),
                tray_id_name=data.get("tray_id_name", ""),
                tray_type=data.get("tray_type", ""),
                tray_color=data.get("tray_color", ""),
                nozzle_temp_min=int(data.get("nozzle_temp_min", 0)),
                nozzle_temp_max=int(data.get("nozzle_temp_max", 0)),
                ams_id=int(data.get("ams_id", 0)),
            )

        elif command == "select_extrusion_calibration_profile":
            instance.select_extrusion_calibration_profile(
                tray_id=int(data["tray_id"]),
                cali_idx=int(data["cali_idx"]),
            )

        elif command == "set_nozzle_details":
            instance.set_nozzle_details(
                nozzle_diameter=NozzleDiameter[data["nozzle_diameter"]],
                nozzle_type=NozzleType[data["nozzle_type"]],
            )

        elif command == "set_active_tool":
            instance.set_active_tool(int(data["tool_id"]))

        elif command == "refresh_spool_rfid":
            instance.refresh_spool_rfid(
                slot_id=int(data["slot_id"]),
                ams_id=int(data["ams_id"]),
            )

        elif command == "send_ams_control_command":
            instance.send_ams_control_command(AMSControlCommand[data["ams_command"]])

        elif command == "set_ams_user_setting":
            instance.set_ams_user_setting(
                setting=AMSUserSetting[data["setting"]],
                enabled=bool(data["enabled"]),
                ams_id=int(data.get("ams_id", 0)),
            )

        elif command == "set_buildplate_marker_detector":
            instance.set_buildplate_marker_detector(bool(data["enabled"]))

        elif command == "send_anything":
            instance.send_anything(data["payload"])

        elif command == "rename_file":
            instance.rename_sdcard_file(data["src"], data["dest"])

        elif command == "pause_session":
            instance.pause_session()

        elif command == "resume_session":
            instance.resume_session()

        else:
            return flask.jsonify({"error": f"Unknown command: {command}"}), 400

        return flask.jsonify({"success": True})

    # ── Blueprint: File Upload/Download ────────────────────────────────

    @octoprint.plugin.BlueprintPlugin.route("/upload/<printer_id>", methods=["POST"])
    def upload_file(self, printer_id):
        if "file" not in flask.request.files:
            return flask.jsonify({"error": "No file provided"}), 400

        uploaded = flask.request.files["file"]
        if uploaded.filename == "":
            return flask.jsonify({"error": "Empty filename"}), 400

        # Sanitize filename — strip path components
        safe_filename = os.path.basename(uploaded.filename)
        if not safe_filename:
            return flask.jsonify({"error": "Invalid filename"}), 400

        remote_path = flask.request.form.get("path", "/{}".format(safe_filename))
        remote_path = self._sanitize_remote_path(remote_path)

        tmp_dir = tempfile.mkdtemp()
        local_path = os.path.join(tmp_dir, safe_filename)
        try:
            uploaded.save(local_path)
            self._file_manager.upload_file(printer_id, local_path, remote_path)
            return flask.jsonify({"success": True, "path": remote_path})
        except Exception as e:
            _logger.exception("Upload failed for %s", printer_id)
            return flask.jsonify({"error": str(e)}), 500
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @octoprint.plugin.BlueprintPlugin.route("/download/<printer_id>", methods=["GET"])
    def download_file(self, printer_id):
        remote_path = flask.request.args.get("path")
        if not remote_path:
            return flask.jsonify({"error": "No path specified"}), 400

        remote_path = self._sanitize_remote_path(remote_path)
        filename = posixpath.basename(remote_path)
        if not filename:
            return flask.jsonify({"error": "Invalid path"}), 400

        tmp_dir = tempfile.mkdtemp()
        local_path = os.path.join(tmp_dir, filename)

        try:
            self._file_manager.download_file(printer_id, remote_path, local_path)

            # Read into memory so we can clean up the temp dir immediately
            with open(local_path, "rb") as f:
                data = f.read()
        except Exception as e:
            _logger.exception("Download failed for %s", printer_id)
            return flask.jsonify({"error": str(e)}), 500
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        response = flask.make_response(data)
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["Content-Disposition"] = "attachment; filename={}".format(filename)
        return response

    # ── Blueprint: Camera Streaming ────────────────────────────────────

    @octoprint.plugin.BlueprintPlugin.route("/camera/<printer_id>/stream", methods=["GET"])
    def camera_stream(self, printer_id):
        """MJPEG multipart stream for a printer's camera."""
        if not hasattr(self, "_camera_proxy") or not self._camera_proxy.is_available():
            return flask.jsonify({"error": "Camera not available. Install opencv-python-headless."}), 503

        return flask.Response(
            self._camera_proxy.generate_mjpeg(printer_id),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @octoprint.plugin.BlueprintPlugin.route("/camera/<printer_id>/snapshot", methods=["GET"])
    def camera_snapshot(self, printer_id):
        """Single JPEG snapshot from a printer's camera."""
        if not hasattr(self, "_camera_proxy") or not self._camera_proxy.is_available():
            return flask.jsonify({"error": "Camera not available. Install opencv-python-headless."}), 503

        frame = self._camera_proxy.get_snapshot(printer_id)
        if frame is None:
            return flask.jsonify({"error": "No frame available"}), 503

        response = flask.make_response(frame)
        response.headers["Content-Type"] = "image/jpeg"
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    @staticmethod
    def _sanitize_remote_path(path):
        """Normalize and validate a remote SD card path.

        Prevents path traversal by collapsing '..' components and ensuring
        the result stays under the root '/'.
        """
        # Normalize using posixpath (FTP paths are always unix-style)
        normalized = posixpath.normpath(path)
        # Ensure it starts with /
        if not normalized.startswith("/"):
            normalized = "/" + normalized
        # After normpath, any '../' at the start would escape root — reject
        if "/.." in normalized or normalized == "/..":
            raise ValueError("Path traversal detected: {}".format(path))
        return normalized

    def is_blueprint_csrf_protected(self):
        return True

    # ── Virtual Serial Port (Native OctoPrint Integration) ──────────────

    def virtual_serial_port_names(self, candidates, *args, **kwargs):
        """Hook: add BAMBU:<name> ports to OctoPrint's Connection dropdown."""
        if not hasattr(self, "_printer_manager"):
            return candidates

        printers = self._settings.get(["printers"]) or []
        for cfg in printers:
            if cfg.get("register_virtual_serial", True):
                port_name = "BAMBU:{}".format(cfg.get("name", cfg["id"]))
                if port_name not in candidates:
                    candidates.append(port_name)

        return candidates

    def virtual_serial_factory(self, comm_instance, port, baudrate, read_timeout, *args, **kwargs):
        """Hook: create a BambuVirtualSerial when port starts with BAMBU:."""
        if not port or not port.startswith("BAMBU:"):
            return None

        if not hasattr(self, "_printer_manager"):
            return None

        from .virtual_serial import BambuVirtualSerial

        printer_name = port[len("BAMBU:"):]

        # Find the managed printer by name
        printers = self._settings.get(["printers"]) or []
        for cfg in printers:
            if cfg.get("name", cfg["id"]) == printer_name:
                printer_id = cfg["id"]
                managed = self._printer_manager.get_printer(printer_id)
                if managed is None:
                    # Not connected yet — try connecting
                    self._printer_manager.connect_printer(cfg)
                    managed = self._printer_manager.get_printer(printer_id)
                if managed is None:
                    _logger.error("Could not connect printer %s for virtual serial", printer_name)
                    return None

                return BambuVirtualSerial(managed, self._printer_manager)

        _logger.warning("No printer config found matching port %s", port)
        return None

    def virtual_serial_additional_state(self, initial):
        """Hook: inject Bambu state into OctoPrint's native state response."""
        if not hasattr(self, "_printer_manager"):
            return initial

        if not isinstance(initial, dict):
            initial = {}

        all_states = self._printer_manager.get_all_states()
        initial["bambuboard"] = all_states
        return initial

    # ── Native OctoPrint Printer (EventHandlerPlugin) ────────────────

    def on_event(self, event, payload):
        if not self._settings.get_boolean(["show_native_printer"]):
            return

        from octoprint.events import Events

        if event == Events.CONNECTED:
            _logger.info("Native serial printer connected, starting BambuBoard polling")
            self._start_native_poll()
            self._send_native_printer_update()
        elif event == Events.DISCONNECTED:
            _logger.info("Native serial printer disconnected")
            self._stop_native_poll()
            self._send_native_printer_update()
        elif event in (
            Events.PRINT_STARTED,
            Events.PRINT_DONE,
            Events.PRINT_FAILED,
            Events.PRINT_CANCELLED,
            Events.PRINT_PAUSED,
            Events.PRINT_RESUMED,
            Events.Z_CHANGE,
        ):
            self._send_native_printer_update()

    def _start_native_poll(self):
        self._stop_native_poll()
        self._native_poll_timer = RepeatedTimer(2.0, self._send_native_printer_update)
        self._native_poll_timer.daemon = True
        self._native_poll_timer.start()

    def _stop_native_poll(self):
        if hasattr(self, "_native_poll_timer") and self._native_poll_timer is not None:
            self._native_poll_timer.cancel()
            self._native_poll_timer = None

    def _get_native_printer_state(self):
        """Map OctoPrint's native printer state to a BambuBoard-compatible dict."""
        current_data = self._printer.get_current_data()
        temps = self._printer.get_current_temperatures()

        # Connection state
        is_connected = self._printer.is_operational()

        # Progress
        progress = current_data.get("progress", {}) or {}
        completion = progress.get("completion") or 0
        print_time = progress.get("printTime") or 0
        print_time_left = progress.get("printTimeLeft") or 0

        # Job
        job = current_data.get("job", {}) or {}
        file_info = job.get("file", {}) or {}
        filename = file_info.get("display") or file_info.get("name") or ""

        # State
        state = current_data.get("state", {}) or {}
        flags = state.get("flags", {}) or {}

        # Map OctoPrint state to BambuBoard gcode_state
        if flags.get("printing"):
            gcode_state = "RUNNING"
        elif flags.get("pausing") or flags.get("paused"):
            gcode_state = "PAUSE"
        elif flags.get("cancelling"):
            gcode_state = "FAILED"
        elif flags.get("finishing"):
            gcode_state = "FINISH"
        elif flags.get("operational") and not flags.get("ready"):
            gcode_state = "PREPARE"
        else:
            gcode_state = "IDLE"

        # Temperatures
        tool0 = temps.get("tool0", {}) or {}
        bed = temps.get("bed", {}) or {}

        return {
            "printer_model": "NATIVE",
            "service_state": "CONNECTED" if is_connected else "QUIT",
            "gcode_state": gcode_state,
            "firmware_version": "",
            "subtask_name": filename,
            "print_percentage": round(completion, 1) if completion else 0,
            "remaining_minutes": round(print_time_left / 60, 1) if print_time_left else 0,
            "elapsed_minutes": round(print_time / 60, 1) if print_time else 0,
            "current_layer": 0,
            "total_layers": 0,
            "nozzle_temp": tool0.get("actual", 0) or 0,
            "nozzle_temp_target": tool0.get("target", 0) or 0,
            "bed_temp": bed.get("actual", 0) or 0,
            "bed_temp_target": bed.get("target", 0) or 0,
            "chamber_temp": 0,
            "chamber_temp_target": 0,
            "speed_level": 2,
            "light_state": False,
            "has_ams": False,
            "has_camera": False,
            "has_chamber_temp": False,
            "has_dual_extruder": False,
            "has_air_filtration": False,
        }

    def _send_native_printer_update(self):
        if not self._settings.get_boolean(["show_native_printer"]):
            return

        try:
            state_dict = self._get_native_printer_state()
        except Exception:
            _logger.exception("Error getting native printer state")
            return

        is_connected = self._printer.is_operational()
        custom_name = self._settings.get(["native_printer_name"])
        name = custom_name if custom_name else "OctoPrint Serial"

        self._plugin_manager.send_plugin_message(
            self._identifier,
            {
                "type": "printer_update",
                "printer_id": self.NATIVE_PRINTER_ID,
                "name": name,
                "connected": is_connected,
                "is_native": True,
                "state": state_dict,
            },
        )

    # ── Plugin Message Dispatch ────────────────────────────────────────

    def _send_printer_update(self, printer_id, state_dict):
        """Send a real-time printer state update to all connected browsers."""
        managed = self._printer_manager.get_printer(printer_id) if hasattr(self, "_printer_manager") else None
        self._plugin_manager.send_plugin_message(
            self._identifier,
            {
                "type": "printer_update",
                "printer_id": printer_id,
                "name": managed.name if managed else "Unknown",
                "connected": managed.connected if managed else False,
                "connection_state": managed.connection_state.value if managed else "disconnected",
                "printer_model": managed.printer_model if managed else "UNKNOWN",
                "error_message": managed.error_message if managed else "",
                "state": state_dict,
            },
        )

    def _send_connection_event(self, printer_id, event, message=""):
        """Send a connection lifecycle event for toast notifications."""
        self._plugin_manager.send_plugin_message(
            self._identifier,
            {
                "type": "connection_event",
                "printer_id": printer_id,
                "event": event,
                "message": message,
            },
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_printer_config(self, printer_id):
        """Find a printer config by ID from settings."""
        for cfg in self._settings.get(["printers"]) or []:
            if cfg.get("id") == printer_id:
                return cfg
        return None

    # ── Software Update ────────────────────────────────────────────────

    def get_update_information(self):
        return {
            "bambuboard": {
                "displayName": "OctoPrint-BambuBoard",
                "displayVersion": self._plugin_version,
                "type": "github_release",
                "user": "schwarztim",
                "repo": "OctoPrint-BambuBoard",
                "current": self._plugin_version,
                "pip": "https://github.com/schwarztim/OctoPrint-BambuBoard/archive/{target_version}.zip",
            }
        }


__plugin_name__ = "OctoPrint-BambuBoard"
__plugin_pythoncompat__ = ">=3.10,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = BambuBoardPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.comm.transport.serial.additional_port_names": __plugin_implementation__.virtual_serial_port_names,
        "octoprint.comm.transport.serial.factory": __plugin_implementation__.virtual_serial_factory,
        "octoprint.printer.additional_state_data": __plugin_implementation__.virtual_serial_additional_state,
    }
