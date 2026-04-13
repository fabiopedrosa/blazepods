# 🟢 BlazePods

Simple PoC to play with BlazePods over BLE.

Connects to BlazePod devices, authenticates using the reverse-engineered protocol, and runs a tap reaction game.

## 📋 Requirements

- Windows (uses `winsound` for audio)
- Python 3.10+
- Bluetooth adapter
- One or more BlazePod devices

## 🚀 Setup

```bash
pip install -r requirements.txt
```

## 📂 Scripts

| Script | Description |
|---|---|
| `main.py` | 🎮 Tap reaction game — lights up all pods, times how fast you tap them all, repeats |
| `discover.py` | 🔍 Scan for nearby BLE devices and list their MAC addresses |
| `timer.py` | ⏱️ Stopwatch GUI (tkinter) that starts/stops on pod tap |
| `tests.py` | 🧪 One-shot BLE connection test — reads a single value from a pod |
| `buzz.py` | 🔊 Test audio playback |

## ⚙️ How it works

1. Scans for BlazePods via BLE advertisements
2. Authenticates each pod using a CRC32 checksum derived from the manufacturer-specific advertisement data
3. Lights up each pod a different color (with tap-to-turn-off)
4. Subscribes to tap notifications
5. Times how long it takes to tap all pods, then starts the next round

Auth protocol based on [sasodoma/blazepod-hacking](https://github.com/sasodoma/blazepod-hacking).

## ⚠️ Disclaimer

This project is not affiliated with, endorsed by, or supported by PLAY COYOTTA LTD or BlazePod. BlazePod® is a registered trademark of PLAY COYOTTA LTD. All trademarks, service marks, and company names mentioned are the property of their respective owners. This software is provided as-is, and the use of this software is at your own risk.
