#!/usr/bin/env python3

"""
Linux System Health and Resource Monitor (Beginner-Friendly)

This script is intentionally simple and educational. It uses basic
Linux commands and the Python standard library to show system info,
CPU/memory/disk usage, running processes, network status, running
services, a file permission checker, and a simple health report.

Notes for students:
- Commands are executed via Python's subprocess module (where useful).
- CPU usage is computed from /proc/stat using a short time interval.
- Memory usage is read from /proc/meminfo.
- Disk usage uses shutil.disk_usage("/") which is equivalent to df for our purpose.
- Services use systemctl in read-only mode (no service changes).
- File permissions use os.stat() and the stat module.
"""

import os
import platform
import socket
import stat
import shutil
import subprocess
import sys
import time
from typing import Tuple, Optional


# ----------- Simple constants for thresholds -----------
CPU_WARN = 70
CPU_CRIT = 90

MEM_WARN = 70
MEM_CRIT = 90

DISK_WARN = 80
DISK_CRIT = 90


# ----------- Small helpers -----------
def run_cmd(cmd: list[str], timeout: int = 5) -> Tuple[bool, str]:
    """Run a shell command safely and return (ok, output_or_error).

    This function never raises an exception to the caller; instead it returns
    ok=False with the error message. It also avoids crashing if the command is
    unavailable on the system.
    """
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout, text=True)
        return True, out.strip()
    except FileNotFoundError:
        return False, f"Command not found: {' '.join(cmd)}"
    except subprocess.CalledProcessError as e:
        return False, e.output.strip() if e.output else str(e)
    except Exception as e:  # catch-all to remain beginner-friendly and robust
        return False, str(e)


def print_header(title: str) -> None:
    print("=" * 40)
    print(f"{title:^40}")
    print("=" * 40)


def wait_for_enter() -> None:
    try:
        input("\nPress Enter to return to the menu...")
    except EOFError:
        # In some environments stdin may be closed; ignore.
        pass


def classify_status(percent: float, warn: int, crit: int) -> str:
    if percent < warn:
        return "NORMAL"
    if percent < crit:
        return "WARNING"
    return "CRITICAL"


def human_gb(bytes_value: int) -> str:
    gb = bytes_value / (1024 ** 3)
    return f"{gb:.1f} GB"


# ----------- 1) System Information -----------
def read_os_name() -> str:
    """Try to read a friendly OS name from /etc/os-release; fallback to uname."""
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                data = {}
                for line in f:
                    line = line.strip()
                    if not line or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    data[k] = v.strip('"')
                pretty = data.get("PRETTY_NAME") or data.get("NAME")
                if pretty:
                    return pretty
    except Exception:
        pass

    ok, out = run_cmd(["uname", "-s"])
    return out if ok else platform.system()


def system_information() -> None:
    print_header("SYSTEM INFORMATION")

    os_name = read_os_name()

    ok_kernel, kernel = run_cmd(["uname", "-r"])  # kernel version
    if not ok_kernel:
        kernel = platform.release()

    ok_arch, arch = run_cmd(["uname", "-m"])  # machine architecture
    if not ok_arch:
        arch = platform.machine()

    # hostname command is common; fallback to socket if missing
    ok_host, hostname = run_cmd(["hostname"])
    if not ok_host:
        hostname = socket.gethostname()

    print(f"Operating System : {os_name}")
    print(f"Kernel Version   : {kernel}")
    print(f"Architecture     : {arch}")
    print(f"Hostname         : {hostname}")


# ----------- 2) CPU Usage -----------
def _read_proc_stat_totals() -> Optional[Tuple[int, int]]:
    """Read the first 'cpu' line from /proc/stat and return (idle_total, total).

    /proc/stat first line begins with 'cpu' and then a series of numbers.
    These numbers are jiffies (time units) spent in different modes.

    Fields (typical order):
      user nice system idle iowait irq softirq steal guest guest_nice

    We compute:
      idle_all = idle + iowait
      non_idle = user + nice + system + irq + softirq + steal
      total = idle_all + non_idle
    """
    try:
        with open("/proc/stat", "r", encoding="utf-8") as f:
            first = f.readline()
        if not first.startswith("cpu "):
            return None
        parts = first.split()
        # Convert numeric fields (skip the 'cpu' label)
        nums = list(map(int, parts[1:]))
        if len(nums) < 7:
            return None
        user, nice, system_t, idle, iowait, irq, softirq = nums[:7]
        steal = nums[7] if len(nums) > 7 else 0
        idle_all = idle + iowait
        non_idle = user + nice + system_t + irq + softirq + steal
        total = idle_all + non_idle
        return idle_all, total
    except Exception:
        return None


