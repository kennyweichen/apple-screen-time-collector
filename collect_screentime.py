#!/usr/bin/env python3
"""Collect Apple Screen Time data into a simple CSV file.

This version is intentionally simpler than the earlier draft. It focuses on the
core workflow:
- read Mac Screen Time rows from knowledgeC.db when access is available
- optionally pull iPhone/iPad App.InFocus events via aw-import-screentime
- append new rows to screentime_data.csv and remember the last timestamp

On macOS Tahoe and newer, Apple can still block access to those databases until
Terminal or your editor has Full Disk Access.
"""

import csv
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_CSV = SCRIPT_DIR / "screentime_data.csv"
LAST_TIMESTAMP_FILE = SCRIPT_DIR / "screentime_data.csv.last"
STATUS_FILE = SCRIPT_DIR / "logs" / "last_run.status"
AW_IMPORT_BIN = SCRIPT_DIR / "aw-import-screentime" / ".venv" / "bin" / "aw-import-screentime"
KNOWLEDGE_DB = Path.home() / "Library" / "Application Support" / "Knowledge" / "knowledgeC.db"
CSV_COLUMNS = ["app", "usage", "start_time", "end_time", "created_at", "tz", "device_id", "device_model"]
APPLE_EPOCH_OFFSET = 978307200


def get_last_timestamp() -> float:
    if LAST_TIMESTAMP_FILE.exists():
        try:
            return float(LAST_TIMESTAMP_FILE.read_text().strip())
        except ValueError:
            return 0.0
    return 0.0


def save_last_timestamp(ts: float) -> None:
    LAST_TIMESTAMP_FILE.write_text(str(ts))


def extract_mac_data(last_created_at: float) -> list[tuple]:
    if not KNOWLEDGE_DB.exists():
        print(f"[mac] knowledgeC.db not found at {KNOWLEDGE_DB}")
        return []

    if not os.access(KNOWLEDGE_DB, os.R_OK):
        print(f"[mac] {KNOWLEDGE_DB} exists but is not readable")
        print("[mac] Grant Full Disk Access to Terminal and your editor, then run again.")
        return []

    query = """
    SELECT
        ZOBJECT.ZVALUESTRING AS app,
        (ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE) AS usage,
        (ZOBJECT.ZSTARTDATE + ?) AS start_time,
        (ZOBJECT.ZENDDATE + ?) AS end_time,
        (ZOBJECT.ZCREATIONDATE + ?) AS created_at,
        ZOBJECT.ZSECONDSFROMGMT AS tz,
        NULL AS device_id,
        'Mac' AS device_model
    FROM ZOBJECT
    WHERE
        ZSTREAMNAME = '/app/usage' AND
        (ZOBJECT.ZCREATIONDATE + ?) > ?
    ORDER BY ZCREATIONDATE DESC
    """

    try:
        with sqlite3.connect(str(KNOWLEDGE_DB)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, (APPLE_EPOCH_OFFSET, APPLE_EPOCH_OFFSET, APPLE_EPOCH_OFFSET, APPLE_EPOCH_OFFSET, last_created_at)).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"[mac] SQLite error: {exc}")
        print("[mac] If this is your first run on macOS Tahoe, open System Settings → Privacy & Security → Full Disk Access and allow Terminal/VS Code.")
        return []

    results = [
        (
            row["app"],
            int(row["usage"] or 0),
            float(row["start_time"] or 0),
            float(row["end_time"] or 0),
            float(row["created_at"] or 0),
            int(row["tz"] or 0),
            row["device_id"],
            row["device_model"],
        )
        for row in rows
    ]
    print(f"[mac] extracted {len(results)} new rows")
    return results


def extract_iphone_data(since_days: int = 28, last_created_at: float = 0.0) -> list[tuple]:
    if not AW_IMPORT_BIN.exists():
        print(f"[iphone] importer not found at {AW_IMPORT_BIN}")
        return []

    try:
        result = subprocess.run(
            [str(AW_IMPORT_BIN), "events", "preview", "--since", f"{since_days}d"],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        print("[iphone] importer executable is missing")
        return []
    except subprocess.TimeoutExpired:
        print("[iphone] importer timed out")
        return []

    if result.returncode != 0:
        print(f"[iphone] importer error: {result.stderr.strip()}")
        return []

    try:
        devices_data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"[iphone] could not parse importer output: {exc}")
        return []

    all_events = []
    skipped_count = 0

    for device_data in devices_data:
        device_id = device_data.get("device_id", "unknown")
        for event in device_data.get("events", []):
            timestamp = event.get("timestamp")
            duration = int(event.get("duration_seconds", 0))
            app = event.get("data", {}).get("app", "unknown")

            if not timestamp:
                continue

            try:
                start_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
            except ValueError:
                continue

            end_time = start_time + duration
            created_at = end_time

            if created_at <= last_created_at:
                skipped_count += 1
                continue

            all_events.append((app, duration, start_time, end_time, created_at, 0, device_id, "iPhone"))

    print(f"[iphone] extracted {len(all_events)} new rows (skipped {skipped_count} duplicates)")
    return all_events


def write_to_csv(mac_rows: list[tuple], iphone_rows: list[tuple]) -> None:
    all_rows = list(mac_rows) + list(iphone_rows)
    if not all_rows:
        print("[output] no new data to write")
        return

    file_exists = OUTPUT_CSV.exists()
    with OUTPUT_CSV.open("a", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_MINIMAL)
        if not file_exists:
            writer.writerow(CSV_COLUMNS)
        writer.writerows(all_rows)

    max_created_at = max(row[4] for row in all_rows if row[4])
    save_last_timestamp(max_created_at)
    print(f"[output] wrote {len(all_rows)} rows to {OUTPUT_CSV}")


def write_status(message: str) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(f"{datetime.now().isoformat()}\n{message}\n")


def main() -> None:
    print(f"=== Screen Time collection - {datetime.now().isoformat()} ===")
    last_ts = get_last_timestamp()

    if last_ts > 0:
        print(f"[config] last run timestamp: {datetime.fromtimestamp(last_ts).isoformat()}")
    else:
        print("[config] first run, collecting available data")

    try:
        mac_rows = extract_mac_data(last_ts)
        iphone_rows = extract_iphone_data(since_days=28, last_created_at=last_ts)
        write_to_csv(mac_rows, iphone_rows)
        write_status("ok")
    except Exception as exc:
        write_status(f"error: {exc}")
        raise

    print("=== collection complete ===")


if __name__ == "__main__":
    main()
