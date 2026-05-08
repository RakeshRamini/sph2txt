# SPH2TXT — Local Speech-to-Text Application

## Solution Design Document

---

## 1. System Assessment

| Component | Specification |
|-----------|--------------|
| CPU | Intel Core i9-14900HX (24 cores / 32 threads) |
| RAM | 32 GB |
| GPU | NVIDIA GeForce RTX 4080 Laptop (12 GB VRAM, Compute 8.9) |
| OS | Windows |
| Python | 3.13 |
| CUDA Compute | 8.9 (Ada Lovelace) |

**Verdict:** Your system is excellent for local STT. The RTX 4080 with 12 GB VRAM can run Whisper `large-v3` in real-time with room to spare. You can achieve sub-second latency with `medium` or `large` models.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    System Tray App                        │
│              (Always running, minimal footprint)          │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│  Hotkey      │ │  Audio       │ │  Text Injection  │
│  Listener    │ │  Capture     │ │  (Cursor Paste)  │
│  (global)    │ │  (mic stream)│ │                  │
└──────┬───────┘ └──────┬───────┘ └────────┬─────────┘
       │                 │                   ▲
       │    ┌────────────▼──────────┐        │
       └───►│   Whisper Inference   │────────┘
            │   (GPU-accelerated)   │
            │   + Text Post-Process │
            └───────────────────────┘
