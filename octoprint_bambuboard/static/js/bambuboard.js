$(function () {
  // ── Filament Presets & Color Palette ─────────────────────────────
  var FILAMENT_PRESETS = {
    PLA: { min: 190, max: 230, idx: "GFL99" },
    "PLA+": { min: 200, max: 230, idx: "GFL01" },
    "PLA Silk": { min: 200, max: 230, idx: "GFL98" },
    PETG: { min: 220, max: 260, idx: "GFG99" },
    ABS: { min: 240, max: 270, idx: "GFA00" },
    ASA: { min: 240, max: 270, idx: "GFA05" },
    TPU: { min: 200, max: 230, idx: "GFU99" },
    "PA/Nylon": { min: 260, max: 300, idx: "GFN99" },
    PC: { min: 260, max: 300, idx: "GFC99" },
    PVA: { min: 190, max: 210, idx: "GFS99" },
    HIPS: { min: 220, max: 250, idx: "" },
    "Wood PLA": { min: 190, max: 220, idx: "" },
    "CF-PLA": { min: 210, max: 240, idx: "" },
    "CF-PETG": { min: 240, max: 270, idx: "" },
  };
  var FILAMENT_TYPES = Object.keys(FILAMENT_PRESETS);

  var FILAMENT_COLORS = [
    { name: "White", hex: "FFFFFF" },
    { name: "Black", hex: "000000" },
    { name: "Gray", hex: "808080" },
    { name: "Silver", hex: "C0C0C0" },
    { name: "Red", hex: "FF0000" },
    { name: "Dark Red", hex: "8B0000" },
    { name: "Orange", hex: "FF6600" },
    { name: "Yellow", hex: "FFD700" },
    { name: "Lemon", hex: "FFFF00" },
    { name: "Lime", hex: "00FF00" },
    { name: "Green", hex: "00AA00" },
    { name: "Dark Green", hex: "006400" },
    { name: "Teal", hex: "008080" },
    { name: "Cyan", hex: "00FFFF" },
    { name: "Light Blue", hex: "87CEEB" },
    { name: "Blue", hex: "0000FF" },
    { name: "Navy", hex: "000080" },
    { name: "Purple", hex: "800080" },
    { name: "Violet", hex: "8B00FF" },
    { name: "Pink", hex: "FF69B4" },
    { name: "Hot Pink", hex: "FF1493" },
    { name: "Magenta", hex: "FF00FF" },
    { name: "Brown", hex: "8B4513" },
    { name: "Tan", hex: "D2B48C" },
    { name: "Gold", hex: "DAA520" },
    { name: "Beige", hex: "F5DEB3" },
    { name: "Natural", hex: "F0E68C" },
    { name: "Olive", hex: "808000" },
    { name: "Bambu Green", hex: "0ACC38" },
    { name: "Fire Red", hex: "F72323" },
    { name: "Sky Blue", hex: "4A90D9" },
    { name: "Transparent", hex: "E8E8E8" },
  ];

  function normalizeColor(c) {
    // Strip # prefix and alpha channel (8th char pair) from Bambu hex colors
    var s = (c || "").replace(/^#/, "").toUpperCase();
    if (s.length === 8) s = s.substring(0, 6);
    return s;
  }

  function PrinterViewModel(data) {
    var self = this;

    // Identity
    self.id = data.id || "";
    self.name = ko.observable(data.name || "Printer");
    self.connectionState = ko.observable(data.connection_state || "pending");
    self.isNative = ko.observable(data.is_native || false);
    self.errorMessage = ko.observable(data.error_message || "");
    self.isNative = ko.observable(data.is_native || false);

    self.connected = ko.computed(function () {
      return self.connectionState() === "connected";
    });

    // Connection
    self.serviceState = ko.observable("NO_STATE");
    self.printerModel = ko.observable("UNKNOWN");
    self.firmwareVersion = ko.observable("");

    // Print job
    self.gcodeState = ko.observable("IDLE");
    self.currentStageName = ko.observable("");
    self.subtaskName = ko.observable("");
    self.printPercentage = ko.observable(0);
    self.remainingMinutes = ko.observable(0);
    self.elapsedMinutes = ko.observable(0);
    self.currentLayer = ko.observable(0);
    self.totalLayers = ko.observable(0);
    self.printError = ko.observable(0);
    self.printType = ko.observable("");
    self.current3mfFile = ko.observable("");
    self.skippedObjects = ko.observableArray([]);

    // Active tool / extruder (H2D)
    self.activeTool = ko.observable("SINGLE_EXTRUDER");
    self.isExternalSpoolActive = ko.observable(false);
    self.targetTrayId = ko.observable(255);

    // Temperatures
    self.bedTemp = ko.observable(0);
    self.bedTempTarget = ko.observable(0);
    self.nozzleTemp = ko.observable(0);
    self.nozzleTempTarget = ko.observable(0);
    self.chamberTemp = ko.observable(0);
    self.chamberTempTarget = ko.observable(0);

    // Editable target inputs (separate from server-reported targets)
    self.bedTempInput = ko.observable("");
    self.nozzleTempInput = ko.observable("");
    self.chamberTempInput = ko.observable("");

    // Fans (read-only from server, separate from slider targets)
    self.partFanSpeed = ko.observable(0);
    self.auxFanSpeed = ko.observable(0);
    self.exhaustFanSpeed = ko.observable(0);
    self.heatbreakFanSpeed = ko.observable(0);

    // Climate / Air Filtration
    self.airductMode = ko.observable(0);
    self.airductSubMode = ko.observable(0);
    self.airConditioningMode = ko.observable("NOT_SUPPORTED");
    self.zoneIntakeOpen = ko.observable(false);
    self.zonePartFanPercent = ko.observable(0);
    self.zoneAuxPercent = ko.observable(0);
    self.zoneExhaustPercent = ko.observable(0);
    self.zoneTopVentOpen = ko.observable(false);
    self.isChamberDoorOpen = ko.observable(false);

    // Nozzle details
    self.nozzleDiameter = ko.observable("UNKNOWN");
    self.nozzleType = ko.observable("UNKNOWN");

    self.nozzleDiameterDisplay = ko.computed(function () {
      var map = {
        POINT_TWO_MM: "0.2",
        POINT_FOUR_MM: "0.4",
        POINT_SIX_MM: "0.6",
        POINT_EIGHT_MM: "0.8",
      };
      return map[self.nozzleDiameter()] || self.nozzleDiameter();
    });
    self.nozzleTypeDisplay = ko.computed(function () {
      var map = {
        STAINLESS_STEEL: "Stainless Steel",
        HARDENED_STEEL: "Hardened Steel",
      };
      return map[self.nozzleType()] || self.nozzleType();
    });

    // Guard flag: suppresses API calls when updating from server state
    self._updatingFromServer = false;

    // Controls
    self.speedLevel = ko.observable(2);
    self.lightState = ko.observable(false);

    // AMS
    self.activeAmsId = ko.observable(-1);
    self.activeTrayId = ko.observable(255);
    self.activeTrayState = ko.observable("UNLOADED");
    self.amsStatusText = ko.observable("");
    self.amsConnectedCount = ko.observable(0);
    self.amsUnits = ko.observableArray([]);
    self.spools = ko.observableArray([]);
    self.extruders = ko.observableArray([]);

    // HMS errors
    self.hmsErrors = ko.observableArray([]);

    // Capabilities
    self.hasAms = ko.observable(false);
    self.hasCamera = ko.observable(false);
    self.hasChamberTemp = ko.observable(false);
    self.hasDualExtruder = ko.observable(false);
    self.hasAirFiltration = ko.observable(false);

    // Print options
    self.autoRecovery = ko.observable(false);
    self.filamentTangleDetect = ko.observable(false);
    self.soundEnable = ko.observable(false);
    self.autoSwitchFilament = ko.observable(false);

    // AMS/Config settings
    self.buildplateMarkerDetector = ko.observable(false);
    self.startupReadOption = ko.observable(false);
    self.trayReadOption = ko.observable(false);
    self.calibrateRemainFlag = ko.observable(false);

    // Wi-Fi signal
    self.wifiSignal = ko.observable("");

    // Files
    self.sdCardContents = ko.observable(null);
    self.filesLoading = ko.observable(false);
    self.fileList = ko.computed(function () {
      var contents = self.sdCardContents();
      if (!contents || typeof contents !== "object") return [];
      return Object.keys(contents);
    });

    // G-code console
    self.gcodeInput = ko.observable("");
    self.gcodeHistory = ko.observableArray([]);

    // Raw JSON console
    self.rawJsonInput = ko.observable("");

    // Skip objects input
    self.skipObjectsInput = ko.observable("");

    // Spool editor modal state
    self.editingSpool = ko.observable(null);
    self.spoolEditorVisible = ko.observable(false);

    // Camera
    self.cameraActive = ko.observable(false);
    self.cameraAvailable = ko.observable(true); // assumed true until proven otherwise

    // Computed
    self.isPrinting = ko.computed(function () {
      var s = self.gcodeState();
      return s === "RUNNING" || s === "PREPARE";
    });

    self.isPaused = ko.computed(function () {
      return self.gcodeState() === "PAUSE";
    });

    self.isIdle = ko.computed(function () {
      var s = self.gcodeState();
      return s === "IDLE" || s === "FINISH" || s === "FAILED";
    });

    self.statusSummary = ko.computed(function () {
      var cs = self.connectionState();
      if (cs === "pending") return "Pending\u2026";
      if (cs === "connecting") return "Connecting\u2026";
      if (cs === "reconnecting") return "Reconnecting\u2026";
      if (cs === "error")
        return "Error: " + (self.errorMessage() || "Connection failed");
      if (cs !== "connected") return "Disconnected";
      var s = self.gcodeState();
      if (s === "RUNNING") return "Printing " + self.printPercentage() + "%";
      if (s === "PREPARE") return "Preparing";
      if (s === "PAUSE") return "Paused";
      if (s === "FINISH") return "Finished";
      if (s === "FAILED") return "Failed";
      return "Idle";
    });

    self.remainingTimeFormatted = ko.computed(function () {
      var mins = self.remainingMinutes();
      if (mins <= 0) return "--";
      var h = Math.floor(mins / 60);
      var m = Math.round(mins % 60);
      return h > 0 ? h + "h " + m + "m" : m + "m";
    });

    self.elapsedTimeFormatted = ko.computed(function () {
      var mins = self.elapsedMinutes();
      if (mins <= 0) return "--";
      var h = Math.floor(mins / 60);
      var m = Math.round(mins % 60);
      return h > 0 ? h + "h " + m + "m" : m + "m";
    });

    self.speedLevelName = ko.computed(function () {
      var names = { 1: "Silent", 2: "Standard", 3: "Sport", 4: "Ludicrous" };
      return names[self.speedLevel()] || "Unknown";
    });

    self.statusClass = ko.computed(function () {
      var cs = self.connectionState();
      if (cs === "pending" || cs === "connecting" || cs === "reconnecting")
        return "bb-status-connecting";
      if (cs === "error") return "bb-status-error";
      if (cs !== "connected") return "bb-status-disconnected";
      var s = self.gcodeState();
      if (s === "RUNNING" || s === "PREPARE") return "bb-status-printing";
      if (s === "PAUSE") return "bb-status-paused";
      if (s === "FAILED") return "bb-status-error";
      return "bb-status-idle";
    });

    self.cameraStreamUrl = ko.computed(function () {
      if (!self.cameraActive()) return "";
      return BASEURL + "plugin/bambuboard/camera/" + self.id + "/stream";
    });

    self.updateFromState = function (state) {
      if (!state || typeof state !== "object") return;

      self._updatingFromServer = true;
      self.serviceState(state.service_state || "NO_STATE");
      self.printerModel(state.printer_model || "UNKNOWN");
      self.firmwareVersion(state.firmware_version || "");

      self.gcodeState(state.gcode_state || "IDLE");
      self.currentStageName(state.current_stage_name || "");
      self.subtaskName(state.subtask_name || "");
      self.printPercentage(state.print_percentage || 0);
      self.remainingMinutes(state.remaining_minutes || 0);
      self.elapsedMinutes(state.elapsed_minutes || 0);
      self.currentLayer(state.current_layer || 0);
      self.totalLayers(state.total_layers || 0);
      self.printError(state.print_error || 0);
      self.printType(state.print_type || "");
      self.current3mfFile(state.current_3mf_file || "");
      self.skippedObjects(state.skipped_objects || []);

      self.activeTool(state.active_tool || "SINGLE_EXTRUDER");
      self.isExternalSpoolActive(state.is_external_spool_active || false);
      self.targetTrayId(
        state.target_tray_id != null ? state.target_tray_id : 255,
      );

      self.bedTemp(state.bed_temp || 0);
      self.bedTempTarget(state.bed_temp_target || 0);
      self.nozzleTemp(state.nozzle_temp || 0);
      self.nozzleTempTarget(state.nozzle_temp_target || 0);
      self.chamberTemp(state.chamber_temp || 0);
      self.chamberTempTarget(state.chamber_temp_target || 0);

      self.partFanSpeed(state.part_fan_speed || 0);
      self.auxFanSpeed(state.aux_fan_speed || 0);
      self.exhaustFanSpeed(state.exhaust_fan_speed || 0);
      self.heatbreakFanSpeed(state.heatbreak_fan_speed || 0);

      self.airductMode(state.airduct_mode || 0);
      self.airductSubMode(state.airduct_sub_mode || 0);
      self.airConditioningMode(state.air_conditioning_mode || "NOT_SUPPORTED");
      self.zoneIntakeOpen(state.zone_intake_open || false);
      self.zonePartFanPercent(state.zone_part_fan_percent || 0);
      self.zoneAuxPercent(state.zone_aux_percent || 0);
      self.zoneExhaustPercent(state.zone_exhaust_percent || 0);
      self.zoneTopVentOpen(state.zone_top_vent_open || false);
      self.isChamberDoorOpen(state.is_chamber_door_open || false);

      self.nozzleDiameter(state.nozzle_diameter || "UNKNOWN");
      self.nozzleType(state.nozzle_type || "UNKNOWN");

      self.speedLevel(state.speed_level || 2);
      self.lightState(state.light_state || false);

      self.activeAmsId(state.active_ams_id != null ? state.active_ams_id : -1);
      self.activeTrayId(
        state.active_tray_id != null ? state.active_tray_id : 255,
      );
      self.activeTrayState(state.active_tray_state || "UNLOADED");
      self.amsStatusText(state.ams_status_text || "");
      self.amsConnectedCount(state.ams_connected_count || 0);
      self.amsUnits(state.ams_units || []);
      self.spools(state.spools || []);
      self.extruders(state.extruders || []);

      self.hmsErrors(state.hms_errors || []);

      self.hasAms(state.has_ams || false);
      self.hasCamera(state.has_camera || false);
      self.hasChamberTemp(state.has_chamber_temp || false);
      self.hasDualExtruder(state.has_dual_extruder || false);
      self.hasAirFiltration(state.has_air_filtration || false);

      self.autoRecovery(state.auto_recovery || false);
      self.filamentTangleDetect(state.filament_tangle_detect || false);
      self.soundEnable(state.sound_enable || false);
      self.autoSwitchFilament(state.auto_switch_filament || false);

      self.buildplateMarkerDetector(state.buildplate_marker_detector || false);
      self.startupReadOption(state.startup_read_option || false);
      self.trayReadOption(state.tray_read_option || false);
      self.calibrateRemainFlag(state.calibrate_remain_flag || false);

      self.wifiSignal(state.wifi_signal || "");
      self._updatingFromServer = false;
    };

    // Initialize from provided data
    if (data.state) {
      self.updateFromState(data.state);
    }
  }

  function BambuBoardViewModel(parameters) {
    var self = this;
    self.loginState = parameters[0];
    self.settings = parameters[1];

    // Expose presets for templates
    self.filamentTypes = FILAMENT_TYPES;
    self.filamentColors = FILAMENT_COLORS;

    // ── Printer list ──────────────────────────────────────────
    self.printers = ko.observableArray([]);
    self.selectedPrinterId = ko.observable("");

    self.selectedPrinter = ko.computed(function () {
      var id = self.selectedPrinterId();
      var list = self.printers();
      for (var i = 0; i < list.length; i++) {
        if (list[i].id === id) return list[i];
      }
      return list.length > 0 ? list[0] : null;
    });

    self.connectedPrinterCount = ko.computed(function () {
      return self.printers().filter(function (p) {
        return p.connected();
      }).length;
    });

    self.totalHmsErrorCount = ko.computed(function () {
      var count = 0;
      self.printers().forEach(function (p) {
        count += p.hmsErrors().length;
      });
      return count;
    });

    // ── Sidebar state ─────────────────────────────────────────
    self.sidebarCollapsed = ko.observable(false);

    self.toggleSidebarCollapsed = function () {
      self.sidebarCollapsed(!self.sidebarCollapsed());
    };

    self.sidebarDisplayMode = ko.computed(function () {
      try {
        return (
          self.settings.settings.plugins.bambuboard.sidebar_display_mode() ||
          "all"
        );
      } catch (e) {
        return "all";
      }
    });

    self.sidebarPrinters = ko.computed(function () {
      var mode = self.sidebarDisplayMode();
      var list = self.printers();
      if (mode === "all") return list;
      if (mode === "active") {
        return list.filter(function (p) {
          return p.isPrinting() || p.isPaused();
        });
      }
      if (mode === "connected") {
        return list.filter(function (p) {
          return p.connected();
        });
      }
      return list;
    });

    self.isPrinterNative = function (printer) {
      // Check if this printer has virtual serial enabled in settings
      try {
        var configs =
          self.settings.settings.plugins.bambuboard.printers() || [];
        for (var i = 0; i < configs.length; i++) {
          var c = configs[i];
          var id = typeof c.id === "function" ? c.id() : c.id;
          var reg =
            typeof c.register_virtual_serial === "function"
              ? c.register_virtual_serial()
              : c.register_virtual_serial;
          if (id === printer.id && reg) return true;
        }
      } catch (e) {
        /* settings not loaded yet */
      }
      return false;
    };

    // ── Settings: printer configs ─────────────────────────────
    self.printerConfigs = ko.observableArray([]);

    self.addPrinter = function () {
      self.printerConfigs.push({
        id: ko.observable(self._generateUUID()),
        name: ko.observable("New Printer"),
        hostname: ko.observable(""),
        access_code: ko.observable(""),
        serial_number: ko.observable(""),
        mqtt_port: ko.observable(8883),
        external_chamber: ko.observable(false),
        sign_commands: ko.observable(true),
        auto_connect: ko.observable(true),
        register_virtual_serial: ko.observable(true),
        camera_url: ko.observable(""),
        _testResult: ko.observable(""),
        _testing: ko.observable(false),
      });
    };

    self.removePrinter = function (printer) {
      if (
        confirm(
          "Remove printer '" + printer.name() + "'? This cannot be undone.",
        )
      ) {
        self.printerConfigs.remove(printer);
      }
    };

    self.testConnection = function (printer) {
      printer._testing(true);
      printer._testResult("");

      OctoPrint.simpleApiCommand("bambuboard", "test_connection", {
        hostname: printer.hostname(),
        access_code: printer.access_code(),
        serial_number: printer.serial_number(),
        mqtt_port: parseInt(printer.mqtt_port()) || 8883,
      })
        .done(function (data) {
          if (data.success) {
            printer._testResult("Connected! Model: " + data.printer_model);
          } else {
            printer._testResult("Failed: " + data.message);
          }
        })
        .fail(function (xhr) {
          printer._testResult(
            "Error: " +
              (xhr.responseJSON ? xhr.responseJSON.error : "Request failed"),
          );
        })
        .always(function () {
          printer._testing(false);
        });
    };

    // ── Settings lifecycle ────────────────────────────────────
    self.onSettingsBeforeSave = function () {
      // Serialize printerConfigs back to settings
      var configs = [];
      var raw = self.printerConfigs();
      for (var i = 0; i < raw.length; i++) {
        var c = raw[i];
        configs.push({
          id: c.id(),
          name: c.name(),
          hostname: c.hostname(),
          access_code: c.access_code(),
          serial_number: c.serial_number(),
          mqtt_port: parseInt(c.mqtt_port()) || 8883,
          external_chamber: c.external_chamber(),
          sign_commands: c.sign_commands(),
          auto_connect: c.auto_connect(),
          register_virtual_serial: c.register_virtual_serial(),
          camera_url: c.camera_url(),
        });
      }
      self.settings.settings.plugins.bambuboard.printers(configs);
    };

    // ── Real-time updates ─────────────────────────────────────
    self.onDataUpdaterPluginMessage = function (plugin, data) {
      if (plugin !== "bambuboard") return;

      if (data.type === "printer_update") {
        var printer = self._findOrCreatePrinter(data.printer_id, data.name);
        printer.connectionState(
          data.connection_state ||
            (data.connected ? "connected" : "disconnected"),
        );
        printer.errorMessage(data.error_message || "");
        if (data.printer_model) printer.printerModel(data.printer_model);
        if (data.is_native !== undefined) printer.isNative(data.is_native);
        if (data.state) {
          printer.updateFromState(data.state);
        }
      }

      if (data.type === "connection_event") {
        self._showConnectionToast(data);
      }
    };

    // ── Initial load ──────────────────────────────────────────
    self.onBeforeBinding = function () {
      self._loadSettingsConfigs();
    };

    self.onAfterBinding = function () {
      self._loadAllStates();

      // Dark mode: apply on load and subscribe to changes
      try {
        var darkObs = self.settings.settings.plugins.bambuboard.dark_mode;
        var applyDark = function (enabled) {
          document.body.classList.toggle("bb-dark-mode", !!enabled);
        };
        applyDark(darkObs());
        darkObs.subscribe(applyDark);
      } catch (e) {
        /* settings not loaded yet */
      }
    };

    self.onSettingsShown = function () {
      self._loadSettingsConfigs();
    };

    self.onTabChange = function (current, previous) {
      if (current === "#tab_plugin_bambuboard") {
        self._loadAllStates();
      }
    };

    // ── Printer commands ──────────────────────────────────────
    self.connectPrinter = function (printer) {
      var id = typeof printer === "string" ? printer : printer.id;
      OctoPrint.simpleApiCommand("bambuboard", "connect_printer", {
        printer_id: id,
      });
    };

    self.disconnectPrinter = function (printer) {
      var id = typeof printer === "string" ? printer : printer.id;
      OctoPrint.simpleApiCommand("bambuboard", "disconnect_printer", {
        printer_id: id,
      });
    };

    self.pausePrinting = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "pause_printing", {
        printer_id: p.id,
      });
    };

    self.resumePrinting = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "resume_printing", {
        printer_id: p.id,
      });
    };

    self.stopPrinting = function () {
      var p = self.selectedPrinter();
      if (!p || !confirm("Stop the current print? This cannot be undone."))
        return;
      OctoPrint.simpleApiCommand("bambuboard", "stop_printing", {
        printer_id: p.id,
      });
    };

    self.setSpeedLevel = function (level) {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "set_speed_level", {
        printer_id: p.id,
        level: level,
      });
    };

    self.toggleLight = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "toggle_light", {
        printer_id: p.id,
        state: !p.lightState(),
      });
    };

    self.setBedTemp = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      var val = parseInt(p.bedTempInput()) || 0;
      OctoPrint.simpleApiCommand("bambuboard", "set_bed_temp", {
        printer_id: p.id,
        target: val,
      });
    };

    self.setNozzleTemp = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      var val = parseInt(p.nozzleTempInput()) || 0;
      OctoPrint.simpleApiCommand("bambuboard", "set_nozzle_temp", {
        printer_id: p.id,
        target: val,
      });
    };

    self.setChamberTemp = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      var val = parseInt(p.chamberTempInput()) || 0;
      OctoPrint.simpleApiCommand("bambuboard", "set_chamber_temp", {
        printer_id: p.id,
        target: val,
      });
    };

    self.setPartFan = function (vm, event) {
      var p = self.selectedPrinter();
      if (!p || p._updatingFromServer) return;
      var val = parseInt(event.target.value) || 0;
      OctoPrint.simpleApiCommand("bambuboard", "set_part_fan", {
        printer_id: p.id,
        percent: val,
      });
    };

    self.setAuxFan = function (vm, event) {
      var p = self.selectedPrinter();
      if (!p || p._updatingFromServer) return;
      var val = parseInt(event.target.value) || 0;
      OctoPrint.simpleApiCommand("bambuboard", "set_aux_fan", {
        printer_id: p.id,
        percent: val,
      });
    };

    self.setExhaustFan = function (vm, event) {
      var p = self.selectedPrinter();
      if (!p || p._updatingFromServer) return;
      var val = parseInt(event.target.value) || 0;
      OctoPrint.simpleApiCommand("bambuboard", "set_exhaust_fan", {
        printer_id: p.id,
        percent: val,
      });
    };

    self.sendGcode = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      var gcode = p.gcodeInput();
      if (!gcode) return;
      OctoPrint.simpleApiCommand("bambuboard", "send_gcode", {
        printer_id: p.id,
        gcode: gcode,
      }).done(function () {
        p.gcodeHistory.unshift({
          command: gcode,
          time: new Date().toLocaleTimeString(),
        });
        if (p.gcodeHistory().length > 50) p.gcodeHistory.pop();
        p.gcodeInput("");
      });
    };

    self.loadFiles = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      p.filesLoading(true);
      OctoPrint.simpleApiCommand("bambuboard", "get_files", {
        printer_id: p.id,
      })
        .done(function (data) {
          p.sdCardContents(data.files || null);
        })
        .fail(function () {
          p.sdCardContents(null);
        })
        .always(function () {
          p.filesLoading(false);
        });
    };

    self.deleteFile = function (path) {
      var p = self.selectedPrinter();
      if (!p || !confirm("Delete " + path + "?")) return;
      OctoPrint.simpleApiCommand("bambuboard", "delete_file", {
        printer_id: p.id,
        path: path,
      }).done(function () {
        self.loadFiles();
      });
    };

    self.makeDirectory = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      var path = prompt("New folder name:");
      if (!path) return;
      OctoPrint.simpleApiCommand("bambuboard", "make_directory", {
        printer_id: p.id,
        path: path,
      }).done(function () {
        self.loadFiles();
      });
    };

    self.startPrint = function (file) {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "start_print", {
        printer_id: p.id,
        file: file,
        plate: 1,
        bed_type: "AUTO",
        use_ams: p.hasAms(),
      });
    };

    self.loadFilament = function (slotId, amsId) {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "load_filament", {
        printer_id: p.id,
        slot_id: slotId,
        ams_id: amsId || 0,
      });
    };

    self.unloadFilament = function (amsId) {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "unload_filament", {
        printer_id: p.id,
        ams_id: amsId || 0,
      });
    };

    self.startAmsDryer = function (amsId) {
      var p = self.selectedPrinter();
      if (!p) return;
      var temp = prompt("Drying temperature:", "55");
      var duration = prompt("Duration (minutes):", "240");
      if (!temp || !duration) return;
      OctoPrint.simpleApiCommand("bambuboard", "start_ams_dryer", {
        printer_id: p.id,
        ams_id: amsId,
        temp: parseInt(temp),
        duration: parseInt(duration),
      });
    };

    self.stopAmsDryer = function (amsId) {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "stop_ams_dryer", {
        printer_id: p.id,
        ams_id: amsId,
      });
    };

    self.setPrintOption = function (option, enabled) {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "set_print_option", {
        printer_id: p.id,
        option: option,
        enabled: enabled,
      });
    };

    self.refreshPrinter = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "refresh_printer", {
        printer_id: p.id,
      });
    };

    self.uploadFile = function (vm, event) {
      var p = self.selectedPrinter();
      if (!p) return;
      var files = event.target.files;
      if (!files || files.length === 0) return;

      var formData = new FormData();
      formData.append("file", files[0]);

      $.ajax({
        url: BASEURL + "plugin/bambuboard/upload/" + p.id,
        type: "POST",
        data: formData,
        processData: false,
        contentType: false,
        headers: {
          "X-CSRF-Token": OctoPrint.getCookie("csrf_token"),
        },
      })
        .done(function () {
          self.loadFiles();
        })
        .fail(function (xhr) {
          alert(
            "Upload failed: " +
              (xhr.responseJSON ? xhr.responseJSON.error : "Unknown error"),
          );
        });

      event.target.value = "";
    };

    // ── Phase 1B commands ─────────────────────────────────────

    self.skipObjects = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      var input = p.skipObjectsInput();
      if (!input) return;
      var objects = input
        .split(",")
        .map(function (s) {
          return parseInt(s.trim());
        })
        .filter(function (n) {
          return !isNaN(n);
        });
      if (objects.length === 0) return;
      OctoPrint.simpleApiCommand("bambuboard", "skip_objects", {
        printer_id: p.id,
        objects: objects,
      }).done(function () {
        p.skipObjectsInput("");
      });
    };

    // Look up spool data for a specific AMS tray position.
    // amsId = AMS unit index (0-based), slotIndex = tray position within unit (0-3)
    self.getSpoolForTray = function (amsId, slotIndex) {
      var p = self.selectedPrinter();
      if (!p) return null;
      var spools = p.spools();
      for (var i = 0; i < spools.length; i++) {
        var s = spools[i];
        if (s && s.ams_id === amsId && s.slot_id === slotIndex) return s;
      }
      return null;
    };

    // Get external spool (vt_tray, ams_id typically 255 or -1)
    self.getExternalSpool = function () {
      var p = self.selectedPrinter();
      if (!p) return null;
      var spools = p.spools();
      for (var i = 0; i < spools.length; i++) {
        var s = spools[i];
        if (
          s &&
          (s.ams_id === 255 || s.ams_id === -1 || s.id === 254 || s.id === 255)
        )
          return s;
      }
      return null;
    };

    self.openSpoolEditor = function (spool) {
      var p = self.selectedPrinter();
      if (!p) return;
      var editing = {
        tray_id: spool.tray_id,
        ams_id: spool.ams_id,
        tray_info_idx: ko.observable(spool.tray_info_idx || ""),
        tray_id_name: ko.observable(spool.tray_id_name || ""),
        tray_type: ko.observable(spool.tray_type || ""),
        tray_color: ko.observable(normalizeColor(spool.tray_color)),
        nozzle_temp_min: ko.observable(spool.nozzle_temp_min || 0),
        nozzle_temp_max: ko.observable(spool.nozzle_temp_max || 0),
      };
      // Auto-fill temps when filament type changes
      editing.tray_type.subscribe(function (newType) {
        var preset = FILAMENT_PRESETS[newType];
        if (preset) {
          editing.nozzle_temp_min(preset.min);
          editing.nozzle_temp_max(preset.max);
          if (preset.idx) editing.tray_info_idx(preset.idx);
        }
      });
      p.editingSpool(editing);
      p.spoolEditorVisible(true);
    };

    self.closeSpoolEditor = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      p.spoolEditorVisible(false);
      p.editingSpool(null);
    };

    self.saveSpoolDetails = function () {
      var p = self.selectedPrinter();
      if (!p || !p.editingSpool()) return;
      var s = p.editingSpool();
      // Normalize color: 6-char hex + FF alpha, no # prefix
      var color = normalizeColor(s.tray_color());
      if (color && color.length === 6) color = color + "FF";
      OctoPrint.simpleApiCommand("bambuboard", "set_spool_details", {
        printer_id: p.id,
        tray_id: s.tray_id,
        ams_id: s.ams_id,
        tray_info_idx: s.tray_info_idx(),
        tray_id_name: s.tray_id_name(),
        tray_type: s.tray_type(),
        tray_color: color,
        nozzle_temp_min: parseInt(s.nozzle_temp_min()) || 0,
        nozzle_temp_max: parseInt(s.nozzle_temp_max()) || 0,
      }).done(function () {
        self.closeSpoolEditor();
      });
    };

    self.refreshSpoolRfid = function (slotId, amsId) {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "refresh_spool_rfid", {
        printer_id: p.id,
        slot_id: slotId,
        ams_id: amsId,
      });
    };

    self.setNozzleDetails = function (diameter, type) {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "set_nozzle_details", {
        printer_id: p.id,
        nozzle_diameter: diameter,
        nozzle_type: type,
      });
    };

    self.setActiveTool = function (toolId) {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "set_active_tool", {
        printer_id: p.id,
        tool_id: toolId,
      });
    };

    self.sendAmsControlCommand = function (command) {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "send_ams_control_command", {
        printer_id: p.id,
        ams_command: command,
      });
    };

    self.setAmsUserSetting = function (setting, enabled, amsId) {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand("bambuboard", "set_ams_user_setting", {
        printer_id: p.id,
        setting: setting,
        enabled: enabled,
        ams_id: amsId || 0,
      });
    };

    self.setBuildplateMarkerDetector = function (enabled) {
      var p = self.selectedPrinter();
      if (!p) return;
      OctoPrint.simpleApiCommand(
        "bambuboard",
        "set_buildplate_marker_detector",
        {
          printer_id: p.id,
          enabled: enabled,
        },
      );
    };

    self.sendAnything = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      var payload = p.rawJsonInput();
      if (!payload) return;
      OctoPrint.simpleApiCommand("bambuboard", "send_anything", {
        printer_id: p.id,
        payload: payload,
      }).done(function () {
        p.gcodeHistory.unshift({
          command: "RAW: " + payload,
          time: new Date().toLocaleTimeString(),
        });
        if (p.gcodeHistory().length > 50) p.gcodeHistory.pop();
        p.rawJsonInput("");
      });
    };

    self.renameFile = function (path) {
      var p = self.selectedPrinter();
      if (!p) return;
      var newName = prompt("New name:", path);
      if (!newName || newName === path) return;
      OctoPrint.simpleApiCommand("bambuboard", "rename_file", {
        printer_id: p.id,
        src: path,
        dest: newName,
      }).done(function () {
        self.loadFiles();
      });
    };

    // ── Camera commands ─────────────────────────────────────

    self.toggleCameraStream = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      p.cameraActive(!p.cameraActive());
    };

    self.cameraSnapshot = function () {
      var p = self.selectedPrinter();
      if (!p) return;
      var url =
        BASEURL +
        "plugin/bambuboard/camera/" +
        p.id +
        "/snapshot?t=" +
        Date.now();
      window.open(url, "_blank");
    };

    // ── Internal helpers ──────────────────────────────────────

    self._findOrCreatePrinter = function (id, name) {
      var list = self.printers();
      for (var i = 0; i < list.length; i++) {
        if (list[i].id === id) return list[i];
      }
      var printer = new PrinterViewModel({ id: id, name: name || "Printer" });
      self.printers.push(printer);
      if (!self.selectedPrinterId()) {
        self.selectedPrinterId(id);
      }
      return printer;
    };

    self._loadAllStates = function () {
      OctoPrint.simpleApiGet("bambuboard").done(function (data) {
        if (!data || !data.printers) return;

        Object.keys(data.printers).forEach(function (pid) {
          var info = data.printers[pid];
          var printer = self._findOrCreatePrinter(pid, info.name);
          printer.connectionState(
            info.connection_state ||
              (info.connected ? "connected" : "disconnected"),
          );
          printer.errorMessage(info.error_message || "");
          if (info.printer_model) printer.printerModel(info.printer_model);
          if (info.is_native !== undefined) printer.isNative(info.is_native);
          if (info.state) {
            printer.updateFromState(info.state);
          }
        });

        // Auto-select default or first printer
        if (!self.selectedPrinterId() && self.printers().length > 0) {
          var defaultId =
            self.settings.settings.plugins.bambuboard.default_printer_id();
          if (
            defaultId &&
            self.printers().some(function (p) {
              return p.id === defaultId;
            })
          ) {
            self.selectedPrinterId(defaultId);
          } else {
            self.selectedPrinterId(self.printers()[0].id);
          }
        }
      });
    };

    self._loadSettingsConfigs = function () {
      var raw = self.settings.settings.plugins.bambuboard.printers();
      var configs = [];
      if (Array.isArray(raw)) {
        raw.forEach(function (c) {
          // OctoPrint wraps each field in ko.observable — unwrap before re-wrapping
          var u = ko.unwrap;
          configs.push({
            id: ko.observable(u(c.id) || self._generateUUID()),
            name: ko.observable(u(c.name) || ""),
            hostname: ko.observable(u(c.hostname) || ""),
            access_code: ko.observable(u(c.access_code) || ""),
            serial_number: ko.observable(u(c.serial_number) || ""),
            mqtt_port: ko.observable(u(c.mqtt_port) || 8883),
            external_chamber: ko.observable(u(c.external_chamber) || false),
            sign_commands: ko.observable(u(c.sign_commands) !== false),
            auto_connect: ko.observable(u(c.auto_connect) !== false),
            register_virtual_serial: ko.observable(
              u(c.register_virtual_serial) !== false,
            ),
            camera_url: ko.observable(u(c.camera_url) || ""),
            _testResult: ko.observable(""),
            _testing: ko.observable(false),
          });
        });
      }
      self.printerConfigs(configs);
    };

    // ── Connection helpers ──────────────────────────────────
    self._showConnectionToast = function (data) {
      if (typeof PNotify === "undefined") return;
      try {
        var type = "info";
        if (data.event === "connected") type = "success";
        if (data.event === "error") type = "error";
        if (data.event === "disconnected") type = "notice";
        new PNotify({
          title: "BambuBoard",
          text: data.message || data.event,
          type: type,
          hide: data.event !== "error",
          delay: 5000,
        });
      } catch (e) {
        console.warn("BambuBoard: PNotify error:", e);
      }
    };

    self._printerConnectionClass = function (printerId) {
      var list = self.printers();
      for (var i = 0; i < list.length; i++) {
        if (list[i].id === printerId) {
          var cs = list[i].connectionState();
          if (cs === "connected") return "bb-status-dot-connected";
          if (cs === "connecting" || cs === "reconnecting")
            return "bb-status-dot-connecting";
          if (cs === "error") return "bb-status-dot-error";
          return "bb-status-dot-disconnected";
        }
      }
      return "bb-status-dot-disconnected";
    };

    self._printerConnectionText = function (printerId) {
      var list = self.printers();
      for (var i = 0; i < list.length; i++) {
        if (list[i].id === printerId) {
          var cs = list[i].connectionState();
          if (cs === "connected") return "Connected";
          if (cs === "connecting") return "Connecting\u2026";
          if (cs === "reconnecting") return "Reconnecting\u2026";
          if (cs === "error") return "Error";
          return "Not connected";
        }
      }
      return "Not connected";
    };

    self._generateUUID = function () {
      return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
        /[xy]/g,
        function (c) {
          var r = (Math.random() * 16) | 0;
          var v = c === "x" ? r : (r & 0x3) | 0x8;
          return v.toString(16);
        },
      );
    };
  }

  OCTOPRINT_VIEWMODELS.push({
    construct: BambuBoardViewModel,
    dependencies: ["loginStateViewModel", "settingsViewModel"],
    elements: [
      "#tab_plugin_bambuboard",
      "#sidebar_plugin_bambuboard",
      "#settings_plugin_bambuboard",
      "#navbar_plugin_bambuboard",
    ],
  });
});