def cpu_usage_percent(interval: float = 0.5) -> Optional[float]:
    """Compute CPU usage percentage over a short interval using /proc/stat.

    Steps (simple explanation):
    1) Read total and idle time from /proc/stat.
    2) Wait a short time (default 0.5 seconds).
    3) Read them again.
    4) Calculate how much total time and idle time increased.
    5) CPU% = (TotalDiff - IdleDiff) / TotalDiff * 100.
    """
    first = _read_proc_stat_totals()
    if first is None:
        return None
    time.sleep(interval)
    second = _read_proc_stat_totals()
    if second is None:
        return None

    idle1, total1 = first
    idle2, total2 = second
    total_diff = total2 - total1
    idle_diff = idle2 - idle1
    if total_diff <= 0:
        return None
    usage = (total_diff - idle_diff) * 100.0 / total_diff
    return round(usage, 1)


def show_cpu_usage() -> None:
    print_header("CPU USAGE")
    usage = cpu_usage_percent()
    if usage is None:
        print("Could not compute CPU usage (\"/proc/stat\" unavailable).")
    else:
        status = classify_status(usage, CPU_WARN, CPU_CRIT)
        print(f"CPU Usage: {usage}%\tStatus: {status}")
        print("\nHow it's calculated:")
        print("- Read CPU time counters from /proc/stat twice.")
        print("- Calculate the difference (total vs idle).")
        print("- Usage% = (TotalDiff - IdleDiff) / TotalDiff * 100.")
    wait_for_enter()


# ----------- 3) Memory Usage -----------
def memory_usage() -> Optional[Tuple[int, int, int, float]]:
    """Return (total_bytes, used_bytes, available_bytes, percent_used)."""
    try:
        meminfo = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    meminfo[k.strip()] = v.strip()

        def kb_value(key: str) -> int:
            # Values are like '16367456 kB'
            raw = meminfo.get(key, "0 kB").split()[0]
            return int(raw) * 1024  # to bytes

        total = kb_value("MemTotal")
        available = kb_value("MemAvailable")
        used = total - available
        percent = (used / total) * 100 if total else 0.0
        return total, used, available, round(percent, 1)
    except Exception:
        return None


def show_memory_usage() -> None:
    print_header("MEMORY USAGE")
    result = memory_usage()
    if result is None:
        print("Could not read /proc/meminfo.")
    else:
        total, used, available, percent = result
        status = classify_status(percent, MEM_WARN, MEM_CRIT)
        print(f"Total     : {human_gb(total)}")
        print(f"Used      : {human_gb(used)}")
        print(f"Available : {human_gb(available)}")
        print(f"Usage     : {percent}%\tStatus: {status}")
    wait_for_enter()


# ----------- 4) Disk Usage -----------
def disk_usage_root() -> Tuple[int, int, int, float]:
    """Return (total_bytes, used_bytes, free_bytes, percent_used) for '/'."""
    du = shutil.disk_usage("/")
    total, used, free = du.total, du.used, du.free
    percent = (used / total) * 100 if total else 0.0
    return total, used, free, round(percent, 1)


def show_disk_usage() -> None:
    print_header("DISK USAGE (/)")
    total, used, free, percent = disk_usage_root()
    status = classify_status(percent, DISK_WARN, DISK_CRIT)
    print(f"Total     : {human_gb(total)}")
    print(f"Used      : {human_gb(used)}")
    print(f"Available : {human_gb(free)}")
    print(f"Usage     : {percent}%\tStatus: {status}")
    # Optional: also show 'df -h /' output for familiarity
    ok, out = run_cmd(["df", "-h", "/"])  # May fail on some minimal systems
    if ok:
        print("\n(df -h /) output:")
        print(out)
    wait_for_enter()