```

### Core Flow:
1. **User presses hotkey** (`Alt+X`) → recording starts
2. **Audio captured** from microphone in real-time
3. **User releases hotkey** (or presses again) → recording stops
4. **Whisper model** transcribes audio on GPU
5. **Post-processing** adds punctuation, formatting, capitalization
6. **Text injected** at current cursor position via simulated keystrokes

---

## 3. Recommended Model

### Primary: **Whisper `large-v3-turbo`** (via faster-whisper)

| Model | VRAM | Speed (RTX 4080) | Accuracy | Recommendation |
|-------|------|-------------------|----------|----------------|
| `tiny` | ~1 GB | instant | basic | testing only |
| `base` | ~1 GB | instant | decent | low-resource fallback |
| `small` | ~2 GB | real-time | good | fast daily use |
| `medium` | ~5 GB | real-time | very good | balanced |
| `large-v3` | ~10 GB | near real-time | excellent | best accuracy |
| **`large-v3-turbo`** | **~6 GB** | **real-time** | **excellent** | **RECOMMENDED** |

**Why `large-v3-turbo` via faster-whisper:**
- Pruned version of large-v3 (decoder reduced from 32 to 4 layers) — near-identical accuracy, 2-3x faster
- Only ~6 GB VRAM — fits comfortably in your 12 GB GPU
- `faster-whisper` uses CTranslate2 (INT8/FP16 quantization) for even more speed
- Produces punctuation, capitalization, and natural formatting out-of-the-box
- Supports 99 languages

### Alternative: **Distil-Whisper large-v3**
- Even faster (5-6x speedup over large-v3)
- Slightly less accurate on edge cases
- Good fallback if turbo doesn't meet latency needs

---

## 4. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| STT Engine | `faster-whisper` | CTranslate2-optimized Whisper inference |
| Audio Capture | `sounddevice` | Low-latency microphone access |
| Hotkey | `pynput` | Global keyboard hotkey listener |
| Text Injection | `pynput` + `pyperclip` | Clipboard paste (default) or keystroke typing |
| System Tray | `pystray` | Tray icon, status, settings |
| GPU Acceleration | CUDA + cuDNN (via CTranslate2) | Fast inference |
| Audio Format | `numpy` | Audio buffer management |
| Post-processing | Built-in Whisper + regex | Punctuation & formatting |

---

## 5. Required Installations

### Step 1: Create Python Virtual Environment
```powershell
cd c:\Users\reach\Documents\projects\sph2txt
python -m venv s2tenv
.\s2tenv\Scripts\Activate.ps1
```

### Step 2: Install CUDA Toolkit (if not present)
- Download CUDA 12.x from: https://developer.nvidia.com/cuda-downloads
- Or rely on bundled CUDA from `faster-whisper` (no separate install needed for inference)

### Step 3: Install Python Dependencies
```powershell
pip install faster-whisper sounddevice numpy pynput pystray Pillow pyperclip
```

### Step 4: (Optional) Install for VAD support
```powershell
pip install silero-vad webrtcvad
```

### One-liner:
```powershell
pip install faster-whisper sounddevice numpy pynput pystray Pillow pyperclip
```

---

## 6. Application Components

### 6.1 Hotkey Manager
- Registers global hotkey (`Alt+X` by default, configurable)
- Two modes:
  - **Push-to-talk**: Hold key to record, release to transcribe
  - **Toggle**: Press to start, press again to stop
- Uses `pynput` for cross-application global hotkey capture

### 6.2 Audio Capture Engine
- Captures from default microphone via `sounddevice`
- Streams 16kHz mono PCM (Whisper's native format)
- Buffers audio in memory (numpy array)
- Optional: Voice Activity Detection (VAD) to trim silence

### 6.3 Whisper Inference Engine
- Loads model once at startup, keeps in GPU memory
- Transcribes buffered audio on demand
- Configuration:
  - `beam_size=5` for accuracy
  - `language="en"` (or auto-detect)
  - `vad_filter=True` (silence trimming)
  - `condition_on_previous_text=True` (context-aware)

### 6.4 Text Post-Processor
- Whisper large-v3-turbo already provides:
  - Punctuation (periods, commas, question marks)
  - Capitalization
  - Number formatting
- Additional processing:
  - Trim leading/trailing whitespace
  - Handle voice commands ("new line" → `\n`, "period" → `.`)
  - Optional: sentence case correction

### 6.5 Text Injector
- **Default mode: Clipboard Paste** — copies text to clipboard, simulates `Ctrl+V`
  - Atomic paste — instant, no character-by-character lag
  - Works identically in browsers, rich text editors, and local apps
  - Saves/restores previous clipboard contents automatically
- **Fallback mode: Keystroke simulation** via `pynput` (configurable)
  - Character-by-character typing, useful for apps that block paste
- Works in any application: browser text fields, Gmail, ChatGPT, Google Docs, Slack, VS Code, Notepad, etc.

### 6.6 System Tray Interface
- Shows recording status (idle / recording / processing)
- Right-click menu: Settings, Model selection, Quit
- Visual indicator: icon color changes during recording
- Notification on transcription complete (optional)

---

## 7. Browser & App Compatibility Matrix

| Application | Clipboard Paste (Default) | Keystroke Mode | Notes |
|-------------|--------------------------|----------------|-------|
| **Notepad / WordPad** | ✅ Perfect | ✅ Perfect | Zero issues |
| **VS Code / IDEs** | ✅ Perfect | ✅ Perfect | Zero issues |
| **Microsoft Word / Excel** | ✅ Perfect | ✅ Works | Clipboard preserves formatting context |
| **Google Search** | ✅ Perfect | ✅ Perfect | Both modes seamless |
| **Gmail compose** | ✅ Perfect | ⚠️ Rich editor quirks | Clipboard mode avoids formatting issues |
| **ChatGPT / Claude** | ✅ Perfect | ⚠️ Slow on long text | Clipboard is instant, keystroke lags |
| **Slack (web & desktop)** | ✅ Perfect | ⚠️ `/` triggers commands | Clipboard avoids slash-command triggers |
| **Microsoft Teams** | ✅ Perfect | ⚠️ `@` triggers mentions | Clipboard pastes cleanly |
| **Google Docs** | ✅ Perfect | ⚠️ Collab cursor issues | Clipboard is the only reliable way |
| **Notion / Confluence** | ✅ Perfect | ⚠️ Block-level interception | Clipboard works natively |
| **Terminal / PowerShell** | ✅ Perfect | ✅ Perfect | Both work; clipboard avoids escape-char issues |
| **Twitter/X, Reddit, etc.** | ✅ Perfect | ✅ Works | No issues |

**Summary:** Clipboard paste mode is expected to work seamlessly across all these scenarios — local apps and web browsers should behave identically. This is why it's the default. (Note: This matrix is based on how these apps handle standard `Ctrl+V` paste events; actual testing will validate during development.)

### How Clipboard Injection Works:

```
1. Save current clipboard TEXT contents (note: non-text clipboard data like images cannot be preserved)
2. Copy transcribed text to clipboard
3. Simulate Ctrl+V (paste into focused field)
4. Wait 200-500ms for paste to complete (adaptive, longer for heavy apps)
5. Restore original clipboard text contents
```

The user experience is identical whether you're typing in Notepad or composing a Gmail — press hotkey, speak, text appears. No difference.

---

## 8. User Experience Flow

```
IDLE STATE
    │
    ▼  User presses Alt+X
RECORDING ──── (tray icon turns red, subtle audio beep)
    │
    ▼  User releases key / presses again
PROCESSING ─── (tray icon turns yellow, ~0.5-2s)
    │
    ▼  Text appears at cursor
