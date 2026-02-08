# OctoPrint-BambuBoard

A multi-printer Bambu Lab dashboard plugin for [OctoPrint](https://octoprint.org/).

Manage multiple Bambu Lab printers (P1S, X1C, A1, etc.) from a single OctoPrint instance with real-time MQTT monitoring and full control.

## Features

- **Multi-printer support** — connect and monitor multiple Bambu printers simultaneously
- **Real-time dashboard** — live temperatures, print progress, fan speeds, AMS status via MQTT
- **Full print control** — pause/resume/stop, speed levels, LED toggle, temperature targets, fan control
- **AMS management** — view tray contents, load/unload filament, start/stop dryer
- **File browser** — browse, upload, download, and delete files on the printer's SD card
- **G-code console** — send arbitrary G-code commands
- **HMS error display** — decoded health management system errors
- **Print options** — auto-recovery, filament tangle detect, sound, auto-switch filament
- **Sidebar summary** — compact multi-printer status at a glance
- **Navbar indicator** — quick-access printer status dropdown

## Requirements

- OctoPrint 1.5.0+
- Python 3.10+
- Network access to your Bambu Lab printer(s) on port 8883 (MQTT/TLS)

## Installation

1. Open OctoPrint Settings → **Plugin Manager**
2. Click **Get More...**
3. Paste this URL in the **...from URL** field:
   ```
   https://github.com/schwarztim/OctoPrint-BambuBoard/archive/main.zip
   ```
4. Click **Install** and restart OctoPrint

For development:

```bash
git clone https://github.com/schwarztim/OctoPrint-BambuBoard.git
cd OctoPrint-BambuBoard
pip install -e .
```

## Configuration

1. Open OctoPrint Settings
2. Navigate to **BambuBoard** under Plugins
3. Click **Add Printer** and enter:
   - **Name** — friendly name for the printer
   - **Hostname / IP** — printer's local IP address
   - **Access Code** — 8-digit code from the printer's network settings screen
   - **Serial Number** — found on the printer or in Bambu Handy app
   - **MQTT Port** — defaults to 8883
4. Click **Test Connection** to verify
5. Save settings — printers auto-connect on startup

## Architecture

This plugin does **not** use OctoPrint's native serial printer connection. Instead, it manages independent MQTT connections to each Bambu printer via the [`bambu-printer-manager`](https://pypi.org/project/bambu-printer-manager/) library. It's a standalone dashboard embedded within OctoPrint's UI framework.

## License

[AGPLv3](LICENSE)
