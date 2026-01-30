# Project Dashboard - User Guide

> Your command center for productivity, task management, and daily planning.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Dashboard Overview](#dashboard-overview)
3. [Tabs & Features](#tabs--features)
4. [Planning Your Day](#planning-your-day)
5. [Tips & Best Practices](#tips--best-practices)
6. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Accessing the Dashboard

Open your browser and navigate to:
```
http://localhost:8889
```

The dashboard loads automatically and fetches data from all configured sources.

### First-Time Setup

1. **Configure API Keys** (if not done):
   ```bash
   cd ~/clawd/projects/project-dashboard
   cp config.example.yaml config.yaml
   # Edit config.yaml with your tokens
   ```

2. **Start the Server**:
   ```bash
   ./start-server.sh
   ```

3. **Open the Dashboard**: Navigate to http://localhost:8889

---

## Dashboard Overview

```
┌─────────────────────────────────────────────────────────────┐
│  🎯 Project Dashboard                    [Status] [Refresh] │
├─────────────────────────────────────────────────────────────┤
│  [Standup] [Plan] [Dashboard] [Analytics] [Git] [Tasks]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  🚀 Git Repos   │  │  📋 Todoist     │                  │
│  │                 │  │                 │                  │
│  │  Recent commits │  │  Today's tasks  │                  │
│  │  Branch status  │  │  Overdue items  │                  │
│  └─────────────────┘  └─────────────────┘                  │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  📊 Linear      │  │  🎯 Kanban      │                  │
│  │                 │  │                 │                  │
│  │  Assigned issues│  │  In progress    │                  │
│  │  By status     │  │  Ready items    │                  │
│  └─────────────────┘  └─────────────────┘                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Status Indicators

The header shows connection status for each data source:

| Indicator | Meaning |
|-----------|---------|
| 🟢 Green | Connected and working |
| 🟡 Yellow | Not configured / Warning |
| 🔴 Red | Error / Connection failed |
| ⚪ Pulsing | Loading |

### Auto-Refresh

The dashboard automatically refreshes every 5 minutes (configurable). Click **Refresh** for immediate updates.

---

## Tabs & Features

### ☀️ Standup Tab

Your morning briefing at a glance.

**Displays:**
- **Weather**: Current conditions and temperature
- **Summary**: Quick counts (overdue, today, in progress)
- **Overdue Tasks**: Tasks past their due date (urgent!)
- **Today's Tasks**: What's scheduled for today
- **In Progress**: Active Kanban items (Jeeves tasks)

**Best for:** Starting your day, quick status checks

---

### 💬 Plan Tab

Interactive planning with AI assistance.

```
┌─────────────────────┐  ┌─────────────────────────────────┐
│  📋 Context         │  │  💬 Planning Chat               │
│                     │  │                                 │
│  ⚠️ Overdue (3)     │  │  [Session #42 active]  [End]   │
│  • Task A           │  │                                 │
│  • Task B           │  │  You: What should I focus on?  │
│                     │  │                                 │
│  📅 Today (5)       │  │  Jeeves: Based on your tasks,  │
│  • 🔴 Urgent task   │  │  I'd recommend starting with   │
│  • 🟠 High priority │  │  the overdue items...          │
│                     │  │                                 │
│  🚀 In Progress (2) │  │  [________________] [Send]     │
│  • Dashboard build  │  │                                 │
│                     │  │  [Focus] [Blockers] [Summary]  │
│  [Refresh]          │  │                                 │
└─────────────────────┘  └─────────────────────────────────┘
```

**How to Use:**

1. Click **Start Session** to begin planning
2. Enter your Gateway token (first time only - saved in browser)
3. Ask questions or use Quick Actions:
   - 🎯 **Focus**: "What should I focus on first?"
   - 🚧 **Blockers**: "What's blocking me?"
   - 📅 **Reschedule**: "Reschedule low priority tasks"
   - 📊 **Summary**: "Give me a quick summary"

4. Jeeves responds with context-aware advice
5. Click **End Session** when done

**Note:** All conversations are logged for analytics.

---

### 📊 Dashboard Tab

The main overview showing all data sources in a grid layout.

**Cards:**
- **Git Repos**: Recent commits, dirty repos, branch status
- **Todoist**: Tasks organized by priority and due date
- **Linear**: Assigned issues by status
- **Kanban**: Jeeves task board status

---

### 📈 Analytics Tab

Trends and insights over time.

**Features:**
- **Period Selector**: 7 / 14 / 30 day views
- **Stats**: Total commits, active repos, tasks, in-progress items
- **Charts**:
  - Git Activity (commits over time)
  - Kanban Flow (task movement)
  - Linear Issues (status distribution)

---

### 🚀 Git Details Tab

Expanded view of all repositories.

**Shows:**
- Repository name and current branch
- Recent commit messages
- Uncommitted changes indicator
- Ahead/behind remote tracking

---

### 📋 Task Details Tab

Complete list of all Todoist tasks.

**Features:**
- Full task content
- Project assignment
- Due dates
- Priority indicators (🔴 🟠 🟡)
- Overdue highlighting

---

### 📊 Linear Details Tab

Detailed view of Linear issues.

**Sections:**
- Stats overview (total, in progress, todo, backlog)
- In Progress issues
- Todo items
- Backlog items

---

## Planning Your Day

### Recommended Morning Workflow

```
1. Open Dashboard
        │
        ▼
2. Check Standup Tab
   - Review weather
   - Note overdue count
   - Scan today's tasks
        │
        ▼
3. Open Plan Tab
   - Start a session
   - Ask "What should I focus on?"
   - Discuss priorities with Jeeves
        │
        ▼
4. Execute Your Plan
   - Work on prioritized tasks
   - Use Dashboard to track progress
        │
        ▼
5. End of Day
   - Review completed items
   - Note blockers for tomorrow
```

### Quick Actions Explained

| Action | What It Does |
|--------|--------------|
| 🎯 Focus | Analyzes priorities and suggests what to tackle first |
| 🚧 Blockers | Identifies what's preventing progress |
| 📅 Reschedule | Helps defer non-urgent items to future dates |
| 📊 Summary | Provides a quick overview of your situation |

### Planning Session Tips

1. **Be specific**: "Move the tyre task to next week" works better than "reschedule stuff"
2. **Ask follow-ups**: "Why that task first?" helps understand priorities
3. **Take action**: Ask Jeeves to actually update tasks, not just suggest
4. **End sessions**: Properly ending sessions helps with analytics

---

## Tips & Best Practices

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message (in Plan chat) |
| `R` | Refresh dashboard (when focused) |

### Optimal Setup

- **Monitor Position**: Keep dashboard visible on secondary monitor
- **Refresh Rate**: Default 5 minutes is good; lower if needed
- **Token Storage**: Gateway token is saved in browser localStorage

### Data Source Priorities

| Priority | Source | Why |
|----------|--------|-----|
| 1 | Todoist | Personal tasks with due dates |
| 2 | Kanban | Jeeves project tasks |
| 3 | Linear | Team/work issues |
| 4 | Git | Development activity |

---

## Troubleshooting

### "Not configured" Warning

**Cause**: API token not set in config.yaml

**Fix**:
```bash
# Edit config
nano ~/clawd/projects/project-dashboard/config.yaml

# Add your tokens
todoist:
  token: "your-token-here"
```

### Chat Not Connecting

**Cause**: Gateway not running or wrong token

**Fix**:
1. Ensure Clawdbot Gateway is running:
   ```bash
   clawdbot gateway status
   ```

2. Get your Gateway token:
   ```bash
   clawdbot config get gateway.auth.token
   ```

3. Clear stored token (in browser console):
   ```javascript
   localStorage.removeItem('gateway_token')
   ```

### Data Not Loading

**Cause**: Server not running or API errors

**Fix**:
1. Check server status:
   ```bash
   curl http://localhost:8889/api/health
   ```

2. Check server logs:
   ```bash
   tail -f ~/clawd/projects/project-dashboard/server.log
   ```

3. Restart server:
   ```bash
   ./stop-server.sh && ./start-server.sh
   ```

### Kanban Not Showing

**Cause**: Kanban server not running

**Fix**:
```bash
cd ~/clawd/jeeves-kanban
./start-server.sh
```

---

## Support

- **Issues**: Check server.log for errors
- **Updates**: `git pull` in project directory
- **Config**: See config.example.yaml for all options

---

*Last updated: 2026-01-30*