IDLE STATE ──── (tray icon turns green)
```

**Latency Target:** < 2 seconds from end of speech to text appearing  
**Actual Expected:** ~0.5-1.5s for typical sentences on your hardware

---

## 9. Project Structure

```
sph2txt/
├── s2tenv/                  # Virtual environment
├── src/
│   ├── __init__.py
│   ├── main.py             # Entry point, orchestrator
│   ├── hotkey.py           # Global hotkey listener
│   ├── audio.py            # Microphone capture
│   ├── transcriber.py      # Whisper inference engine
│   ├── injector.py         # Text injection at cursor
│   ├── postprocess.py      # Text cleanup & formatting
│   ├── tray.py             # System tray UI
│   └── config.py           # Settings management
├── assets/
│   ├── icon_idle.png
│   ├── icon_recording.png
│   └── icon_processing.png
├── config.json             # User settings
├── requirements.txt
├── DESIGN.md               # This file
└── README.md
```

---

## 10. Configuration (config.json)

```json
{
  "model": "large-v3-turbo",
  "device": "cuda",
  "compute_type": "float16",
  "language": "en",
  "hotkey": ["alt", "x"],
  "mode": "push_to_talk",
  "beam_size": 5,
  "vad_filter": true,
  "injection_mode": "clipboard",
  "typing_speed": 0.01,
  "restore_clipboard": true,
  "voice_commands": {
    "new line": "\n",
    "new paragraph": "\n\n",
    "tab": "\t"
  }
}
```

---

## 11. Performance Characteristics

| Metric | Expected on Your System |
|--------|------------------------|
| Model load time | ~3-5s (first launch, cached after) |
| Transcription latency (10s audio) | ~0.8-1.5s |
| Transcription latency (30s audio) | ~2-4s |
| VRAM usage (idle, model loaded) | ~6 GB |
| RAM usage | ~500 MB |
| CPU usage (idle) | < 1% |
| Accuracy (English) | ~2-5% WER (i.e. ~95-98% of words correct) |

---

## 12. Comparison with WhisperFlow

| Feature | WhisperFlow | SPH2TXT (This Design) |
|---------|-------------|----------------------|
| Global hotkey | ✓ | ✓ |
| Push-to-talk | ✓ | ✓ |
| Any app text injection | ✓ | ✓ |
| Local/offline | ✓ | ✓ |
| GPU acceleration | ✓ | ✓ |
| Auto punctuation | ✓ | ✓ (native Whisper) |
| System tray | ✓ | ✓ |
| Voice commands | Limited | ✓ (configurable) |
| Model selection | Fixed | ✓ (switchable) |
| Open source | Partial | ✓ (fully open) |
| Lean footprint | Medium | ✓ (single process) |

---

## 13. Advanced Features (Phase 2)

- **Streaming transcription**: Show partial results as user speaks
- **Multi-language auto-detect**: Switch languages on the fly
- **Custom vocabulary**: Bias toward domain-specific words
- **Audio feedback**: Subtle beep on record start/stop
- **Noise suppression**: Pre-process audio with RNNoise

---

## 14. Quick Start Commands

```powershell
# Setup (one-time)
cd c:\Users\reach\Documents\projects\sph2txt
python -m venv s2tenv
.\s2tenv\Scripts\Activate.ps1
pip install faster-whisper sounddevice numpy pynput pystray Pillow pyperclip

