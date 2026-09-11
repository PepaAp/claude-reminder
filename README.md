# Claude Reminder

Physical ESP32-C3 notification when Claude Code needs attention.

## Contents

- `setup.sh` / `setup.ps1` — check for `uv`, create the virtual environment, install dependencies, launch the wizard
- `setup.py` — interactive Textual wizard for Claude Code hook installation
- `notify.py` — finds the connected ESP32-C3 and sends a trigger byte over serial
- `board/` — PlatformIO project for the firmware (solenoid on GPIO 4)

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Claude Code
- ESP32-C3 connected over USB
- [PlatformIO Core](https://platformio.org/) for building or flashing firmware

## Setup

```bash
./setup.sh
```

```powershell
.\setup.ps1
```

The script checks for `uv`, runs `uv sync`, and opens an interactive terminal wizard.

The wizard shows hook status and offers these actions:

- Install hooks
- Remove hooks
- Test notification
- Quit

Hooks are written to `~/.claude/settings.json` without overwriting your other Claude settings. They call Python from `.venv` and run `notify.py` directly from this repository.

Installed events:

- `Notification` — matcher `permission_prompt|idle_prompt`
- `PermissionRequest` — empty matcher for immediate notification when Claude asks for permission

## Firmware

Build and flash from the PlatformIO project in `board/` (bootloader, partition table, and app):

```bash
cd board
pio run -t upload
pio device monitor
```

PlatformIO auto-detects the serial port (Linux/macOS `/dev/...`, Windows `COMx`). Override with `upload_port` / `monitor_port` in `board/platformio.ini` if needed.

Source is `board/src/main.cpp`. Do not flash a lone application `.bin` to offset `0x0` — that overwrites the bootloader.

## Hardware

The firmware uses GPIO 4 to control the solenoid. Use an appropriate driver circuit and external power supply; do not connect a solenoid directly to an ESP32 GPIO pin.
