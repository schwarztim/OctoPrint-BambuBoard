# OctoPrint-BambuBoard

A multi-printer Bambu Lab dashboard plugin for [OctoPrint](https://octoprint.org/).

Manage multiple Bambu Lab printers from a single OctoPrint instance with real-time MQTT monitoring, full print control, AMS management, camera streaming, and an integrated file browser — all without replacing OctoPrint's native functionality.

## Supported Printers

| Series | Models                   |
| ------ | ------------------------ |
| **X1** | X1 Carbon, X1, X1E       |
| **P1** | P1S, P1P                 |
| **A1** | A1, A1 Mini              |
| **P2** | P2S                      |
| **H2** | H2S, H2D (dual extruder) |

Printer model is automatically detected from the serial number prefix — no MQTT connection needed for identification.

## Features

### Real-Time Dashboard

- Live temperature monitoring for bed, nozzle, and chamber (where supported)
- Print progress with percentage, elapsed time, remaining time, current/total layers
- Fan speed indicators (part cooling, auxiliary, exhaust, heatbreak)
- Wi-Fi signal strength display
- Firmware version and nozzle configuration display (diameter + type)
- Connection state machine with visual feedback: Pending → Connecting → Connected, with Error/Reconnecting states

### Print Control

- Start prints from the printer's SD card (`.3mf` files)
- Pause, resume, and stop active prints
- Speed profile selection: Silent, Standard, Sport, Ludicrous
- Skip/cancel individual objects mid-print
- Chamber LED on/off toggle

### Temperature & Fan Control

- Set bed, nozzle, and chamber temperature targets directly from the dashboard
- Adjust part cooling, auxiliary, and exhaust fan speeds with sliders
- Real-time feedback — changes reflect immediately via MQTT updates

### AMS (Automatic Material System) Management

- View all AMS units, trays, and spool details (color, material, remaining %)
- Load and unload filament by tray
- Start/stop AMS dryer with configurable temperature and duration
- Refresh spool RFID data
- Edit spool details (material, color, temperatures)
- AMS control commands: Pause, Resume, Reset
- User settings: calibrate remaining flag, startup read, tray read

### File Browser

- Browse the printer's SD card directory tree
- Upload files from your computer to the printer
- Download files from the printer
- Create new directories
- Rename and delete files
- One-click print for `.3mf` files

### Camera Streaming

- Live MJPEG camera stream from the printer's built-in camera (RTSP → MJPEG proxy)
- Single-frame snapshot capture
- Auto-stops after 60 seconds of inactivity to save resources
- Requires `opencv-python-headless` (installed automatically)

### G-code & Raw MQTT Console

- Send arbitrary G-code commands with scrollable history (last 50 commands)
- Send raw JSON payloads directly to the printer's MQTT topic for advanced control
- Full command history with timestamps

### Print Options

- Auto Recovery
- Filament Tangle Detect
- Sound Enable
- Auto Switch Filament
- Buildplate Marker Detector (Vision AI)

### Nozzle Configuration

- View and change nozzle diameter (0.2mm, 0.4mm, 0.6mm, 0.8mm)
- View and change nozzle type (Stainless Steel, Hardened Steel, HS01, HH01)

### HMS Error Display

- Decoded Health Management System errors with severity and descriptions
- Error count badge in sidebar and navbar for at-a-glance awareness

### Multi-Printer Management

- Connect and monitor multiple Bambu printers simultaneously
- Each printer gets an independent MQTT connection with automatic retry
- Sidebar widget showing all printers with status dots, temperatures, and print progress
- Navbar dropdown for quick-access printer status
- Sidebar filtering: show all printers, only active (printing/paused), or only connected
- Per-printer connection state tracking with toast notifications (connected, disconnected, error, reconnecting)

### OctoPrint Virtual Serial Integration

- Optionally registers each Bambu printer as a virtual serial port in OctoPrint
- Appears as `BAMBU:<PrinterName>` in OctoPrint's serial port dropdown
- Translates standard M-codes (M104, M140, M105, M106, M107, M24, M25, M27, M115) to Bambu MQTT commands
- Enables OctoPrint's native temperature graph, print status, and plugins to work with Bambu printers
- Enabled by default for new printers — disable per-printer in settings if not needed

### Dark Mode

- Toggle dark mode from settings for the BambuBoard dashboard

## Requirements

- **OctoPrint** 1.5.0 or later
- **Python** 3.10 or later
- **Network access** to your Bambu Lab printer(s) on port 8883 (MQTT over TLS)
- **opencv-python-headless** (optional, for camera streaming — installed automatically with the plugin)

## Installation

### From OctoPrint Plugin Manager (Recommended)

1. Open OctoPrint **Settings** → **Plugin Manager**
2. Click **Get More...**
3. Paste this URL in the **...from URL** field:
   ```
   https://github.com/schwarztim/OctoPrint-BambuBoard/archive/main.zip
   ```
4. Click **Install** and restart OctoPrint

### Manual / Development Install

```bash
git clone https://github.com/schwarztim/OctoPrint-BambuBoard.git
cd OctoPrint-BambuBoard
pip install -e .
```

### Docker

If running OctoPrint in Docker, install the plugin by adding the GitHub URL to your plugin install list or by mounting the plugin directory into the container's `site-packages`.

## Configuration

### Adding a Printer

1. Open OctoPrint **Settings**
2. Navigate to **BambuBoard** under Plugins
3. Click **Add Printer** and fill in:

| Field                          | Description                                      | Where to Find                                                                          |
| ------------------------------ | ------------------------------------------------ | -------------------------------------------------------------------------------------- |
| **Name**                       | Friendly display name                            | Your choice                                                                            |
| **Hostname / IP**              | Printer's local IP address                       | Printer screen → Network → IP Address                                                  |
| **Access Code**                | 8-digit access code                              | Printer screen → Network → Access Code                                                 |
| **Serial Number**              | Printer serial number                            | Printer screen → Device → Serial Number, or sticker on the printer, or Bambu Handy app |
| **MQTT Port**                  | MQTT broker port                                 | Defaults to `8883` (standard Bambu TLS MQTT)                                           |
| **External Chamber**           | Enable for printers with external chamber sensor | Only for X1E or aftermarket mods                                                       |
| **Register as Virtual Serial** | Add as `BAMBU:<name>` serial port in OctoPrint   | Enabled by default                                                                     |
| **Auto Connect**               | Connect automatically on OctoPrint startup       | Enabled by default                                                                     |

4. Click **Test Connection** to verify connectivity
5. Click **Save** — printers with auto-connect enabled will connect immediately

### Finding Your Printer's Access Code

1. On the printer touchscreen, go to **Settings** (gear icon)
2. Navigate to **Network** → **WLAN**
3. The **Access Code** is displayed (8-digit alphanumeric code)

### Finding Your Printer's Serial Number

The serial number is:

- On the printer's touchscreen under **Settings** → **Device**
- On a sticker on the back or bottom of the printer
- In the **Bambu Handy** app under device details

The first 3 characters of the serial number determine the printer model:

| Prefix | Model     |
| ------ | --------- |
| `00M`  | X1 Carbon |
| `00W`  | X1        |
| `03W`  | X1E       |
| `01S`  | P1P       |
| `01P`  | P1S       |
| `030`  | A1 Mini   |
| `039`  | A1        |
| `22E`  | P2S       |
| `093`  | H2S       |
| `094`  | H2D       |

## Architecture

### How It Works

BambuBoard does **not** use OctoPrint's native serial communication for printer control. Instead, it manages independent MQTT connections to each Bambu Lab printer using the vendored [`bambu-printer-manager`](https://github.com/synman/bambu-printer-manager) library.

```
OctoPrint UI
    │
    ├── BambuBoard Tab ──────── bambuboard.js (Knockout.js viewmodel)
    │       │                        │
    │       │                   WebSocket (plugin messages)
    │       │                        │
    │       ▼                        ▼
    │   REST API ◄──────────── __init__.py (OctoPrint plugin)
    │                                │
    │                          PrinterManager
    │                           │         │
    │                      ManagedPrinter  ManagedPrinter
    │                           │              │
    │                      BambuPrinter   BambuPrinter
    │                       (MQTT/TLS)     (MQTT/TLS)
    │                           │              │
    │                      ┌────┘              └────┐
    │                      ▼                        ▼
    │                 Bambu Printer 1          Bambu Printer 2
    │
    ├── OctoPrint Serial ──── Virtual Serial Bridge (optional)
    │       │                        │
    │       ▼                        ▼
    │   M-code translation ──── BambuPrinter MQTT commands
    │   (M104, M140, etc.)
    │
    └── Sidebar / Navbar ──── Compact status widgets
```

### Key Components

| File                 | Purpose                                                              |
| -------------------- | -------------------------------------------------------------------- |
| `__init__.py`        | Plugin entry point, API routes, OctoPrint lifecycle hooks            |
| `printer_manager.py` | Multi-printer connection lifecycle with retry loop and state machine |
| `state_bridge.py`    | Serializes BambuPrinter state to frontend-friendly JSON (60+ fields) |
| `virtual_serial.py`  | Translates M-codes to MQTT commands for OctoPrint serial integration |
| `camera_proxy.py`    | RTSP → MJPEG streaming proxy with auto-timeout                       |
| `file_manager.py`    | FTP/FTPS file operations (upload, download, browse, delete)          |
| `bambuboard.js`      | Knockout.js frontend viewmodel with 100+ observables                 |

### Connection State Machine

Each printer connection follows this state flow:

```
PENDING ──► CONNECTING ──► CONNECTED
                │                │
                ▼                ▼ (connection lost)
              ERROR        RECONNECTING ──► CONNECTING
                                              │
                                              ▼
                                          CONNECTED
```

- **Pending**: Printer configured but not yet started
- **Connecting**: MQTT session starting, retrying every ~1 second (matches standalone BPM behavior)
- **Connected**: MQTT session established, receiving real-time telemetry
- **Error**: Connection failed (bad credentials, network unreachable)
- **Reconnecting**: Previously connected but lost connection, auto-retrying after 5-second delay

The UI shows pulsing status dots for connecting/reconnecting states, solid dots for connected, and error messages for failed connections. Toast notifications appear for connection lifecycle events.

## Troubleshooting

### Printer shows "Connecting..." indefinitely

- Verify the printer is powered on and connected to your local network
- Check that the IP address is correct and reachable (`ping <printer-ip>`)
- Verify port 8883 is accessible (`nc -zv <printer-ip> 8883`)
- Ensure the access code matches what's displayed on the printer screen
- Check OctoPrint logs for connection errors: `octoprint.log` → search for `bambuboard`

### Camera stream not working

- Camera streaming requires `opencv-python-headless` to be installed
- The RTSP stream uses port 322 — verify it's not blocked by your network
- Check that the printer's camera is enabled in its settings
- Camera auto-stops after 60 seconds of inactivity — click to restart

### Virtual serial port not appearing

- Ensure "Register as Virtual Serial Port" is enabled for the printer in BambuBoard settings
- The port appears as `BAMBU:<PrinterName>` in OctoPrint's serial port dropdown
- Restart OctoPrint after enabling the setting

### Temperature graph shows 0

- The virtual serial bridge must be connected (select the `BAMBU:` port in OctoPrint's Connection panel)
- Temperature updates come via MQTT — ensure the printer is connected in BambuBoard first

### Print options not saving

- Print options are sent to the printer immediately when toggled — they don't persist in OctoPrint settings
- The printer must be connected for print options to take effect

## API

BambuBoard exposes a REST API via OctoPrint's `SimpleApiPlugin` interface.

### GET `/api/plugin/bambuboard`

Returns current state of all printers.

### POST `/api/plugin/bambuboard`

Send commands. All commands require a `command` field and most require a `printer_id` field.

<details>
<summary>Available commands (35 total)</summary>

**Connection**: `test_connection`, `connect_printer`, `disconnect_printer`

**Print Control**: `pause_printing`, `resume_printing`, `stop_printing`, `start_print`, `skip_objects`

**Temperature**: `set_bed_temp`, `set_nozzle_temp`, `set_chamber_temp`

**Fans**: `set_part_fan`, `set_aux_fan`, `set_exhaust_fan`

**Speed & LED**: `set_speed_level`, `toggle_light`

**AMS**: `load_filament`, `unload_filament`, `send_ams_control_command`, `start_ams_dryer`, `stop_ams_dryer`, `refresh_spool_rfid`, `set_spool_details`, `set_ams_user_setting`

**Files**: `get_files`, `delete_file`, `make_directory`, `rename_file`

**Configuration**: `set_nozzle_details`, `set_active_tool`, `select_extrusion_calibration_profile`, `set_print_option`, `set_buildplate_marker_detector`

**Advanced**: `send_gcode`, `send_anything`, `refresh_printer`, `pause_session`, `resume_session`

</details>

### Blueprint Routes

| Route                                             | Method | Description                        |
| ------------------------------------------------- | ------ | ---------------------------------- |
| `/plugin/bambuboard/upload/<printer_id>`          | POST   | Upload file to printer SD card     |
| `/plugin/bambuboard/download/<printer_id>`        | GET    | Download file from printer SD card |
| `/plugin/bambuboard/camera/<printer_id>/stream`   | GET    | MJPEG camera stream                |
| `/plugin/bambuboard/camera/<printer_id>/snapshot` | GET    | Single JPEG frame                  |

## Credits

- Built on the [bambu-printer-manager](https://github.com/synman/bambu-printer-manager) library by [synman](https://github.com/synman)
- Designed for [OctoPrint](https://octoprint.org/) by [Gina Haussge](https://github.com/foosel)

## License

[AGPLv3](LICENSE)
