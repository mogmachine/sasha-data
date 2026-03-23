#!/usr/bin/env python3
import json
import os
import glob
import subprocess
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

def load_json(path):
    """Load JSON file, return empty dict if not exists."""
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}

def save_json(path, data):
    """Save JSON file with formatting."""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    os.chmod(path, 0o644)

def collect_usage_history():
    """Scan session JSONL files and aggregate usage by day and model."""
    print("Collecting usage history...")
    
    # Load existing data to preserve history from rotated/deleted sessions
    existing = load_json(DATA_DIR / "usage-history.json")
    old_daily = existing.get("daily", {})
    
    # Fresh scan — aggregate into new dict to avoid double-counting
    scanned_daily = {}
    
    # Scan all session JSONL files
    pattern = "/home/ubuntu/.openclaw/agents/*/sessions/*.jsonl"
    for jsonl_path in glob.glob(pattern):
        try:
            with open(jsonl_path) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        # JSONL wraps messages: {"type":"message","message":{"role":"assistant",...},"timestamp":...}
                        msg = entry.get("message", entry)
                        if msg.get("role") != "assistant":
                            continue
                        
                        usage = msg.get("usage")
                        if not usage:
                            continue
                        
                        # Extract date and model - timestamp can be at entry or message level
                        timestamp = entry.get("timestamp", msg.get("timestamp", msg.get("createdAt", "")))
                        if not timestamp:
                            continue
                        
                        date = timestamp.split("T")[0]
                        model = msg.get("model", "unknown")
                        
                        # Initialize daily entry
                        if date not in scanned_daily:
                            scanned_daily[date] = {}
                        if model not in scanned_daily[date]:
                            scanned_daily[date][model] = {
                                "input": 0,
                                "output": 0,
                                "cacheRead": 0,
                                "cacheWrite": 0,
                                "cost": 0,
                                "calls": 0
                            }
                        
                        # Aggregate
                        scanned_daily[date][model]["input"] += usage.get("input", 0)
                        scanned_daily[date][model]["output"] += usage.get("output", 0)
                        scanned_daily[date][model]["cacheRead"] += usage.get("cacheRead", 0)
                        scanned_daily[date][model]["cacheWrite"] += usage.get("cacheWrite", 0)
                        scanned_daily[date][model]["cost"] += usage.get("cost", {}).get("total", 0)
                        scanned_daily[date][model]["calls"] += 1
                    except:
                        continue
        except:
            continue
    
    # Merge: scanned days overwrite, old days not in scan are preserved
    daily = {}
    for date in old_daily:
        if date not in scanned_daily:
            daily[date] = old_daily[date]
    for date in scanned_daily:
        daily[date] = scanned_daily[date]
    
    # Calculate totals
    grand_total = {"tokens": 0, "cost": 0}
    providers = defaultdict(lambda: {"tokens": 0, "cost": 0})
    
    for date, models in daily.items():
        for model, stats in models.items():
            tokens = stats["input"] + stats["output"]
            cost = stats["cost"]
            grand_total["tokens"] += tokens
            grand_total["cost"] += cost
            
            # Extract provider from model name
            provider = model.split("/")[0] if "/" in model else "unknown"
            providers[provider]["tokens"] += tokens
            providers[provider]["cost"] += cost
    
    # Calculate weekly (last 7 days)
    today = datetime.now().date()
    weekly = {"tokens": 0, "cost": 0}
    for i in range(7):
        date = (today - timedelta(days=i)).isoformat()
        if date in daily:
            for model, stats in daily[date].items():
                weekly["tokens"] += stats["input"] + stats["output"]
                weekly["cost"] += stats["cost"]
    
    result = {
        "daily": daily,
        "grandTotal": grand_total,
        "weekly": weekly,
        "providers": dict(providers),
        "generated": datetime.now().isoformat()
    }
    
    save_json(DATA_DIR / "usage-history.json", result)
    print(f"  ✓ Found {len(daily)} days of usage data")