# Run
python src/main.py
```

---

## 15. Why This Stack?

| Decision | Reasoning |
|----------|-----------|
| `faster-whisper` over OpenAI `whisper` | 4x faster, 2x less memory, same accuracy |
| `large-v3-turbo` over `large-v3` | Same quality, 2-3x faster, fits in 6GB VRAM |
| `pynput` over `keyboard` lib | More reliable cross-app, no admin needed |
| `sounddevice` over `pyaudio` | Easier install on Windows, lower latency |
| Single-process design | Lean, no IPC overhead, simpler debugging |
| Python | Rich ML ecosystem, fast prototyping, all libs available |

---

## 16. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Hotkey conflicts with other apps | Make hotkey fully configurable |
| Text injection fails in some apps | Fallback to clipboard paste (`Ctrl+V`) |
| Model takes too long to load | Keep model resident in memory (daemon mode) |
| Microphone permissions | Guide user through Windows privacy settings |
| CUDA version mismatch | `faster-whisper` bundles its own CUDA runtime |

---

## 17. Design Clarifications & Deep Dive

### Q1: Compute Impact — Active Use vs Idle

**When IDLE (model loaded, waiting for hotkey):**

| Resource | Usage | Impact on Your Work |
|----------|-------|---------------------|
| VRAM | ~6 GB occupied (of 12 GB) | 6 GB free for other GPU tasks. Browser, VS Code, light gaming unaffected. Heavy CUDA workloads (training, rendering) will share the remaining 6 GB |
| RAM | ~300-500 MB | Negligible — you have 32 GB |
| CPU | < 0.5% | Hotkey listener + tray icon = virtually zero |
| Disk I/O | None | Zero |
| Power draw | ~5-10W extra GPU idle | Barely measurable on a laptop |

**When ACTIVELY TRANSCRIBING (1-5 seconds burst):**

| Resource | Usage | Impact |
|----------|-------|--------|
| VRAM | ~6-8 GB peak | Spikes briefly, returns to 6 GB |
| GPU Utilization | 80-100% | For 1-3 seconds only — you won't notice |
| CPU | 5-15% (one core) | Audio preprocessing — trivial |
| RAM | ~500-700 MB peak | No impact |

**Verdict:** This will NOT interfere with your normal laptop work. The idle footprint is comparable to having a browser tab with a video paused. The GPU burst during transcription is shorter than a game loading a texture. You can code, browse, run Docker containers, and do everything normally. The only scenario where you'd notice contention is if you're running another heavy CUDA workload simultaneously (e.g., ML training, video encoding) — in that case, you can switch to the `small` model (~2 GB VRAM) via config.

**Unload option:** The design includes a tray menu "Unload Model" option to free VRAM entirely when you need full GPU for other tasks, and "Reload Model" when you're ready again.

---

### Q2: Security Framework

**This is a 100% local, offline application. No data ever leaves your machine.**

#### Security Architecture:

```
┌──────────────────────────────────────────────────────────────┐
│                    YOUR LAPTOP (Trust Boundary)               │
│                                                                │
│  ┌─────────────┐    In-Memory     ┌──────────────────┐       │
│  │ Microphone   │───(PCM audio)──►│  Whisper Engine   │       │
│  │ (OS-managed) │    buffer only   │  (GPU, in-proc)  │       │
│  └─────────────┘                   └────────┬─────────┘       │
│                                              │                 │
│                                     (text string)              │
│                                              │                 │
│  ┌─────────────┐                   ┌────────▼─────────┐       │
│  │ Target App   │◄──(keystrokes)──│  Text Injector    │       │
│  │ (any window) │                  │  (pynput)         │       │
│  └─────────────┘                   └──────────────────┘       │
│                                                                │
│  ┌──────────────────────────────────────────────────┐         │
│  │          Local Log Store (optional)               │         │
│  │   c:\Users\reach\Documents\projects\sph2txt\data\ │         │
│  │   (SQLite, filesystem-permissioned)               │         │
│  └──────────────────────────────────────────────────┘         │
│                                                                │
│   ✗ No network sockets opened                                 │
│   ✗ No API calls                                              │
│   ✗ No telemetry                                              │
│   ✗ No cloud dependencies                                    │
│   ✗ No data exfiltration possible                             │
└──────────────────────────────────────────────────────────────┘
```

#### Security Properties:

| Concern | Status | Detail |
|---------|--------|--------|
| **Network access** | NONE | App opens zero network connections. Can be verified by firewall rules blocking the process entirely |
| **Audio storage** | IN-MEMORY ONLY | Raw audio lives in a numpy buffer, discarded after transcription. Never written to disk unless logging is explicitly enabled |
| **Model source** | One-time download from HuggingFace | Downloaded once, cached locally at `~/.cache/huggingface/`. Verified via checksums. No further network needed |
| **Data at rest** | Optional, local-only | Transcription logs (if enabled) are stored in a local SQLite DB in the project folder. Protected by Windows file system ACLs |
| **Keystroke injection** | Scoped | `pynput` has both Listener (reads) and Controller (writes) capabilities. The app uses Listener ONLY for detecting the configured hotkey combo — it does not log, store, or transmit any keystrokes. Controller is used only to paste transcribed text. No keylogging behavior |
| **Process isolation** | Single process, user-level | Runs under your user account with no elevated privileges. No admin/root required |
| **Dependencies** | Auditable open-source | All packages (`faster-whisper`, `pynput`, `sounddevice`, etc.) are open-source, pip-installable, and auditable |

#### Hardening Recommendations:

1. **Firewall rule:** Add a Windows Firewall outbound block rule for `python.exe` in the `s2tenv` — guarantees zero network egress
2. **Folder ACLs:** Restrict `sph2txt\data\` to your user account only
3. **Virtual environment isolation:** All dependencies are in `s2tenv`, isolated from your system Python
4. **No secrets/keys:** The app stores no credentials, tokens, or secrets of any kind

**Bottom line:** This is as secure as a local application can be. It's an air-gapped design — even if you disconnect from the internet, it works identically.

---

### Q3: Transcription History & Usage Logging

**Yes — this is a configurable feature.** The design includes an optional logging system:

#### What Gets Logged (when enabled):

| Field | Example |
|-------|---------|
| Timestamp | `2026-05-08T14:32:15` |
| Transcribed text | `"Meeting notes: discussed Q3 roadmap..."` |
| Duration of audio | `4.2 seconds` |
| Target application | `chrome.exe` / `Code.exe` / `notepad.exe` |
| Window title (optional) | `"Slack - General"` |
| Confidence score | `0.94` |

#### Storage Design:

```
sph2txt/
└── data/
    ├── transcriptions.db    # SQLite database (single file)
    └── exports/             # On-demand CSV/JSON exports
