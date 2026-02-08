"""Virtual serial port that makes Bambu printers appear in OctoPrint's Connection dropdown.

Shares the existing ManagedPrinter MQTT session (no duplicate connections).
Translates M-codes to BambuPrinter actions and emits Marlin-format responses.
"""

import logging
import queue
import re
import threading
import time

_logger = logging.getLogger("octoprint.plugins.bambuboard.virtual_serial")

# Matches standard Marlin M-code patterns
_MCODE_RE = re.compile(r"^M(\d+)")


class BambuVirtualSerial:
    """A virtual serial transport for a single Bambu printer.

    Implements the minimal interface OctoPrint expects from a serial connection:
    write(), readline(), close(), plus the @property attributes.
    """

    def __init__(self, managed_printer, printer_manager):
        self._managed = managed_printer
        self._pm = printer_manager
        self._instance = managed_printer.instance

        self._output = queue.Queue()
        self._closed = False
        self._lock = threading.Lock()

        # Chain into the existing MQTT update callback
        self._original_on_update = self._instance.on_update
        self._instance.on_update = self._chained_on_update

        # Send initial identification
        self._output.put("start\n")
        self._output.put("ok\n")

        _logger.info(
            "Virtual serial opened for %s (%s)",
            managed_printer.name,
            managed_printer.printer_id,
        )

    # ── Serial interface expected by OctoPrint ────────────────

    def write(self, data):
        """Process data written by OctoPrint (G-code/M-code commands)."""
        if self._closed:
            return 0

        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")

        line = data.strip()
        if not line:
            return len(data)

        self._handle_command(line)
        return len(data)

    def readline(self):
        """Read next line of output for OctoPrint. Blocks with timeout."""
        try:
            line = self._output.get(timeout=1.0)
            if isinstance(line, str):
                line = line.encode("utf-8")
            return line
        except queue.Empty:
            return b""

    def close(self):
        """Close the virtual serial connection."""
        with self._lock:
            if self._closed:
                return
            self._closed = True

        # Restore original callback
        if self._instance and self._original_on_update:
            self._instance.on_update = self._original_on_update

        _logger.info("Virtual serial closed for %s", self._managed.name)

    @property
    def timeout(self):
        return 1.0

    @timeout.setter
    def timeout(self, value):
        pass  # OctoPrint sets this; we use our own timeout in readline

    @property
    def port(self):
        return f"BAMBU:{self._managed.name}"

    @property
    def baudrate(self):
        return 115200

    @baudrate.setter
    def baudrate(self, value):
        pass

    @property
    def in_waiting(self):
        return self._output.qsize()

    # ── M-code handling ───────────────────────────────────────

    def _handle_command(self, line):
        """Parse and dispatch an M-code or G-code command."""
        match = _MCODE_RE.match(line)
        if not match:
            # Not an M-code — forward as raw G-code
            if line.startswith("G") or line.startswith("T"):
                self._instance.send_gcode(line)
            self._output.put("ok\n")
            return

        mcode = int(match.group(1))

        if mcode == 105:
            # M105: Report temperatures
            self._report_temps()

        elif mcode == 115:
            # M115: Firmware info
            model = self._managed.config.printer_model.name
            fw = self._managed.config.firmware_version or "unknown"
            self._output.put(
                f"FIRMWARE_NAME:BambuBoard FIRMWARE_VERSION:{fw} "
                f"MACHINE_TYPE:{model} PROTOCOL_VERSION:1.0\n"
            )

        elif mcode == 104:
            # M104: Set hotend temp
            temp = self._parse_param(line, "S", 0)
            self._instance.set_nozzle_temp_target(int(temp))

        elif mcode == 140:
            # M140: Set bed temp
            temp = self._parse_param(line, "S", 0)
            self._instance.set_bed_temp_target(int(temp))

        elif mcode == 106:
            # M106: Fan on (S0-255 → 0-100%)
            speed = self._parse_param(line, "S", 255)
            percent = int(round(speed / 255 * 100))
            self._instance.set_part_cooling_fan_speed_target_percent(percent)

        elif mcode == 107:
            # M107: Fan off
            self._instance.set_part_cooling_fan_speed_target_percent(0)

        elif mcode == 24:
            # M24: Resume print
            self._instance.resume_printing()

        elif mcode == 25:
            # M25: Pause print
            self._instance.pause_printing()

        elif mcode == 27:
            # M27: Report SD print status
            state = self._managed.instance.printer_state
            pct = state.print_percentage
            if state.gcode_state in ("RUNNING", "PREPARE"):
                self._output.put(f"SD printing byte {pct}/100\n")
            else:
                self._output.put("Not SD printing.\n")

        else:
            # Unknown M-code — try forwarding as G-code
            self._instance.send_gcode(line)

        self._output.put("ok\n")

    def _report_temps(self):
        """Emit a Marlin-format temperature line."""
        state = self._managed.instance.printer_state
        climate = state.climate

        nozzle_temp = state.active_nozzle_temp
        nozzle_target = state.active_nozzle_temp_target
        bed_temp = climate.bed_temp
        bed_target = climate.bed_temp_target

        line = (
            f"ok T:{nozzle_temp:.1f} /{nozzle_target} "
            f"B:{bed_temp:.1f} /{bed_target}"
        )

        # Add chamber if supported
        caps = state.capabilities
        if caps.has_chamber_temp:
            chamber = climate.chamber_temp
            chamber_target = climate.chamber_temp_target
            line += f" C:{chamber:.1f} /{chamber_target}"

        self._output.put(line + "\n")

    # ── Chained MQTT callback ─────────────────────────────────

    def _chained_on_update(self, bambu_printer):
        """Generate Marlin temp lines, then call the original BambuBoard callback."""
        if not self._closed:
            # Emit an auto-report temperature line (like M155)
            self._report_temps()

        # Always call the original callback so BambuBoard tab still works
        if self._original_on_update:
            self._original_on_update(bambu_printer)

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _parse_param(line, param, default=0):
        """Extract a numeric parameter from a G-code line (e.g., S200 → 200)."""
        match = re.search(rf"{param}(\d+\.?\d*)", line)
        if match:
            return float(match.group(1))
        return default