# ----------- 5) Running Processes -----------
def show_running_processes() -> None:
    print_header("RUNNING PROCESSES (Top 10 by CPU)")
    # Show a simple, readable list without overwhelming output
    cmd = [
        "ps", "-eo", "pid,comm,pcpu", "--sort=-pcpu"
    ]
    ok, out = run_cmd(cmd)
    if not ok:
        print("Could not run 'ps' to list processes.")
    else:
        lines = out.splitlines()
        # Keep header + first 10
        limited = lines[:11] if len(lines) > 11 else lines
        print("\n".join(limited))
    wait_for_enter()


# ----------- 6) Network Status -----------
def get_network_status() -> Tuple[str, str]:
    """Return (status, info_text). Status is 'ACTIVE' or 'INACTIVE'.

    We consider the network ACTIVE if we can find an interface with an IPv4
    address in the 'up' state. Fallback to broader checks if needed.
    """
    # Quick, clean form: one-line per address
    ok, out = run_cmd(["ip", "-o", "-4", "addr", "show", "up"])
    if ok and out:
        return "ACTIVE", out

    # Fallback: any 'inet ' in general listing
    ok2, out2 = run_cmd(["ip", "addr"])
    if ok2 and ("inet " in out2):
        return "ACTIVE", out2

    # Last resort: try ifconfig if installed
    ok3, out3 = run_cmd(["ifconfig", "-a"])  # not always present
    if ok3 and ("inet " in out3 or "inet addr:" in out3):
        return "ACTIVE", out3

    return "INACTIVE", (out if ok else out2 if ok2 else out3)


def show_network_status() -> None:
    print_header("NETWORK STATUS")
    status, info = get_network_status()
    print(f"Network Status: {status}")
    # Show a small snippet for context (avoid walls of text)
    if info:
        lines = info.splitlines()
        preview = lines[:8]
        if len(lines) > 8:
            preview.append("...")
        print("\n".join(preview))
    wait_for_enter()


# ----------- 7) Running Services -----------
def show_running_services() -> None:
    print_header("RUNNING SERVICES (systemd)")
    # Show currently running services using systemctl, if available
    cmd = [
        "systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--no-legend"
    ]
    ok, out = run_cmd(cmd, timeout=10)
    if not ok or not out:
        print("Could not list services. This may happen if:")
        print("- systemctl is not installed, or")
        print("- systemd is not the init system (e.g., containers/WSL).")
        wait_for_enter()
        return
    lines = out.splitlines()
    header = "UNIT NAME (first 10)"
    print(header)
    print("-" * len(header))
    for line in lines[:10]:
        # Typical line: "cron.service                 loaded active running Regular background program processing daemon"
        unit = line.split()[0] if line else line
        print(unit)
    wait_for_enter()


# ----------- 8) File Permission Checker -----------
def mode_to_rwx(mode: int) -> Tuple[str, str, str]:
    """Return (owner, group, others) rwx strings like 'rwx', 'r-x', 'r--'."""
    owner = ["r" if mode & stat.S_IRUSR else "-",
             "w" if mode & stat.S_IWUSR else "-",
             "x" if mode & stat.S_IXUSR else "-"]
    group = ["r" if mode & stat.S_IRGRP else "-",
             "w" if mode & stat.S_IWGRP else "-",
             "x" if mode & stat.S_IXGRP else "-"]
    others = ["r" if mode & stat.S_IROTH else "-",
              "w" if mode & stat.S_IWOTH else "-",
              "x" if mode & stat.S_IXOTH else "-"]
    return ("".join(owner), "".join(group), "".join(others))


def show_file_permission_checker() -> None:
    print_header("FILE PERMISSION CHECKER")
    path = input("Enter file path: ").strip()
    if not path:
        print("No path provided.")
        wait_for_enter()
        return
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        print(f"Path does not exist: {path}")
        wait_for_enter()
        return
    try:
        st = os.stat(path)
        mode = stat.S_IMODE(st.st_mode)
        owner_rwx, group_rwx, others_rwx = mode_to_rwx(mode)
        numeric = format(mode, "o").zfill(3)  # e.g., '644'

        print(f"File: {path}")
        print(f"Owner permissions : {owner_rwx}")
        print(f"Group permissions : {group_rwx}")
        print(f"Others permissions: {others_rwx}")
        print(f"Numeric code      : {numeric}")
        print("\nExplanation:")
        print("- Owner: permissions for the file's owner user")
        print("- Group: permissions for users in the file's group")
        print("- Others: permissions for everyone else")
    except PermissionError:
        print("Permission denied while accessing the file's metadata.")
    except Exception as e:
        print(f"Error reading permissions: {e}")
    wait_for_enter()