```

#### Configuration (config.json additions):

```json
{
  "logging": {
    "enabled": true,
    "store_path": "c:\\Users\\reach\\Documents\\projects\\sph2txt\\data",
    "log_target_app": true,
    "log_window_title": false,
    "retention_days": 90,
    "max_db_size_mb": 500
  }
}
```

#### Features:
- **Search history:** Query past transcriptions by date, keyword, or target app
- **Export:** Export to CSV/JSON for review
- **Dashboard (Phase 2):** Simple local web UI to browse history
- **Privacy toggle:** Disable logging entirely with one config change. When disabled, zero data is persisted

---

### Q4: Space Constraints & Auto-Cleanup

#### Current Disk Assessment:

| Item | Size |
|------|------|
| Your free disk space | **~1,461 GB free** — more than enough |
| Whisper large-v3-turbo model | ~3 GB (one-time download, cached) |
| Application code | < 1 MB |
| Python venv + dependencies | ~2-3 GB |
| **Total app footprint** | **~5-6 GB** |

#### Transcription Log Space Estimate:

| Usage Pattern | Daily Log Size | Monthly | Yearly |
|---------------|---------------|---------|--------|
| Light (20 transcriptions/day) | ~50 KB | ~1.5 MB | ~18 MB |
| Moderate (100/day) | ~250 KB | ~7.5 MB | ~90 MB |
| Heavy (500/day) | ~1.2 MB | ~36 MB | ~432 MB |

**Even at heavy usage, it would take years to reach 1 GB of logs.**

#### Auto-Cleanup System:

```python
# Built into the application — runs on every startup
# Configurable in config.json

