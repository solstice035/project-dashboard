# 🎯 Project Dashboard

> A unified command center for productivity, task management, and AI-assisted daily planning.

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-yellow)

## Overview

Project Dashboard aggregates data from multiple productivity tools into a single, beautiful dark-mode interface. Features include real-time task tracking, git repository monitoring, and an AI-powered planning chat for daily prioritization.

```
┌─────────────────────────────────────────────────────────────┐
│  🎯 Project Dashboard                    [●●●●] [↻] 07:00  │
├─────────────────────────────────────────────────────────────┤
│  [☀️ Standup] [💬 Plan] [📊 Dashboard] [📈 Analytics]      │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────┐  ┌───────────────────┐              │
│  │ 🚀 Git Repos      │  │ 📋 Todoist        │              │
│  │ 5 repos, 23 commits│  │ 3 overdue, 8 today│              │
│  └───────────────────┘  └───────────────────┘              │
│  ┌───────────────────┐  ┌───────────────────┐              │
│  │ 📊 Linear         │  │ 🎯 Kanban         │              │
│  │ 12 issues assigned│  │ 2 in progress     │              │
│  └───────────────────┘  └───────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

## ✨ Features

### 📊 Multi-Source Dashboard
- **Git Repositories**: Commits, branches, uncommitted changes
- **Todoist**: Tasks by priority and due date
- **Linear**: Issues by status and assignment
- **Kanban**: Jeeves task board integration

### ☀️ Morning Standup
- Weather conditions
- Overdue task alerts
- Today's priorities
- In-progress work summary

### 💬 AI Planning Chat
- Context-aware conversations with Jeeves
- Quick action buttons (Focus, Blockers, Reschedule)
- Real-time task updates
- Session logging for analytics

### 📈 Analytics & Trends
- Commit activity over time
- Task completion rates
- Planning session insights
- Custom date range views

## 🚀 Quick Start

```bash
# 1. Clone and setup
cd ~/clawd/projects/project-dashboard
cp config.example.yaml config.yaml

# 2. Add your API tokens to config.yaml
#    - Todoist token
#    - Linear API key (optional)

# 3. Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Start the server
./start-server.sh

# 5. Open in browser
open http://localhost:8889
```

## 📁 Project Structure

```
project-dashboard/
├── server.py              # Flask backend
├── database.py            # PostgreSQL operations
├── index.html             # Frontend (single file)
├── schema.sql             # Database schema
├── config.yaml            # Configuration (gitignored)
├── config.example.yaml    # Config template
├── requirements.txt       # Python dependencies
├── start-server.sh        # Launch script
├── stop-server.sh         # Stop script
├── docs/
│   ├── USER-GUIDE.md      # End-user documentation
│   ├── TECHNICAL.md       # API & technical reference
│   ├── DESIGN.md          # UI/UX design system
│   ├── ARCHITECTURE.md    # System architecture
│   └── plans/             # Design documents
└── tests/                 # Test suite
```

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/USER-GUIDE.md) | How to use the dashboard |
| [Technical Reference](docs/TECHNICAL.md) | API, database, configuration |
| [Design System](docs/DESIGN.md) | UI components, colors, typography |
| [Architecture](docs/ARCHITECTURE.md) | System diagrams, data flows |

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard UI |
| `/api/health` | GET | Health check |
| `/api/dashboard` | GET | Aggregated data from all sources |
| `/api/standup` | GET | Morning briefing data |
| `/api/planning/session` | POST | Start/end planning session |
| `/api/planning/message` | POST | Log chat message |
| `/api/planning/analytics` | GET | Planning statistics |
| `/api/analytics/trends` | GET | Historical trends |

## 🛠️ Configuration

```yaml
# config.yaml
todoist:
  token: "your-todoist-api-token"
  projects: []  # Empty = all projects

linear:
  api_key: "lin_api_..."  # Optional

git:
  scan_paths:
    - "~/clawd/projects"
  history_days: 7

kanban:
  api_url: "http://localhost:8888/api/tasks"

server:
  port: 8889
  host: "0.0.0.0"
  refresh_interval: 300
```

## 🎨 Design

Built with a developer-focused dark mode aesthetic:

- **Background**: Deep space (#0f0f1a)
- **Accent**: Teal (#38b2ac)
- **Cards**: Midnight blue (#16213e)

See [Design System](docs/DESIGN.md) for complete specifications.

## 🏗️ Architecture

```
Browser ──► Flask Server ──┬──► Git (subprocess)
   │           │           ├──► Todoist API
   │           │           ├──► Linear API
   │           │           ├──► Kanban API
   │           │           └──► PostgreSQL
   │           │
   └── WebSocket ──────────────► Clawdbot Gateway
```

See [Architecture](docs/ARCHITECTURE.md) for detailed diagrams.

## 🧪 Development

```bash
# Run in debug mode
FLASK_DEBUG=1 python server.py

# Run tests
pytest

# With coverage
pytest --cov=. --cov-report=html
```

## 📋 Requirements

- Python 3.11+
- PostgreSQL 15+
- Node.js (for Clawdbot Gateway)
- Modern browser (Chrome, Safari, Firefox)

## 🔗 Related Projects

- [Jeeves Kanban](../jeeves-kanban/) - Task board backend
- [Clawdbot](https://github.com/clawdbot/clawdbot) - AI assistant platform

## 📄 License

MIT

---

*Built with ❤️ by Jeeves & Nick*