def collect_sessions():
    """Merge all session files and sort by updatedAt."""
    print("Collecting sessions...")
    
    sessions = []
    pattern = "/home/ubuntu/.openclaw/agents/*/sessions/sessions.json"
    
    for sessions_path in glob.glob(pattern):
        try:
            with open(sessions_path) as f:
                data = json.load(f)
                for key, session in data.items():
                    sessions.append({
                        "key": key,
                        "agent": session.get("agentId", "unknown"),
                        "label": session.get("label", ""),
                        "model": session.get("model", ""),
                        "inputTokens": session.get("inputTokens", 0),
                        "outputTokens": session.get("outputTokens", 0),
                        "updatedAt": session.get("updatedAt", "")
                    })
        except:
            continue
    
    # Sort by updatedAt descending
    sessions.sort(key=lambda s: s.get("updatedAt", ""), reverse=True)
    
    save_json(DATA_DIR / "sessions.json", sessions)
    print(f"  ✓ Found {len(sessions)} sessions")

def collect_cron():
    """Get cron jobs from openclaw CLI."""
    print("Collecting cron jobs...")
    
    try:
        result = subprocess.run(
            ["openclaw", "cron", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            raw = json.loads(result.stdout)
            # CLI returns {"jobs": [...]} wrapper
            cron_data = raw.get("jobs", raw) if isinstance(raw, dict) else raw
            # Extract relevant fields
            jobs = []
            for job in cron_data:
                jobs.append({
                    "id": job.get("id"),
                    "name": job.get("name"),
                    "schedule": job.get("schedule"),
                    "enabled": job.get("enabled", True)
                })
            save_json(DATA_DIR / "cron.json", jobs)
            print(f"  ✓ Found {len(jobs)} cron jobs")
        else:
            save_json(DATA_DIR / "cron.json", [])
            print("  ✗ No cron jobs found")
    except:
        save_json(DATA_DIR / "cron.json", [])
        print("  ✗ Failed to get cron jobs")

def collect_tasks():
    """Parse TODO.md for checklist items."""
    print("Collecting tasks...")
    
    todo_path = Path("/home/ubuntu/.openclaw/workspace/TODO.md")
    tasks = []
    
    if todo_path.exists():
        try:
            with open(todo_path) as f:
                current_section = "Uncategorized"
                for line in f:
                    line = line.strip()
                    
                    # Detect section headers
                    if line.startswith("#"):
                        current_section = line.lstrip("#").strip()
                        continue
                    
                    # Parse checklist items
                    if line.startswith("- [ ]") or line.startswith("- [x]"):
                        done = "[x]" in line[:6]
                        text = line[6:].strip()
                        
                        # Extract priority if present
                        priority = "normal"
                        if text.startswith("🔴"):
                            priority = "high"
                            text = text[1:].strip()
                        elif text.startswith("🟡"):
                            priority = "medium"
                            text = text[1:].strip()
                        
                        tasks.append({
                            "text": text,
                            "priority": priority,
                            "category": current_section,
                            "done": done
                        })
        except:
            pass
    
    save_json(DATA_DIR / "tasks.json", tasks)
    print(f"  ✓ Found {len(tasks)} tasks")

def collect_vps():
    """Collect VPS metrics."""
    print("Collecting VPS metrics...")
    
    metrics = {}
    
    # Memory
    try:
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = int(parts[1].strip().split()[0])
                    meminfo[key] = value
            
            total = meminfo.get("MemTotal", 0)
            available = meminfo.get("MemAvailable", 0)
            used = total - available
            
            metrics["memory"] = {
                "total": total * 1024,  # Convert to bytes
                "used": used * 1024,
                "percent": round((used / total * 100), 1) if total > 0 else 0
            }
    except:
        metrics["memory"] = {"total": 0, "used": 0, "percent": 0}
    
    # Load average
    try:
        with open("/proc/loadavg") as f:
            load = f.read().split()
            metrics["load"] = {
                "1min": float(load[0]),
                "5min": float(load[1]),
                "15min": float(load[2])
            }
    except:
        metrics["load"] = {"1min": 0, "5min": 0, "15min": 0}
    
    # CPU cores
    try:
        with open("/proc/cpuinfo") as f:
            cores = 0
            for line in f:
                if line.startswith("processor"):
                    cores += 1
            metrics["cpuCores"] = cores
    except:
        metrics["cpuCores"] = 1
    
    # Disk
    try:
        disk = shutil.disk_usage("/")
        metrics["disk"] = {
            "total": disk.total,
            "used": disk.used,
            "percent": round((disk.used / disk.total * 100), 1)
        }
    except:
        metrics["disk"] = {"total": 0, "used": 0, "percent": 0}
    
    # OpenClaw disk usage
    try:
        openclaw_dir = Path.home() / ".openclaw"
        total_size = 0
        
        if openclaw_dir.exists():
            for item in openclaw_dir.rglob("*"):
                if item.is_file():
                    try:
                        total_size += item.stat().st_size
                    except:
                        pass
        
        metrics["openclawSize"] = total_size
    except:
        metrics["openclawSize"] = 0
    
    # Count sessions
    try:
        pattern = "/home/ubuntu/.openclaw/agents/*/sessions/*.jsonl"
        session_count = len(glob.glob(pattern))
        metrics["sessionCount"] = session_count
    except:
        metrics["sessionCount"] = 0
    
    # Uptime
    try:
        with open("/proc/uptime") as f:
            uptime_seconds = float(f.read().split()[0])
            metrics["uptime"] = int(uptime_seconds)
    except:
        metrics["uptime"] = 0
    
    metrics["timestamp"] = datetime.now().isoformat()
    
    save_json(DATA_DIR / "vps.json", metrics)
    print(f"  ✓ Collected VPS metrics")
    
    # Update history
    collect_vps_history(metrics)

def collect_vps_history(current_metrics):
    """Append current metrics to history, keep last 672 entries."""
    print("Updating VPS history...")
    
    history = load_json(DATA_DIR / "vps-history.json")
    if not isinstance(history, list):
        history = []
    
    # Append current
    history.append({
        "timestamp": current_metrics["timestamp"],
        "memory": current_metrics["memory"]["percent"],
        "disk": current_metrics["disk"]["percent"],
        "load": current_metrics["load"]["1min"]
    })
    
    # Keep last 672 entries (7 days at 5-min intervals)
    history = history[-672:]
    
    save_json(DATA_DIR / "vps-history.json", history)
    print(f"  ✓ History has {len(history)} entries")

def collect_git():
    """Collect git repository stats."""
    print("Collecting git stats...")
    
    repo_path = "/home/ubuntu/.openclaw/workspace"
    stats = {}
    
    try:
        # Total commits
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        stats["totalCommits"] = int(result.stdout.strip()) if result.returncode == 0 else 0
    except:
        stats["totalCommits"] = 0
    
    try:
        # Total files
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        files = result.stdout.strip().split("\n") if result.returncode == 0 else []
        stats["totalFiles"] = len([f for f in files if f])
        
        # Extensions
        extensions = defaultdict(int)
        for f in files:
            if f:
                ext = Path(f).suffix or "no-ext"
                extensions[ext] += 1
        stats["extensions"] = dict(extensions)
    except:
        stats["totalFiles"] = 0
        stats["extensions"] = {}
    
    try:
        # Total size
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            total_size = 0
            files = result.stdout.split("\0")
            for f in files:
                if f:
                    try:
                        path = Path(repo_path) / f
                        if path.exists():
                            total_size += path.stat().st_size
                    except:
                        pass
            stats["totalSize"] = total_size
        else:
            stats["totalSize"] = 0
    except:
        stats["totalSize"] = 0
    
    try:
        # Largest files (top 15)
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            file_sizes = []
            files = result.stdout.split("\0")
            for f in files:
                if f:
                    try:
                        path = Path(repo_path) / f
                        if path.exists():
                            size = path.stat().st_size
                            file_sizes.append({"file": f, "size": size})
                    except:
                        pass
            
            file_sizes.sort(key=lambda x: x["size"], reverse=True)
            stats["largestFiles"] = file_sizes[:15]
        else:
            stats["largestFiles"] = []
    except:
        stats["largestFiles"] = []
    
    try:
        # Commits by day (last 30 days)
        result = subprocess.run(
            ["git", "log", "--format=%ai", "--since=30 days ago"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            commits_by_day = defaultdict(int)
            for line in result.stdout.strip().split("\n"):
                if line:
                    date = line.split()[0]
                    commits_by_day[date] += 1
            stats["commitsByDay"] = dict(commits_by_day)
        else:
            stats["commitsByDay"] = {}
    except:
        stats["commitsByDay"] = {}
    
    stats["generated"] = datetime.now().isoformat()
    
    save_json(DATA_DIR / "git.json", stats)
    print(f"  ✓ Collected git stats")

def main():
    print("🔹 OpenClaw Dashboard Data Collector\n")
    
    collect_usage_history()
    collect_sessions()
    collect_cron()
    collect_tasks()
    collect_vps()
    collect_git()
    
    # Set permissions on index.html if it exists
    index_path = Path(__file__).parent / "index.html"
    if index_path.exists():
        os.chmod(index_path, 0o644)
    
    print("\n✅ Collection complete!")

if __name__ == "__main__":
    main()
