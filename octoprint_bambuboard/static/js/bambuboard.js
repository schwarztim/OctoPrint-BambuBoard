$(function () {
  function PrinterViewModel(data) {
    var self = this;

    // Identity
    self.id = data.id || "";
    self.name = ko.observable(data.name || "Printer");
    self.connected = ko.observable(data.connected || false);
    self.errorMessage = ko.observable(data.error_message || "");

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
      if (!self.connected()) return "Disconnected";
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
      if (!self.connected()) return "bb-status-disconnected";
      var s = self.gcodeState();
      if (s === "RUNNING" || s === "PREPARE") return "bb-status-printing";
      if (s === "PAUSE") return "bb-status-paused";
      if (s === "FAILED") return "bb-status-error";
      return "bb-status-idle";
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

      self.bedTemp(state.bed_temp || 0);
      self.bedTempTarget(state.bed_temp_target || 0);
      self.nozzleTemp(state.nozzle_temp || 0);
      self.nozzleTempTarget(state.nozzle_temp_target || 0);
      self.chamberTemp(state.chamber_temp || 0);
      self.chamberTempTarget(state.chamber_temp_target || 0);

      self.partFanSpeed(state.part_fan_speed || 0);
      self.auxFanSpeed(state.aux_fan_speed || 0);
      self.exhaustFanSpeed(state.exhaust_fan_speed || 0);

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
        auto_connect: ko.observable(true),
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
          auto_connect: c.auto_connect(),
        });
      }
      self.settings.settings.plugins.bambuboard.printers(configs);
    };

    // ── Real-time updates ─────────────────────────────────────
    self.onDataUpdaterPluginMessage = function (plugin, data) {
      if (plugin !== "bambuboard") return;

      if (data.type === "printer_update") {
        var printer = self._findOrCreatePrinter(data.printer_id, data.name);
        printer.connected(data.connected || false);
        if (data.state) {
          printer.updateFromState(data.state);
        }
      }
    };

    // ── Initial load ──────────────────────────────────────────
    self.onBeforeBinding = function () {
      self._loadSettingsConfigs();
    };

    self.onAfterBinding = function () {
      self._loadAllStates();
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
          "X-CSRF-Token": OctoPrint.getCookie("csrf_token_bambuboard"),
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
          printer.connected(info.connected || false);
          printer.errorMessage(info.error_message || "");
          if (info.state) {
            printer.updateFromState(info.state);
          }
        });

        // Auto-select first printer if none selected
        if (!self.selectedPrinterId() && self.printers().length > 0) {
          self.selectedPrinterId(self.printers()[0].id);
        }
      });
    };

    self._loadSettingsConfigs = function () {
      var raw = self.settings.settings.plugins.bambuboard.printers();
      var configs = [];
      if (Array.isArray(raw)) {
        raw.forEach(function (c) {
          configs.push({
            id: ko.observable(c.id || self._generateUUID()),
            name: ko.observable(c.name || ""),
            hostname: ko.observable(c.hostname || ""),
            access_code: ko.observable(c.access_code || ""),
            serial_number: ko.observable(c.serial_number || ""),
            mqtt_port: ko.observable(c.mqtt_port || 8883),
            external_chamber: ko.observable(c.external_chamber || false),
            auto_connect: ko.observable(c.auto_connect !== false),
            _testResult: ko.observable(""),
            _testing: ko.observable(false),
          });
        });
      }
      self.printerConfigs(configs);
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
