# Apple Screen Time Collector

This repository collects Apple Screen Time data from macOS and optionally from iPhone/iPad data exposed through the ActivityWatch importer.

Inspired by https://boazsobrado.com/blog/2026/02/03/how-i-built-a-personal-screen-time-tracker-for-mac-and-iphone-using-claude/#what-we-built.

## What it does

- Reads Mac Screen Time rows from the macOS knowledge database when access is available.
- Optionally imports iPhone/iPad App.InFocus events through the bundled importer.
- Appends new rows to a CSV file for later analysis.

## Requirements

- macOS with Screen Time enabled.
- Full Disk Access for Terminal and any editor used to run the scripts.
- Python 3.

## Setup

1. Clone the repository.
2. Install the importer dependency if you want iPhone/iPad collection.
3. Run the collector manually:

```bash
python3 collect_screentime.py
```

Or use the shell wrapper:

```bash
bash run_screentime_collection.sh
```

## Notes

- The scripts use your local Apple database paths and will only work if macOS allows access to them.
- The generated CSV and log files are ignored by git by default.
- If you want to automate the job with launchd, create your own plist and replace the local path and label with your own values.