# ----------- 9) System Health Report -----------
def overall_health(cpu_p: Optional[float], mem_p: Optional[float], disk_p: float, net_status: str) -> str:
    """Simple overall health: CRITICAL -> POOR; WARNING -> FAIR; else GOOD.

    Network status doesn't affect the numeric thresholds here; it's shown in the report.
    """
    statuses = []
    if cpu_p is None:
        # If we cannot read CPU, be conservative and ignore it for overall.
        pass
    else:
        statuses.append(classify_status(cpu_p, CPU_WARN, CPU_CRIT))
    if mem_p is not None:
        statuses.append(classify_status(mem_p, MEM_WARN, MEM_CRIT))
    statuses.append(classify_status(disk_p, DISK_WARN, DISK_CRIT))

    if "CRITICAL" in statuses:
        return "POOR"
    if "WARNING" in statuses:
        return "FAIR"
    return "GOOD"


def show_system_health_report() -> None:
    print_header("SYSTEM HEALTH REPORT")
    cpu_p = cpu_usage_percent()
    mem = memory_usage()
    if mem is None:
        mem_p = None
    else:
        _, _, _, mem_p = mem
    total, used, free, disk_p = disk_usage_root()
    net_status, _ = get_network_status()

    # Prepare per-resource statuses
    cpu_line = "Unavailable"
    if cpu_p is not None:
        cpu_line = f"{cpu_p}%\t{classify_status(cpu_p, CPU_WARN, CPU_CRIT)}"
    mem_line = "Unavailable"
    if mem_p is not None:
        mem_line = f"{mem_p}%\t{classify_status(mem_p, MEM_WARN, MEM_CRIT)}"
    disk_line = f"{disk_p}%\t{classify_status(disk_p, DISK_WARN, DISK_CRIT)}"

    print(f"CPU Usage       : {cpu_line}")
    print(f"Memory Usage    : {mem_line}")
    print(f"Disk Usage      : {disk_line}")
    print(f"Network         : {net_status}")

    overall = overall_health(cpu_p, mem_p, disk_p, net_status)
    print("\nOverall Health  :", overall)
    print("=" * 40)
    wait_for_enter()


# ----------- Menu and main loop -----------
def print_menu() -> None:
    print("=" * 40)
    print(f"{'LINUX SYSTEM HEALTH MONITOR':^40}")
    print("=" * 40)
    print()
    print("1. System Information")
    print("2. CPU Usage")
    print("3. Memory Usage")
    print("4. Disk Usage")
    print("5. Running Processes")
    print("6. Network Status")
    print("7. Running Services")
    print("8. File Permission Checker")
    print("9. System Health Report")
    print("10. Exit")
    print()


def main() -> None:
    actions = {
        "1": system_information,
        "2": show_cpu_usage,
        "3": show_memory_usage,
        "4": show_disk_usage,
        "5": show_running_processes,
        "6": show_network_status,
        "7": show_running_services,
        "8": show_file_permission_checker,
        "9": show_system_health_report,
    }

    while True:
        print_menu()
        try:
            choice = input("Enter your choice: ").strip()
        except EOFError:
            print("\nInput closed. Exiting.")
            break
        if choice == "10":
            print("Exiting. Goodbye!")
            break
        action = actions.get(choice)
        if action is None:
            print("Invalid choice. Please enter a number from 1 to 10.")
            time.sleep(1)
            continue
        try:
            action()
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            time.sleep(1)
        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(1)


if __name__ == "__main__":
    # Ensure Linux environment for best results (Debian/Ubuntu as requested)
    if os.name != "posix":
        print("Note: This program is intended for Linux (Debian/Ubuntu).")
    main()
