# Linux System Health Monitor (Beginner-Friendly)

## Objective
A simple, terminal-based Python program to help beginners explore basic Linux system information and resources: CPU, memory, disk, processes, network, running services, file permissions, and a basic health report. Designed for an "Introduction to Linux" course.

## Features
- System Information: OS name, kernel version, architecture, hostname.
- CPU Usage: Current percentage from `/proc/stat` with NORMAL/WARNING/CRITICAL.
- Memory Usage: Total/Used/Available/Percent from `/proc/meminfo`.
- Disk Usage: Root filesystem totals via `shutil.disk_usage("/")` (+ `df -h /` preview).
- Running Processes: Simple list from `ps` (top 10 by CPU).
- Network Status: Checks interfaces with `ip` (fallbacks to `ifconfig`).
- Running Services: Lists active services with `systemctl` (read-only).
- File Permission Checker: Shows owner/group/others permissions and numeric code.
- System Health Report: Combines CPU/Memory/Disk/Network into a simple overall health.

## Technologies Used
- Python 3 (standard library only)
- Basic Linux commands executed via `subprocess`

## Linux Commands/Concepts Used
- `uname` (system info)
- `/proc/stat`, `/proc/meminfo` (kernel-provided info files)
- `df` (disk usage, optional preview)
- `ps` (running processes)
- `ip addr` / `ip -o -4 addr show up` (network info)
- `systemctl list-units --type=service --state=running` (running services)
- File permissions (owner/group/others), `os.stat()` and permission bits (e.g., `644`)

## How to Run
```bash
# On Debian/Ubuntu or other Linux
cd linux-system-health-monitor
python3 monitor.py
```

If you want to make it executable:
```bash
chmod +x monitor.py
./monitor.py
```

## How It Works (Brief)
- Menu-driven CLI with simple functions for each feature.
- CPU usage: reads `/proc/stat` twice, 0.5s apart. Usage% = (TotalDiff - IdleDiff) / TotalDiff × 100.
- Memory: parses `MemTotal` and `MemAvailable` from `/proc/meminfo` (Used = Total - Available).
- Disk: uses `shutil.disk_usage("/")` to get total/used/free, equivalent in spirit to `df`.
- Processes: calls `ps` and shows a small, readable subset (top 10 by CPU).
- Network: uses `ip` to detect an active interface with an IPv4 address; fallbacks included.
- Services: uses `systemctl` in read-only mode. If unavailable (e.g., containers/WSL), it reports that gracefully.
- File permissions: `os.stat()` + `stat` to show rwx for owner/group/others and the numeric mode (e.g., 644).

## Thresholds (Simple)
- CPU & Memory: NORMAL < 70% < WARNING < 90% < CRITICAL
- Disk: NORMAL < 80% < WARNING < 90% < CRITICAL
- Overall Health: any CRITICAL → POOR; else if any WARNING → FAIR; else GOOD.

## Future Scope
- Add per-core CPU details and historical charts (still terminal-based).
- Show top processes by memory usage too.
- Add simple log file export (text report) for demonstrations.
- Extend disk/network checks to multiple mount points and interfaces.

## Limitations
- Intended for Linux (Debian/Ubuntu). Some features need `/proc` and `systemctl`.
- Service listing requires `systemd`; environments without it will show a friendly note.
- Network "ACTIVE" detection is basic (IPv4 presence on an up interface).
- Not a real-time monitor; it runs on demand with simple snapshots.
- Keeps output short on purpose (beginner-friendly).

## Educational Notes
- This project favors clarity over complexity, using only the Python standard library and familiar Linux commands. Students should be able to map each feature to a core Linux concept: kernel info (`/proc`), processes (`ps`), filesystems (`df`/disk usage), networking (`ip`), services (`systemctl`), and permissions (`chmod`-style bits via `os.stat`).
