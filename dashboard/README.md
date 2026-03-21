# 🔹 Sasha Dashboard

A complete self-contained dashboard for monitoring OpenClaw usage, system resources, and project activity.

## Components

### 1. Data Collector (`collect.py`)
Python script that aggregates data from multiple sources:

- **usage-history.json** — Token usage and costs by day and model
- **sessions.json** — All active sessions sorted by last update
- **cron.json** — Scheduled jobs from OpenClaw
- **tasks.json** — Tasks from TODO.md with priorities
- **vps.json** — Current system resources (memory, disk, CPU, uptime)
- **vps-history.json** — Historical metrics (7 days at 5-min intervals)
- **git.json** — Repository statistics and commit history

### 2. Frontend (`index.html`)
Single-file HTML dashboard with:

- Light/dark theme toggle (persisted to localStorage)
- Real-time cost tracking and usage visualization
- Chart.js stacked bar chart for daily costs
- System resource monitoring with progress bars
- Session and cron job management views
- Task list integration
- Git repository statistics
- Auto-refresh every 5 minutes

## Usage

### Run the collector:
```bash
cd /home/ubuntu/.openclaw/workspace/dashboard
./collect.py
```

### View the dashboard:
Open `index.html` in a web browser or serve it with a local server:
```bash
python3 -m http.server 8080
```

Then navigate to `http://localhost:8080`

### Automate collection:
Add a cron job to run the collector periodically:
```bash
openclaw cron add "Dashboard Collector" "*/5 * * * *" "cd /home/ubuntu/.openclaw/workspace/dashboard && ./collect.py"
```

## Design

### Colors
- **Light theme:** 
  - Background: #f5f6f6
  - Cards: #ffffff
  - Border: #e9eaeb
  - Accent: #00d4aa (teal)

- **Dark theme:**
  - Background: #0a0a0a
  - Cards: #111111
  - Border: #1e1e1e
  - Accent: #00d4aa (teal)

### Fonts
- **Text:** Switzer (from Fontshare)
- **Numbers/Code:** JetBrains Mono

## Requirements

- Python 3 (standard library only)
- Modern web browser with JavaScript enabled
- OpenClaw installation with session history

## File Structure

```
dashboard/
├── collect.py          # Data collector script
├── index.html          # Self-contained dashboard
├── README.md           # This file
└── data/               # Generated JSON files
    ├── usage-history.json
    ├── sessions.json
    ├── cron.json
    ├── tasks.json
    ├── vps.json
    ├── vps-history.json
    └── git.json
```

## Features

✅ Zero dependencies (except Python stdlib and Chart.js CDN)
✅ Self-contained single HTML file
✅ Responsive design
✅ Dark/light theme
✅ Auto-refresh
✅ Historical data preservation
✅ Clean, modern UI

---

Built for **Sasha** 🔹
