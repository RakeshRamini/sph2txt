"""
sph2txt — On-demand transcription export.

Parses log files for transcription entries and exports them to
CSV or JSON in data/exports/.
"""

import csv
import glob
import json
import logging
import os
import re
from datetime import datetime

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")
_EXPORT_DIR = os.path.join(_PROJECT_ROOT, "data", "exports")

# Matches: 2026-05-18 07:30:06,019 [INFO] __main__: Raw transcription: 'text here'
_RE_TRANSCRIPTION = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\] __main__: Raw transcription: '(.*)'$"
)
# Matches: 2026-05-18 07:30:06,137 [INFO] __main__: Injected: text here
_RE_INJECTED = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[INFO\] __main__: Injected: (.+)$"
)


def _parse_log_file(path: str) -> list[dict]:
    """Parse a single log file and return transcription entries."""
    entries = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                m = _RE_TRANSCRIPTION.match(line)
                if m:
                    entries.append({
                        "timestamp": m.group(1),
                        "raw_text": m.group(2),
                        "injected_text": "",
                    })
                    continue
                m = _RE_INJECTED.match(line)
                if m and entries and not entries[-1]["injected_text"]:
                    # Attach injected text to the most recent raw transcription
                    entries[-1]["injected_text"] = m.group(2)
    except OSError as e:
        logger.warning("Could not read log file %s: %s", path, e)
    return entries


def parse_all_logs() -> list[dict]:
    """Parse all log files (current + rotated) and return transcription entries sorted by time."""
    log_files = sorted(glob.glob(os.path.join(_LOG_DIR, "sph2txt.log*")))
    all_entries = []
    for path in log_files:
        all_entries.extend(_parse_log_file(path))
    # Sort by timestamp
    all_entries.sort(key=lambda e: e["timestamp"])
    return all_entries


def export_csv(entries: list[dict] | None = None) -> str:
    """Export transcription history to a timestamped CSV file. Returns the file path."""
    if entries is None:
        entries = parse_all_logs()
    os.makedirs(_EXPORT_DIR, exist_ok=True)
    filename = f"transcriptions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(_EXPORT_DIR, filename)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "raw_text", "injected_text"])
        writer.writeheader()
        writer.writerows(entries)
    logger.info("Exported %d transcriptions to %s", len(entries), filepath)
    return filepath


def export_json(entries: list[dict] | None = None) -> str:
    """Export transcription history to a timestamped JSON file. Returns the file path."""
    if entries is None:
        entries = parse_all_logs()
    os.makedirs(_EXPORT_DIR, exist_ok=True)
    filename = f"transcriptions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(_EXPORT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    logger.info("Exported %d transcriptions to %s", len(entries), filepath)
    return filepath


def cleanup_old_logs(retention_days: int = 90) -> int:
    """Delete rotated log files older than retention_days. Returns count of files removed."""
    if retention_days <= 0:
        return 0
    cutoff = datetime.now().timestamp() - (retention_days * 86400)
    removed = 0
    # Only clean up rotated logs (sph2txt.log.1, .2, etc.), never the active log
    for path in glob.glob(os.path.join(_LOG_DIR, "sph2txt.log.[0-9]*")):
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
                logger.info("Removed old log: %s", os.path.basename(path))
        except OSError:
            pass
    return removed