{
  "storage": {
    "data_root": "c:\\Users\\reach\\Documents\\projects\\sph2txt\\data",
    "retention_days": 90,
    "max_db_size_mb": 500,
    "auto_cleanup": true,
    "cleanup_on_startup": true
  }
}
```

#### Confinement Strategy:

All application data is strictly confined to one folder tree:

```
c:\Users\reach\Documents\projects\sph2txt\
├── src/            # Code (read-only at runtime)
├── data/           # ALL mutable data lives here
│   ├── transcriptions.db
│   ├── exports/
│   └── cache/
├── config.json     # Settings
└── logs/           # Application logs (auto-rotated)
```

- **Model cache** can also be redirected into this tree via `HF_HOME` env var (default: `~/.cache/huggingface/`)
- **No writes outside this folder** — the app has no reason to touch anything else
- Auto-purge deletes entries older than `retention_days` (default: 90 days)
- DB size cap: if `transcriptions.db` exceeds `max_db_size_mb`, oldest entries are pruned first
- Log rotation: application logs auto-rotate at 10 MB, keep last 3 files

---

### Q5: Dockerization

#### Current Status: Not dockerized (and **not recommended** as the primary approach)

#### Why Docker is problematic for this app:

| Challenge | Detail |
|-----------|--------|
| **GPU passthrough** | Requires NVIDIA Container Toolkit + WSL2 GPU support. Works but adds complexity and slight latency |
| **Microphone access** | Docker containers can't directly access Windows audio devices. Requires PulseAudio forwarding or host-side audio capture with socket IPC |
| **Global hotkey** | Containers can't capture host keyboard events. Must run hotkey listener on host |
| **Keystroke injection** | Container can't send keystrokes to host applications. Must bridge back to host |
| **System tray** | No GUI from container — tray must run on host |

**The fundamental problem:** This app's core features (hotkey capture, mic access, keystroke injection, tray icon) all require direct host OS interaction — exactly what Docker abstracts away.

#### If You Still Want Docker (Hybrid Approach):

You could dockerize only the inference engine:

```
┌─ HOST ──────────────────────────────┐
│  Hotkey Listener                     │
│  Audio Capture                       │
│  Text Injector                       │
│  System Tray                         │
│         │ (gRPC/WebSocket)           │
│         ▼                            │
│  ┌─ DOCKER CONTAINER ─────────────┐ │
│  │  Whisper Inference Server       │ │
│  │  (GPU passthrough via NVIDIA)   │ │
│  └─────────────────────────────────┘ │
└──────────────────────────────────────┘
```

#### Docker Requirements (if pursued):
- Docker Desktop 28.3.0 ✓ (you have this)
- NVIDIA Container Toolkit (install needed)
- WSL2 with GPU support enabled
- `nvidia/cuda` base image
- ~8-10 GB Docker image size

#### Recommendation:

**Skip Docker for v1.** Run natively — it's simpler, faster, and more reliable. The app is already isolated in a Python virtual environment. Docker adds complexity without meaningful benefit for a single-user local tool. If portability becomes important later, dockerize the inference engine only (Phase 2).

---

### Q6: Startup & On/Off Control

#### Auto-Start on Windows Boot:

Three options (from simplest to most robust):

**Option A — Startup Folder Shortcut (Recommended):**
```powershell
# Creates a shortcut that auto-launches sph2txt on login
$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\sph2txt.lnk")
$shortcut.TargetPath = "c:\Users\reach\Documents\projects\sph2txt\s2tenv\Scripts\pythonw.exe"
$shortcut.Arguments = "c:\Users\reach\Documents\projects\sph2txt\src\main.py"
$shortcut.WorkingDirectory = "c:\Users\reach\Documents\projects\sph2txt"
$shortcut.WindowStyle = 7  # Minimized
$shortcut.Save()
```

**Option B — Windows Task Scheduler:**
```powershell
# Runs at logon, with delay to let other services start
$action = New-ScheduledTaskAction -Execute "s2tenv\Scripts\pythonw.exe" -Argument "src\main.py" -WorkingDirectory "c:\Users\reach\Documents\projects\sph2txt"
$trigger = New-ScheduledTaskTrigger -AtLogon -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "sph2txt" -Action $action -Trigger $trigger -Settings $settings
```

**Option C — Windows Service (via NSSM):**
- For always-on daemon behavior, even before user login
- Overkill for this use case

#### On/Off Controls:

| Action | How |
|--------|-----|
| **Pause (keep model loaded)** | Right-click tray icon → "Pause" (ignores hotkey, keeps VRAM) |
| **Sleep (unload model)** | Right-click tray icon → "Sleep" (frees VRAM, quick reload) |
| **Quit entirely** | Right-click tray icon → "Quit" (full shutdown, frees everything) |
| **Quick toggle** | Assign a secondary hotkey (e.g., `Ctrl+Shift+F1`) to pause/resume |
| **Disable auto-start** | Delete the startup shortcut or disable the scheduled task |

The app uses `pythonw.exe` (not `python.exe`) so no console window appears — it runs silently in the background with only the tray icon visible.

---

### Q7: Overhead & Long-Term Costs

#### Financial Cost: **$0**

| Item | Cost |
|------|------|
| Whisper model | Free (MIT license, open-source) |
| faster-whisper | Free (open-source) |
| All Python packages | Free (open-source) |
| Cloud API fees | None — fully local |
| Subscription | None |
| Ongoing fees | None |

#### System Overhead Over Time:

| Concern | Reality |
|---------|---------|
| **VRAM wear** | GPUs are designed for sustained load. Idle model-in-memory is zero wear |
| **SSD writes** | Minimal — only log entries. Far less than browser cache |
| **Model updates** | Optional. New Whisper versions release ~yearly. Download new model (~3 GB), delete old one |
| **Dependency rot** | Pin versions in `requirements.txt`. Update annually or when needed |
| **DB growth** | Auto-cleanup at 90 days keeps it bounded. Even without cleanup, years to reach 1 GB |
| **Memory leaks** | `faster-whisper` (CTranslate2) is C++-backed, stable. Rare leaks restart via tray "Restart" |
| **Windows updates** | Python venv and CUDA are self-contained. Windows updates won't break it |

#### Battery Impact (Laptop):

| State | Battery Impact |
|-------|---------------|
| Idle (model loaded) | ~5-10 min less battery life per full charge (~2-3% impact) |
| Idle (model unloaded / sleep mode) | Negligible — < 1% impact |
| Active transcription | Brief GPU spike, equivalent to watching a 4K video for 2 seconds |

**Recommendation:** Use "Sleep" mode when on battery to free GPU power. Switch to the `small` model on battery for minimal power draw.

---

## 18. Overall Fitness Assessment

### Does it fit with your daily laptop use?

| Your Activity | Compatibility | Notes |
|---------------|--------------|-------|
| **VS Code / coding** | ✅ Excellent | Zero conflict. 6 GB VRAM free for VS Code Copilot, extensions |
| **Web browsing** | ✅ Excellent | Browsers use minimal GPU. No contention |
| **Docker containers** | ✅ Good | CPU containers unaffected. GPU containers share 6 GB remaining VRAM |
| **Video calls (Teams/Zoom)** | ✅ Excellent | Video encoding uses different GPU silicon (NVENC) |
| **Light gaming** | ✅ Good | Most games work fine with 6 GB free VRAM. AAA titles at max settings may compete |
| **ML training / notebooks** | ⚠️ Moderate | Use "Sleep" mode to free VRAM, or switch to `small` model |
| **Video editing** | ⚠️ Moderate | NVENC unaffected, but GPU rendering may compete |

### Is it secure enough?

**Yes — this is one of the most secure STT setups possible:**

- ✅ **Zero network exposure** — no ports, no APIs, no cloud
- ✅ **Zero data exfiltration risk** — nothing leaves the machine
- ✅ **No credentials stored** — no API keys, no tokens
- ✅ **User-level process** — no admin privileges, no system-wide hooks
- ✅ **Auditable open-source stack** — every component inspectable
- ✅ **File-system confined** — all data in one known folder
- ✅ **Air-gap compatible** — works identically without internet

The only attack surface is physical access to your laptop (which applies to everything on your machine, not specific to this app). Enabling full-disk encryption (BitLocker) covers that.

**Compared to cloud STT services (Google, Azure, AWS, OpenAI API):** Your data stays on your laptop instead of being sent to third-party servers. This is objectively more private and secure.

---

## 19. Existing AI Tools Audit & What's Needed

### What You Already Have Installed:

| Tool | Version | Location | Size | Used by sph2txt? |
|------|---------|----------|------|-------------------|
| **Ollama** | 0.9.6 | `C:\Users\reach\AppData\Local\Programs\Ollama\` | ~200 MB binary | **NO** — Ollama is an LLM runner (text generation), not a speech-to-text engine |
| Ollama model: `gemma3` | latest | `C:\Users\reach\.ollama\models\` | ~3.1 GB | **NO** |
| **HuggingFace cache** | — | `C:\Users\reach\.cache\huggingface\hub\` | ~7.2 GB | **YES** — Whisper model will be cached here |
| HF model: `Phi-3-mini-4k-instruct` | — | `~\.cache\huggingface\hub\` | ~3.8 GB | **NO** — this is an LLM, not STT |
| HF model: `all-MiniLM-L6-v2` | — | `~\.cache\huggingface\hub\` | ~90 MB | **NO** — this is an embedding model |
| **Python** | 3.13 | `C:\Users\reach\AppData\Local\Microsoft\WindowsApps\` | system install | **YES** — runtime |
| **pip** | 26.0.1 | same as Python | bundled | **YES** — package installer |
| **Docker** | 28.3.0 | system install | — | **NO** — not needed for v1 |
| **NVIDIA Driver** | 32.0.15.7700 | system install | — | **YES** — GPU access |
| **CUDA Toolkit (standalone)** | NOT INSTALLED | — | — | **NOT NEEDED** — `faster-whisper` bundles its own CUDA runtime |

### Key Insight: Ollama ≠ Speech-to-Text

Ollama runs **large language models** (text-in → text-out). It cannot:
- Capture audio from your microphone
- Transcribe speech to text
- Replace Whisper in any way

Ollama + Gemma3 are useful for other tasks (chat, code generation, summarization), but they play **no role** in sph2txt. They can coexist peacefully — different tools, different purposes.

### What You Still Need (sph2txt-specific):

| Component | Status | Action Required |
|-----------|--------|-----------------|
| Python 3.13 | ✅ Installed | None |
| NVIDIA GPU Driver | ✅ Installed | None |
| Python venv for sph2txt | ❌ Not created | `python -m venv s2tenv` (one-time) |
| `faster-whisper` | ❌ Not installed | `pip install faster-whisper` |
| `sounddevice` | ❌ Not installed | `pip install sounddevice` |
| `pynput` | ❌ Not installed | `pip install pynput` |
| `pystray` + `Pillow` | ❌ Not installed | `pip install pystray Pillow` |
| `pyperclip` | ❌ Not installed | `pip install pyperclip` |
| `numpy` | ❌ Not installed | `pip install numpy` |
| Whisper large-v3-turbo model | ❌ Not downloaded | Auto-downloads on first run (~3 GB, one-time) |
| CUDA Toolkit (standalone) | ❌ Not installed | **NOT NEEDED** — `faster-whisper` bundles CTranslate2 with CUDA |

### VRAM Coexistence with Ollama:

| Scenario | VRAM Usage |
|----------|-----------|
| Only sph2txt running | ~6 GB (Whisper model) |
| Only Ollama + Gemma3 running | ~5-6 GB |
| Both running simultaneously | ~11-12 GB ⚠️ (tight on 12 GB VRAM) |

**Recommendation:** Don't run Ollama with a loaded model and sph2txt simultaneously. Ollama unloads models after idle timeout (default 5 min), so in practice they rarely compete. If you need both, use `sph2txt` with the `small` model (~2 GB VRAM).

---

## 20. Self-Contained Directory — "Delete Folder = Full Uninstall"

### The Problem with Default Locations:

Currently, your AI tools scatter files across your system:

```
C:\Users\reach\
├── .ollama\models\                    ← 3.1 GB (Ollama models)
├── .cache\huggingface\hub\            ← 7.2 GB (HuggingFace models)
├── AppData\Local\Programs\Ollama\     ← Ollama binary
└── Documents\projects\sph2txt\        ← Your project
```

If you delete `sph2txt\`, the Whisper model (~3 GB) would remain orphaned in `~\.cache\huggingface\`.

### The Solution: Redirect Everything Into the Project Folder

Set environment variables so all caches live inside `sph2txt\`:

```
c:\Users\reach\Documents\projects\sph2txt\
├── src/                    # Application code
├── s2tenv/                  # Python virtual environment (~2-3 GB)
├── models/                 # Whisper model cache (~3 GB) ← redirected here
│   └── huggingface/
│       └── hub/
│           └── models--Systran--faster-whisper-large-v3-turbo/
├── data/                   # Transcription logs, SQLite DB
│   ├── transcriptions.db
│   └── exports/
├── logs/                   # App logs (auto-rotated)
├── assets/                 # Tray icons
├── config.json             # All settings
├── requirements.txt        # Pinned dependencies
├── install.ps1             # One-click setup script
├── uninstall.ps1           # One-click removal script
└── DESIGN.md               # This document
```

### How to Redirect the Model Cache:

In the application startup code and in `config.json`:

```json
{
  "paths": {
    "model_cache": "c:\\Users\\reach\\Documents\\projects\\sph2txt\\models\\huggingface",
    "data_root": "c:\\Users\\reach\\Documents\\projects\\sph2txt\\data",
    "log_dir": "c:\\Users\\reach\\Documents\\projects\\sph2txt\\logs"
  }
}
```

In Python, before loading the model:
```python
import os
os.environ["HF_HOME"] = os.path.join(os.path.dirname(__file__), "..", "models", "huggingface")
```

The `faster-whisper` `WhisperModel()` constructor also accepts a `download_root` parameter:
```python
model = WhisperModel("large-v3-turbo", download_root="./models/huggingface")
```

### What "Delete This Folder" Covers:

| Item | Inside sph2txt\ ? | Cleaned up? |
|------|-------------------|-------------|
| Application code | ✅ Yes | ✅ Deleted |
| Python venv + all packages | ✅ Yes (s2tenv/) | ✅ Deleted |
| Whisper model weights | ✅ Yes (models/) | ✅ Deleted |
| Transcription history | ✅ Yes (data/) | ✅ Deleted |
| Application logs | ✅ Yes (logs/) | ✅ Deleted |
| Config & settings | ✅ Yes (config.json) | ✅ Deleted |
| Startup shortcut | ❌ No (AppData\Startup\) | ⚠️ Must remove separately |
| Python (system) | ❌ No (WindowsApps\) | Shared, don't delete |
| NVIDIA drivers | ❌ No (system) | Shared, don't delete |

**Only one thing lives outside:** the Windows startup shortcut (if created). The uninstall script handles that.

### What About Your Existing HuggingFace Cache?

Your existing `~\.cache\huggingface\hub\` (7.2 GB) contains `Phi-3-mini-4k-instruct` and `all-MiniLM-L6-v2` — these are **not related to sph2txt**. They belong to other projects. The sph2txt app will use its own local `models/` folder and will NOT touch your existing HF cache.

---

## 21. Pause & Uninstall Procedures

### Pause / Temporarily Disable:

#### Option 1: From System Tray (While Running)
```
Right-click tray icon → "Pause"     ← Stops listening, keeps model in VRAM
Right-click tray icon → "Sleep"     ← Stops listening, unloads model, frees VRAM
Right-click tray icon → "Resume"    ← Back to active
```

#### Option 2: Kill the Process
```powershell
# Find and stop sph2txt
Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*sph2txt*"
} | Stop-Process -Force

