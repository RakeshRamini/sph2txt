"""
sph2txt — Settings UI (tkinter).

Minimalistic control panel:
  - View / update hotkey
  - View live logs
  - Activate / deactivate the transcription engine
  - Launches standalone or from the tray icon menu

No external dependencies beyond Python's built-in tkinter.
"""

import json
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config.json")
_LOG_PATH = os.path.join(_PROJECT_ROOT, "logs", "sph2txt.log")


class SettingsUI:
    """Main settings window."""

    def __init__(self, on_activate=None, on_deactivate=None,
                 initially_active=True):
        """
        Args:
            on_activate: callback when user clicks Activate (no args).
            on_deactivate: callback when user clicks Deactivate (no args).
            initially_active: whether the app is currently active.
        """
        self._on_activate = on_activate
        self._on_deactivate = on_deactivate
        self._active = initially_active
        self._log_tail_running = False
        self._log_position = 0
        self._root = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self):
        """Create and show the settings window (blocks on mainloop)."""
        self._root = tk.Tk()
        self._root.title("sph2txt — Settings")
        self._root.geometry("620x520")
        self._root.resizable(True, True)
        self._root.configure(bg="#1e1e1e")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background="#1e1e1e", foreground="#d4d4d4",
                        fieldbackground="#2d2d2d", font=("Segoe UI", 10))
        style.configure("TLabel", background="#1e1e1e", foreground="#d4d4d4")
        style.configure("TButton", background="#3c3c3c", foreground="#d4d4d4",
                        padding=6)
        style.map("TButton",
                  background=[("active", "#505050")])
        style.configure("TLabelframe", background="#1e1e1e",
                        foreground="#569cd6")
        style.configure("TLabelframe.Label", background="#1e1e1e",
                        foreground="#569cd6")
        style.configure("Active.TButton", background="#2d7d46",
                        foreground="#ffffff")
        style.configure("Inactive.TButton", background="#c24a4a",
                        foreground="#ffffff")

        self._build_hotkey_frame()
        self._build_status_frame()
        self._build_log_frame()

        # Set initial state appearance
        if self._active:
            self._status_var.set("Active")
            self._status_label.configure(foreground="#4ec9b0")

        # Start tailing logs
        self._log_tail_running = True
        self._tail_log()

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._root.mainloop()

    def show_nonblocking(self):
        """Launch UI in a background thread (for integration with tray)."""
        t = threading.Thread(target=self.show, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # UI Building
    # ------------------------------------------------------------------

    def _build_hotkey_frame(self):
        frame = ttk.LabelFrame(self._root, text="  Hotkey  ", padding=12)
        frame.pack(fill="x", padx=12, pady=(12, 6))

        row = ttk.Frame(frame)
        row.pack(fill="x")

        ttk.Label(row, text="Current hotkey:").pack(side="left")

        self._hotkey_var = tk.StringVar()
        self._load_hotkey()

        self._hotkey_label = ttk.Label(row, textvariable=self._hotkey_var,
                                       font=("Consolas", 12, "bold"),
                                       foreground="#4ec9b0")
        self._hotkey_label.pack(side="left", padx=(10, 20))

        self._change_btn = ttk.Button(row, text="Change Hotkey",
                                      command=self._start_hotkey_capture)
        self._change_btn.pack(side="right")

        # Hidden capture label
        self._capture_label = ttk.Label(frame,
                                        text="Press new key combination...",
                                        foreground="#ce9178",
                                        font=("Segoe UI", 9, "italic"))

    def _build_status_frame(self):
        frame = ttk.LabelFrame(self._root, text="  App Control  ", padding=12)
        frame.pack(fill="x", padx=12, pady=6)

        row = ttk.Frame(frame)
        row.pack(fill="x")

        ttk.Label(row, text="Status:").pack(side="left")

        self._status_var = tk.StringVar(value="Inactive")
        self._status_label = ttk.Label(row, textvariable=self._status_var,
                                       font=("Segoe UI", 10, "bold"),
                                       foreground="#ce9178")
        self._status_label.pack(side="left", padx=(10, 20))

        self._deactivate_btn = ttk.Button(row, text="Deactivate",
                                          command=self._deactivate,
                                          style="Inactive.TButton")
        self._deactivate_btn.pack(side="right", padx=(6, 0))

        self._activate_btn = ttk.Button(row, text="Activate",
                                        command=self._activate,
                                        style="Active.TButton")
        self._activate_btn.pack(side="right")

    def _build_log_frame(self):
        frame = ttk.LabelFrame(self._root, text="  Live Logs  ", padding=8)
        frame.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        self._log_text = tk.Text(frame, bg="#1a1a1a", fg="#cccccc",
                                 font=("Consolas", 9), wrap="word",
                                 state="disabled", borderwidth=0,
                                 highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scrollbar.set)

        self._log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Clear button
        btn_row = ttk.Frame(self._root)
        btn_row.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Button(btn_row, text="Clear Log View",
                   command=self._clear_log).pack(side="right")

    # ------------------------------------------------------------------
    # Hotkey Capture
    # ------------------------------------------------------------------

    def _load_hotkey(self):
        config = self._read_config()
        keys = config.get("hotkey", ["alt", "x"])
        self._hotkey_var.set(" + ".join(k.capitalize() for k in keys))

    def _start_hotkey_capture(self):
        self._capture_label.pack(fill="x", pady=(8, 0))
        self._change_btn.configure(state="disabled")
        self._captured_keys = set()
        self._root.bind("<KeyPress>", self._on_capture_key_down)
        self._root.bind("<KeyRelease>", self._on_capture_key_up)
        self._root.focus_set()

    def _on_capture_key_down(self, event):
        key = self._normalize_key(event)
        if key:
            self._captured_keys.add(key)
            self._capture_label.configure(
                text="Captured: " + " + ".join(
                    k.capitalize() for k in sorted(self._captured_keys)))

    def _on_capture_key_up(self, event):
        if not self._captured_keys:
            return
        # Save on first key release (entire combo captured)
        self._root.unbind("<KeyPress>")
        self._root.unbind("<KeyRelease>")
        self._capture_label.pack_forget()
        self._change_btn.configure(state="normal")

        new_hotkey = sorted(self._captured_keys)
        self._save_hotkey(new_hotkey)
        self._hotkey_var.set(" + ".join(k.capitalize() for k in new_hotkey))
        messagebox.showinfo("Hotkey Updated",
                            f"New hotkey: {' + '.join(k.capitalize() for k in new_hotkey)}\n\n"
                            "Restart the app for changes to take effect.")

    def _normalize_key(self, event):
        """Map tkinter keysym to pynput-compatible key name."""
        mapping = {
            "Control_L": "ctrl", "Control_R": "ctrl",
            "Alt_L": "alt", "Alt_R": "alt",
            "Shift_L": "shift", "Shift_R": "shift",
            "Super_L": "cmd", "Super_R": "cmd",
            "Escape": "esc", "Return": "enter",
            "space": "space", "Tab": "tab",
            "BackSpace": "backspace", "Delete": "delete",
        }
        keysym = event.keysym
        if keysym in mapping:
            return mapping[keysym]
        if len(keysym) == 1:
            return keysym.lower()
        # F-keys, etc.
        if keysym.startswith("F") and keysym[1:].isdigit():
            return keysym.lower()
        return keysym.lower()

    def _save_hotkey(self, keys):
        config = self._read_config()
        config["hotkey"] = keys
        self._write_config(config)

    # ------------------------------------------------------------------
    # Activate / Deactivate
    # ------------------------------------------------------------------

    def _activate(self):
        self._active = True
        self._status_var.set("Active")
        self._status_label.configure(foreground="#4ec9b0")
        if self._on_activate:
            self._on_activate()

    def _deactivate(self):
        self._active = False
        self._status_var.set("Inactive")
        self._status_label.configure(foreground="#ce9178")
        if self._on_deactivate:
            self._on_deactivate()

    # ------------------------------------------------------------------
    # Log Tailing
    # ------------------------------------------------------------------

    def _tail_log(self):
        if not self._log_tail_running:
            return
        try:
            if os.path.exists(_LOG_PATH):
                with open(_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(self._log_position)
                    new_content = f.read()
                    self._log_position = f.tell()
                if new_content:
                    self._log_text.configure(state="normal")
                    self._log_text.insert("end", new_content)
                    self._log_text.see("end")
                    self._log_text.configure(state="disabled")
        except Exception:
            pass
        # Poll every 1 second
        self._root.after(1000, self._tail_log)

    def _clear_log(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Config I/O
    # ------------------------------------------------------------------

    def _read_config(self):
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_config(self, config):
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _on_close(self):
        self._log_tail_running = False
        self._root.destroy()


# ------------------------------------------------------------------
# Standalone launcher
# ------------------------------------------------------------------

def launch_ui(on_activate=None, on_deactivate=None):
    """Convenience function to launch the UI."""
    ui = SettingsUI(on_activate=on_activate, on_deactivate=on_deactivate)
    ui.show()


if __name__ == "__main__":
    launch_ui()
