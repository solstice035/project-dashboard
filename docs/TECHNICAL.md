# Project Dashboard - Technical Documentation

> Complete technical reference for developers and maintainers.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Technology Stack](#technology-stack)
3. [API Reference](#api-reference)
4. [Database Schema](#database-schema)
5. [Configuration](#configuration)
6. [Data Flow](#data-flow)
7. [WebSocket Integration](#websocket-integration)
8. [Development Guide](#development-guide)
9. [Deployment](#deployment)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Project Dashboard                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │
│  │   Browser   │◄──►│   Flask     │◄──►│   PostgreSQL            │ │
│  │   (index.   │    │   Server    │    │   (nick database)       │ │
│  │    html)    │    │   :8889     │    │                         │ │
│  └─────────────┘    └──────┬──────┘    └─────────────────────────┘ │
│         │                  │                                        │
│         │                  │           ┌─────────────────────────┐ │
│         │                  ├──────────►│   External APIs         │ │
│         │                  │           │   • Todoist REST API    │ │
│         │                  │           │   • Linear GraphQL      │ │
│         │                  │           │   • wttr.in Weather     │ │
│         │                  │           └─────────────────────────┘ │
│         │                  │                                        │
│         │                  │           ┌─────────────────────────┐ │
│         │                  ├──────────►│   Local Services        │ │
│         │                  │           │   • Git repos (shell)   │ │
│         │                  │           │   • Kanban API :8888    │ │
│         │                  │           └─────────────────────────┘ │
│         │                  │                                        │
│         │    WebSocket     │           ┌─────────────────────────┐ │
│         └─────────────────────────────►│   Clawdbot Gateway      │ │
│                                        │   :18789 (WS)           │ │
│                                        └─────────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **Flask Server** | API endpoints, data aggregation, session management |
| **Browser Client** | UI rendering, WebSocket chat, local state |
| **PostgreSQL** | Analytics storage, planning session logs |
| **Clawdbot Gateway** | AI chat interface via WebSocket |

---

## Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| Flask | 2.3+ | Web framework |
| psycopg2 | 2.9+ | PostgreSQL driver |
| requests | 2.31+ | HTTP client |
| PyYAML | 6.0+ | Config parsing |

### Frontend

| Technology | Purpose |
|------------|---------|
| Vanilla JS | Application logic |
| Chart.js | Data visualization |
| CSS3 Custom Properties | Theming |
| WebSocket API | Gateway chat |

### Database

| System | Database | Tables |
|--------|----------|--------|
| PostgreSQL 15+ | nick | dashboard_*, planning_* |

### External Integrations

| Service | Protocol | Auth Method |
|---------|----------|-------------|
| Todoist | REST API | Bearer token |
| Linear | GraphQL | API key header |
| wttr.in | REST API | None |
| Kanban | REST API | None (local) |
| Git | Shell exec | File system |
| Clawdbot | WebSocket | Token auth |

---

## API Reference

### Base URL

```
http://localhost:8889/api
```

### Endpoints

#### Health Check

```http
GET /api/health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-01-30T07:00:00.000000",
  "version": "1.0.0"
}
```

---

#### Dashboard Data

```http
GET /api/dashboard
```

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| store | bool | true | Store snapshot to DB |

**Response:**
```json
{
  "timestamp": "2026-01-30T07:00:00.000000",
  "fetch_time_seconds": 1.23,
  "refresh_interval": 300,
  "db_available": true,
  "sources": {
    "git": { "status": "ok", "repos": [...] },
    "todoist": { "status": "ok", "tasks": [...] },
    "kanban": { "status": "ok", "tasks": [...], "by_column": {...} },
    "linear": { "status": "ok", "issues": [...], "by_status": {...} }
  }
}
```

---

#### Standup Data

```http
GET /api/standup
```

**Response:**
```json
{
  "generated_at": "2026-01-30T07:00:00.000000",
  "date": "2026-01-30",
  "day_name": "Thursday",
  "fetch_time_seconds": 0.85,
  "weather": {
    "status": "ok",
    "temp_c": "12",
    "condition": "Partly cloudy",
    "humidity": "65",
    "wind_kph": "15"
  },
  "tasks": {
    "overdue": [...],
    "today": [...],
    "upcoming": [...]
  },
  "kanban": {
    "in_progress": [...],
    "ready": [...]
  },
  "summary": {
    "overdue_count": 3,
    "today_count": 5,
    "in_progress_count": 2
  }
}
```

---

#### Analytics Trends

```http
GET /api/analytics/trends?days=30
```

**Query Parameters:**
| Param | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| days | int | 30 | 1-365 | Lookback period |

**Response:**
```json
{
  "days": 30,
  "git": [
    { "date": "2026-01-01", "total_commits": 15, "repos_with_activity": 3 }
  ],
  "todoist": [...],
  "kanban": [...],
  "linear": [...]
}
```

---

#### Planning Session Management

```http
POST /api/planning/session
```

**Request Body (Start):**
```json
{
  "action": "start"
}
```

**Response:**
```json
{
  "status": "ok",
  "session_id": 42,
  "started_at": "2026-01-30T07:00:00.000000",
  "context": {
    "tasks": [...],
    "kanban": {...}
  }
}
```

**Request Body (End):**
```json
{
  "action": "end",
  "session_id": 42,
  "final_state": { "notes": "..." }
}
```

---

#### Log Planning Action

```http
POST /api/planning/action
```

**Request Body:**
```json
{
  "session_id": 42,
  "action_type": "defer",
  "target_type": "todoist",
  "target_id": "12345",
  "target_title": "Check tyre pressure",
  "details": { "new_due_date": "2026-02-01" }
}
```

**Action Types:**
| Type | Description |
|------|-------------|
| defer | Task rescheduled to later |
| complete | Task marked done |
| prioritize | Priority changed |
| add | New task created |
| drop | Task removed/cancelled |
| reschedule | Due date changed |

---

#### Log Planning Message

```http
POST /api/planning/message
```

**Request Body:**
```json
{
  "session_id": 42,
  "role": "user",
  "content": "What should I focus on today?",
  "tokens_used": 150
}
```

---

#### Planning Analytics

```http
GET /api/planning/analytics?days=30
```

**Response:**
```json
{
  "days": 30,
  "sessions": [
    {
      "id": 42,
      "started_at": "2026-01-30T07:00:00",
      "ended_at": "2026-01-30T07:15:00",
      "duration_seconds": 900,
      "messages_count": 12,
      "actions_count": 5
    }
  ],
  "action_breakdown": [
    { "action_type": "defer", "count": 15 },
    { "action_type": "complete", "count": 8 }
  ],
  "totals": {
    "total_sessions": 25,
    "total_duration": 18000,
    "total_messages": 300,
    "total_actions": 75,
    "avg_duration": 720
  }
}
```

---

#### Configuration Status

```http
GET /api/config
```

**Response:**
```json
{
  "todoist": {
    "configured": true,
    "projects": ["Personal", "Work"]
  },
  "linear": {
    "configured": true
  },
  "git": {
    "scan_paths": ["~/clawd/projects"],
    "history_days": 7
  },
  "kanban": {
    "api_url": "http://localhost:8888/api/tasks"
  },
  "server": {
    "refresh_interval": 300
  }
}
```

---

## Database Schema

### Entity Relationship Diagram

```
┌────────────────────────┐
│  dashboard_git_        │
│  snapshots             │
├────────────────────────┤
│  id (PK)               │
│  repo_name             │
│  branch                │
│  commit_count          │
│  is_dirty              │
│  ahead                 │
│  behind                │
│  snapshot_at           │
└────────────────────────┘

┌────────────────────────┐
│  dashboard_todoist_    │
│  snapshots             │
├────────────────────────┤
│  id (PK)               │
│  total_tasks           │
│  overdue_tasks         │
│  today_tasks           │
│  completed_today       │
│  by_project (JSONB)    │
│  by_priority (JSONB)   │
│  snapshot_at           │
└────────────────────────┘

┌────────────────────────┐
│  dashboard_kanban_     │
│  snapshots             │
├────────────────────────┤
│  id (PK)               │
│  backlog_count         │
│  ready_count           │
│  in_progress_count     │
│  review_count          │
│  done_count            │
│  total_tasks           │
│  snapshot_at           │
└────────────────────────┘

┌────────────────────────┐       ┌────────────────────────┐
│  planning_sessions     │       │  planning_actions      │
├────────────────────────┤       ├────────────────────────┤
│  id (PK)               │◄──┐   │  id (PK)               │
│  started_at            │   │   │  session_id (FK)───────┤
│  ended_at              │   │   │  action_at             │
│  duration_seconds      │   │   │  action_type           │
│  initial_context       │   │   │  target_type           │
│  final_state (JSONB)   │   │   │  target_id             │
│  messages_count        │   │   │  target_title          │
│  actions_count         │   │   │  details (JSONB)       │
└────────────────────────┘   │   └────────────────────────┘
                             │
                             │   ┌────────────────────────┐
                             │   │  planning_messages     │
                             │   ├────────────────────────┤
                             └───│  id (PK)               │
                                 │  session_id (FK)       │
                                 │  sent_at               │
                                 │  role                  │
                                 │  content               │
                                 │  tokens_used           │
                                 └────────────────────────┘
```

### Table Definitions

See `schema.sql` for complete CREATE TABLE statements.

### Indexes

| Table | Index | Columns |
|-------|-------|---------|
| dashboard_git_snapshots | idx_git_snapshots_repo | repo_name |
| dashboard_git_snapshots | idx_git_snapshots_time | snapshot_at |
| planning_sessions | idx_planning_sessions_started | started_at |
| planning_actions | idx_planning_actions_session | session_id |
| planning_actions | idx_planning_actions_type | action_type |

---

## Configuration

### config.yaml Structure

```yaml
# API Tokens
todoist:
  token: "your-todoist-api-token"
  projects: []  # Empty = all projects

linear:
  api_key: "lin_api_..."
  team_id: ""  # Optional team filter

# Git Configuration
git:
  scan_paths:
    - "~/clawd/projects"
    - "~/dev"
  history_days: 7

# Local Services
kanban:
  api_url: "http://localhost:8888/api/tasks"

# Server Settings
server:
  port: 8889
  host: "0.0.0.0"
  refresh_interval: 300  # seconds
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| FLASK_DEBUG | Enable debug mode | false |
| DATABASE_URL | PostgreSQL connection | dbname=nick host=localhost |

---

## Data Flow

### Dashboard Refresh Flow

```
┌─────────┐     ┌─────────┐     ┌─────────────────┐
│ Browser │────►│  Flask  │────►│ ThreadPool      │
│         │     │ /api/   │     │ Executor        │
└─────────┘     │dashboard│     │ (4 workers)     │
                └─────────┘     └────────┬────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
              ▼                          ▼                          ▼
    ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
    │  fetch_git()    │      │ fetch_todoist() │      │  fetch_kanban() │
    │  - subprocess   │      │ - REST API      │      │  - REST API     │
    │  - git commands │      │ - Bearer token  │      │  - Fallback DB  │
    └────────┬────────┘      └────────┬────────┘      └────────┬────────┘
             │                        │                        │
             └────────────────────────┼────────────────────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │  Aggregate Results  │
                           │  Store Snapshots    │
                           │  Return JSON        │
                           └─────────────────────┘
```

### Planning Chat Flow

```
┌─────────┐     ┌─────────────┐     ┌─────────────┐
│ Browser │────►│ Start       │────►│ PostgreSQL  │
│         │     │ Session API │     │ INSERT      │
└────┬────┘     └─────────────┘     │ session     │
     │                              └─────────────┘
     │
     │  WebSocket
     ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Clawdbot    │────►│ AI Process  │────►│ Stream      │
│ Gateway     │     │ Message     │     │ Response    │
│ :18789      │     │             │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
     ┌─────────────────────────────────────────┘
     │
     ▼
┌─────────────┐     ┌─────────────┐
│ Log Message │────►│ PostgreSQL  │
│ to Backend  │     │ INSERT      │
│             │     │ message     │
└─────────────┘     └─────────────┘
```

---

## WebSocket Integration

### Gateway Connection

The frontend connects directly to Clawdbot Gateway via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:18789');

// Authentication
ws.send(JSON.stringify({
  type: 'connect',
  params: { auth: { token: gatewayToken } }
}));

// Send message
ws.send(JSON.stringify({
  type: 'chat.send',
  message: 'Hello',
  sessionKey: 'main'
}));
```

### Message Types

| Type | Direction | Description |
|------|-----------|-------------|
| connect | → Gateway | Initial auth handshake |
| chat.send | → Gateway | Send user message |
| chat | ← Gateway | Response events |
| error | ← Gateway | Error notification |

### Chat Event Kinds

| Kind | Description |
|------|-------------|
| text | Full message text |
| chunk | Streaming text chunk |
| tool_start | Tool execution starting |
| tool_end | Tool execution complete |
| done / end | Message complete |

---

## Development Guide

### Local Setup

```bash
# Clone project
cd ~/clawd/projects/project-dashboard

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp config.example.yaml config.yaml
# Edit config.yaml

# Run database migrations
python3 -c "
import psycopg2
conn = psycopg2.connect(dbname='nick', host='localhost')
# Execute schema.sql
"

# Start development server
FLASK_DEBUG=1 python server.py
```

### Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=. --cov-report=html

# Test specific endpoint
curl http://localhost:8889/api/health | jq
```

### Code Structure

```
project-dashboard/
├── server.py           # Flask application & API routes
├── database.py         # PostgreSQL operations
├── index.html          # Frontend (single file)
├── schema.sql          # Database schema
├── config.yaml         # Configuration (gitignored)
├── config.example.yaml # Config template
├── requirements.txt    # Python dependencies
├── start-server.sh     # Launch script
├── stop-server.sh      # Stop script
├── docs/               # Documentation
│   ├── USER-GUIDE.md
│   ├── TECHNICAL.md
│   ├── DESIGN.md
│   └── ARCHITECTURE.md
└── tests/              # Test suite
```

---

## Deployment

### Production Checklist

- [ ] Set `FLASK_DEBUG=false`
- [ ] Configure proper CORS if needed
- [ ] Use gunicorn/uvicorn instead of Flask dev server
- [ ] Set up SSL/TLS for WebSocket
- [ ] Configure database connection pooling
- [ ] Set up log rotation
- [ ] Monitor with health check endpoint

### Systemd Service

```ini
[Unit]
Description=Project Dashboard
After=network.target postgresql.service

[Service]
Type=simple
User=nick
WorkingDirectory=/Users/nick/clawd/projects/project-dashboard
ExecStart=/Users/nick/clawd/projects/project-dashboard/venv/bin/python server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Reverse Proxy (nginx)

```nginx
location /dashboard/ {
    proxy_pass http://localhost:8889/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

---

*Last updated: 2026-01-30*