# Or simpler — stop all pythonw (only if sph2txt is your only pythonw app)
Stop-Process -Name pythonw -Force -ErrorAction SilentlyContinue
```

#### Option 3: Disable Auto-Start (Prevent It From Starting on Boot)
```powershell
# Remove startup shortcut
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\sph2txt.lnk" -ErrorAction SilentlyContinue

# Or if using Task Scheduler
Unregister-ScheduledTask -TaskName "sph2txt" -Confirm:$false -ErrorAction SilentlyContinue
```

### Full Uninstall — One-Click Script:

Save this as `uninstall.ps1` in the project root:

```powershell
# sph2txt Uninstall Script
# Run from: c:\Users\reach\Documents\projects\sph2txt\

Write-Host "=== SPH2TXT Uninstaller ===" -ForegroundColor Yellow

# 1. Stop the running process
Write-Host "Stopping sph2txt process..." -ForegroundColor Cyan
Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object {
    try { $_.CommandLine -like "*sph2txt*" } catch { $false }
} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# 2. Remove startup shortcut
Write-Host "Removing startup shortcut..." -ForegroundColor Cyan
$startupLink = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\sph2txt.lnk"
if (Test-Path $startupLink) {
    Remove-Item $startupLink -Force
    Write-Host "  Removed: $startupLink" -ForegroundColor Green
} else {
    Write-Host "  No startup shortcut found" -ForegroundColor Gray
}

