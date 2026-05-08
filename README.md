# SPH2TXT — Local Speech-to-Text

A local, GPU-accelerated speech-to-text application that works system-wide.  
Press a hotkey, speak, and text appears at your cursor — in any app, any browser.  
Fully offline. No cloud. No API keys. No subscriptions.

---

## Requirements

- Windows 10/11
- Python 3.10+ ([python.org](https://www.python.org/downloads/) or Microsoft Store)
- NVIDIA GPU with 6+ GB VRAM (RTX 3060 or better)
- NVIDIA GPU driver installed (no separate CUDA toolkit needed)
- A working microphone
- ~6 GB free disk space (app + model)

---

## Installation

### One-Click Setup

Open PowerShell in the project folder and run:

```powershell
.\install.ps1
```

This will:
1. Create a Python virtual environment (`s2tenv/`)
2. Install all dependencies from `requirements.txt`
3. Create the `models/`, `data/`, `logs/` directories

### Manual Setup (if you prefer)

```powershell
cd c:\Users\reach\Documents\projects\sph2txt
python -m venv s2tenv
.\s2tenv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### First Run

```powershell
.\s2tenv\Scripts\Activate.ps1
python src\main.py
```

On the first launch, the Whisper model (~3 GB) downloads automatically into `models/huggingface/`. This happens once. All subsequent starts are instant (~3-5 seconds to load model into GPU).

---

## How to Use

### Basic Usage

1. **Click your cursor** where you want text to appear (any app, any browser)
2. **Press and hold** `Alt+X`
3. **Speak** naturally — full sentences with punctuation
4. **Release the key** — text appears at your cursor within 1-2 seconds

That's it. Works in Notepad, VS Code, Gmail, ChatGPT, Slack, Google Docs, Word — everywhere.

### Voice Commands

While speaking, you can say these to insert formatting:

| Say This | Inserts |
|----------|---------|
| "new line" | Line break |
| "new paragraph" | Double line break |
| "tab" | Tab character |

Example: *"Hello comma this is a test period new line Second line period"* →  
`Hello, this is a test.`  
`Second line.`

---

## Hotkey Configuration

The default hotkey is **Alt+X**. To change it:

### Step 1: Open `config.json` in any text editor

### Step 2: Edit the `"hotkey"` field

```json
"hotkey": ["alt", "x"]
```

### Available Key Names

| Modifier Keys | Regular Keys |
|---------------|-------------|
| `ctrl` | `space`, `a`-`z`, `0`-`9` |
| `shift` | `f1`-`f12` |
| `alt` | `enter`, `tab`, `backspace` |
| `cmd` (Windows key) | `insert`, `delete`, `home`, `end` |

### Examples

| Hotkey Combo | Config Value |
|-------------|-------------|
| Alt+X (default) | `["alt", "x"]` |
| Ctrl+Alt+R | `["ctrl", "alt", "r"]` |
| Ctrl+Shift+F9 | `["ctrl", "shift", "f9"]` |
| Alt+Space | `["alt", "space"]` |

### Step 3: Restart sph2txt for changes to take effect

> **Tip:** Choose a combo that doesn't conflict with your most-used apps. `Alt+X` is conflict-free and reachable with the left hand alone.

---

## Recording Modes

Edit `"mode"` in `config.json`:

| Mode | Config Value | How It Works |
|------|-------------|-------------|
| **Push-to-talk** (default) | `"push_to_talk"` | Hold hotkey to record, release to transcribe |
| **Toggle** | `"toggle"` | Press hotkey to start recording, press again to stop |

---

## System Tray Controls

When running, sph2txt shows a tray icon near the clock:

| Icon Color | Meaning |
|-----------|---------|
| 🟢 Green | Idle — ready to record |
| 🔴 Red | Recording — speak now |
| 🟡 Yellow | Processing — transcribing your speech |

### Right-Click Menu

| Option | What It Does |
|--------|-------------|
| **Pause** | Stops listening for hotkey. Model stays loaded in GPU memory |
| **Sleep** | Unloads model from GPU. Frees ~6 GB VRAM. Quick to resume |
| **Resume** | Returns to active state from Pause or Sleep |
| **Quit** | Fully shuts down. Frees all resources |

---

## Auto-Start on Windows Login

To have sph2txt launch automatically when you log in:

```powershell
.\install.ps1 -AddStartup
```

This creates a shortcut in your Windows Startup folder. The app runs silently in the background (no console window — uses `pythonw.exe`).

### Remove Auto-Start

```powershell
# Option 1: Delete the shortcut
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\sph2txt.lnk"

# Option 2: Run uninstall script (also stops the process)
.\uninstall.ps1
```

---

## Stopping the Application

### From System Tray
Right-click tray icon → **Quit**

### From PowerShell
```powershell
# Stop sph2txt process
Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object {
    try { $_.CommandLine -like "*sph2txt*" } catch { $false }
} | Stop-Process -Force
```

### Quick Kill (if tray is unresponsive)
```powershell
Stop-Process -Name pythonw -Force
```

---

## Configuration Reference

All settings are in `config.json`. Edit with any text editor. Restart the app after changes.

| Setting | Default | Options | Description |
|---------|---------|---------|-------------|
| `model` | `large-v3-turbo` | `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo` | Whisper model. Smaller = faster + less VRAM, larger = more accurate |
| `device` | `cuda` | `cuda`, `cpu` | Use GPU or CPU. CPU is much slower |
| `compute_type` | `float16` | `float16`, `int8`, `float32` | GPU precision. `float16` is best balance |
| `language` | `en` | Any ISO language code, or `auto` | Set your language or let Whisper auto-detect |
| `hotkey` | `["alt","x"]` | Any key combo | Global hotkey to trigger recording |
| `mode` | `push_to_talk` | `push_to_talk`, `toggle` | Hold-to-record or press-toggle |
| `beam_size` | `5` | `1`-`10` | Higher = more accurate but slower |
| `vad_filter` | `true` | `true`, `false` | Trim silence from audio |
| `injection_mode` | `clipboard` | `clipboard`, `keystroke` | How text is typed. Clipboard works everywhere |
| `restore_clipboard` | `true` | `true`, `false` | Restore clipboard after paste |

### Model Selection Guide

| Model | VRAM | Speed | When to Use |
|-------|------|-------|-------------|
| `tiny` | ~1 GB | Instant | Quick testing |
| `small` | ~2 GB | Real-time | Battery/low-VRAM mode |
| `medium` | ~5 GB | Real-time | Good balance on constrained GPUs |
| **`large-v3-turbo`** | **~6 GB** | **Real-time** | **Daily use (recommended)** |
| `large-v3` | ~10 GB | Near real-time | Maximum accuracy |

### Switching Language

Edit `config.json`:
```json
"language": "es"
```

Common codes: `en` (English), `es` (Spanish), `fr` (French), `de` (German), `hi` (Hindi), `ja` (Japanese), `zh` (Chinese), `auto` (auto-detect).

---

## Transcription History

When logging is enabled (default), all transcriptions are stored locally.

### Where Logs Are Stored
```
sph2txt\data\transcriptions.db    ← SQLite database
```

### What Gets Logged
- Timestamp
- Transcribed text
- Audio duration
- Target application (e.g., `chrome.exe`, `Code.exe`)
- Confidence score

### Disable Logging
Edit `config.json`:
```json
"logging": {
    "enabled": false
}
```

### Auto-Cleanup
By default, entries older than 90 days are automatically deleted on startup. Configure in `config.json`:
```json
"logging": {
    "retention_days": 90,
    "max_db_size_mb": 500
}
```

---

## Uninstall

### Step 1: Run Uninstall Script
```powershell
.\uninstall.ps1
```
This stops the running process and removes the startup shortcut.

### Step 2: Delete the Folder
```powershell
Remove-Item "c:\Users\reach\Documents\projects\sph2txt" -Recurse -Force
```

This removes **everything**: code, virtual environment, models, logs, and data.

### What Is NOT Affected
- Your system Python installation
- NVIDIA drivers
- Ollama and its models
- Any other applications

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Hotkey doesn't work** | Check for conflicts with other apps. Try a different combo in `config.json` |
| **No audio captured** | Check Windows Settings → Privacy → Microphone → ensure access is allowed |
| **Slow transcription** | Switch to `small` or `medium` model. Check GPU isn't overloaded (close other GPU apps) |
| **Text doesn't appear** | Some apps block paste. Try `"injection_mode": "keystroke"` in config |
| **Model download fails** | Check internet connection. The model needs to download once (~3 GB) |
| **CUDA error** | Update NVIDIA driver to latest. Run `nvidia-smi` to verify GPU is accessible |
| **App crashes on start** | Run `python src\main.py` (not `pythonw.exe`) to see error messages in the console |
| **High VRAM usage** | Switch to a smaller model. Use tray → Sleep to unload model when not needed |

---

## Folder Structure

```
sph2txt/
├── src/                    # Application code
├── models/huggingface/     # Whisper model (~3 GB, auto-downloaded)
├── data/                   # Transcription history (SQLite)
├── logs/                   # App logs (auto-rotated)
├── assets/                 # Tray icons
├── config.json             # ← Edit this to customize
├── requirements.txt        # Python dependencies
├── install.ps1             # Setup script
├── uninstall.ps1           # Teardown script
└── DESIGN.md               # Full architecture docs
```

Everything is self-contained. Delete this folder = clean uninstall (after running `uninstall.ps1` to remove the startup shortcut).

---

## Security & Privacy

- **100% offline** — no data leaves your machine, ever
- **No accounts, API keys, or cloud** — runs entirely on local hardware
- **Audio is never saved to disk** — processed in-memory, discarded after transcription
- **Transcription logs are local-only** — stored in `data/` folder, deletable at any time
- **Open-source dependencies** — fully auditable

See [DESIGN.md](DESIGN.md) for the full security architecture and design decisions.