# 3. Remove scheduled task (if any)
Write-Host "Removing scheduled task..." -ForegroundColor Cyan
Unregister-ScheduledTask -TaskName "sph2txt" -Confirm:$false -ErrorAction SilentlyContinue

# 4. Summary
Write-Host ""
Write-Host "=== Uninstall Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Process stopped and auto-start removed." -ForegroundColor White
Write-Host ""
Write-Host "To fully remove all files, delete this folder:" -ForegroundColor Yellow
Write-Host "  c:\Users\reach\Documents\projects\sph2txt\" -ForegroundColor White
Write-Host ""
Write-Host "This will remove: code, venv, models (~5-6 GB), logs, and data." -ForegroundColor Gray
Write-Host "Your system Python, NVIDIA drivers, and Ollama are NOT affected." -ForegroundColor Gray
```

### Reinstall After Uninstall:

If you ever want it back:
```powershell
cd c:\Users\reach\Documents\projects\sph2txt
python -m venv s2tenv
.\s2tenv\Scripts\Activate.ps1
pip install faster-whisper sounddevice numpy pynput pystray Pillow pyperclip
python src/main.py   # Model auto-downloads on first run
```

---

*This design delivers a WhisperFlow-equivalent experience that is fully local, GPU-accelerated, secure, self-contained, and works system-wide on your hardware with negligible impact on daily use.*
