# Project Dashboard - Architecture Documentation

> System architecture, component interactions, and deployment topology.

## Table of Contents

1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Data Flow Diagrams](#data-flow-diagrams)
4. [Sequence Diagrams](#sequence-diagrams)
5. [Database Architecture](#database-architecture)
6. [Integration Architecture](#integration-architecture)
7. [Deployment Architecture](#deployment-architecture)
8. [Security Architecture](#security-architecture)

---

## System Overview

### High-Level Architecture

```
                              ┌─────────────────────────────────────────┐
                              │           User's Browser                │
                              │  ┌───────────────────────────────────┐  │
                              │  │        Project Dashboard          │  │
                              │  │         (index.html)              │  │
                              │  │                                   │  │
                              │  │  • Dashboard Views                │  │
                              │  │  • Charts (Chart.js)              │  │
                              │  │  • Planning Chat UI               │  │
                              │  │  • WebSocket Client               │  │
                              │  └─────────────┬─────────────────────┘  │
                              └────────────────┼────────────────────────┘
                                               │
                     ┌─────────────────────────┼─────────────────────────┐
                     │                         │                         │
                     │ HTTP REST               │ WebSocket               │
                     ▼                         ▼                         │
┌─────────────────────────────┐    ┌─────────────────────────────┐      │
│    Flask Server (:8889)     │    │   Clawdbot Gateway (:18789) │      │
│                             │    │                             │      │
│  • /api/dashboard           │    │  • chat.send                │      │
│  • /api/standup             │    │  • chat.history             │      │
│  • /api/planning/*          │    │  • AI Processing            │      │
│  • /api/analytics/*         │    │                             │      │
│                             │    └─────────────────────────────┘      │
└──────────────┬──────────────┘                                         │
               │                                                         │
    ┌──────────┼──────────┬──────────────────┬──────────────────┐       │
    │          │          │                  │                  │       │
    ▼          ▼          ▼                  ▼                  ▼       │
┌───────┐  ┌───────┐  ┌───────┐      ┌─────────────┐    ┌───────────┐  │
│ Git   │  │Todoist│  │Linear │      │   Kanban    │    │PostgreSQL │  │
│ Repos │  │  API  │  │  API  │      │   (:8888)   │    │    DB     │  │
│(local)│  │(REST) │  │(GQL)  │      │   (REST)    │    │  (nick)   │  │
└───────┘  └───────┘  └───────┘      └─────────────┘    └───────────┘  │
                                                                        │
└───────────────────────────────────────────────────────────────────────┘
```

### Component Descriptions

| Component | Technology | Port | Purpose |
|-----------|------------|------|---------|
| Browser Client | HTML/JS/CSS | - | User interface |
| Flask Server | Python/Flask | 8889 | API backend, data aggregation |
| Clawdbot Gateway | Node.js | 18789 | AI chat interface |
| Kanban Server | Python/Flask | 8888 | Task board management |
| PostgreSQL | PostgreSQL 15 | 5432 | Analytics & session storage |

---

## Component Architecture

### Frontend Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         index.html                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │   HTML      │  │    CSS      │  │ JavaScript  │  │  Chart.js  │ │
│  │   Layout    │  │   Styling   │  │    Logic    │  │   Charts   │ │
│  └─────────────┘  └─────────────┘  └──────┬──────┘  └────────────┘ │
│                                           │                         │
│                           ┌───────────────┼───────────────┐         │
│                           │               │               │         │
│                           ▼               ▼               ▼         │
│                    ┌───────────┐   ┌───────────┐   ┌───────────┐   │
│                    │  State    │   │  Render   │   │    API    │   │
│                    │ Management│   │ Functions │   │  Clients  │   │
│                    └───────────┘   └───────────┘   └───────────┘   │
│                           │                               │         │
│                           │                    ┌──────────┴───┐     │
│                           │                    │              │     │
│                           ▼                    ▼              ▼     │
│                    ┌───────────┐        ┌──────────┐  ┌──────────┐ │
│                    │dashboardData│       │  fetch() │  │WebSocket │ │
│                    │standupData │        │   HTTP   │  │  Client  │ │
│                    │planSession │        └──────────┘  └──────────┘ │
│                    └───────────┘                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Backend Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          server.py                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     Flask Application                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                │                                    │
│          ┌────────────────────┼────────────────────┐               │
│          │                    │                    │               │
│          ▼                    ▼                    ▼               │
│  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐        │
│  │  API Routes   │   │ Data Fetchers │   │   Database    │        │
│  │               │   │               │   │   Module      │        │
│  │ • /           │   │ • fetch_git   │   │ (database.py) │        │
│  │ • /api/*      │   │ • fetch_todo  │   │               │        │
│  │               │   │ • fetch_kanban│   │ • Snapshots   │        │
│  │               │   │ • fetch_linear│   │ • Planning    │        │
│  │               │   │ • fetch_weather│  │ • Analytics   │        │
│  └───────────────┘   └───────────────┘   └───────────────┘        │
│                                │                                    │
│                   ┌────────────┼────────────┐                      │
│                   │            │            │                      │
│                   ▼            ▼            ▼                      │
│            ┌──────────┐ ┌──────────┐ ┌──────────┐                 │
│            │subprocess│ │ requests │ │ psycopg2 │                 │
│            │(git cmds)│ │  (HTTP)  │ │(Postgres)│                 │
│            └──────────┘ └──────────┘ └──────────┘                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagrams

### Dashboard Data Aggregation

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Dashboard Data Aggregation Flow                   │
└─────────────────────────────────────────────────────────────────────┘

     Browser                 Flask Server              External Services
        │                         │                          │
        │   GET /api/dashboard    │                          │
        │────────────────────────►│                          │
        │                         │                          │
        │                         │   ┌──────────────────────┤
        │                         │   │  ThreadPoolExecutor  │
        │                         │   │     (4 workers)      │
        │                         │   └──────────────────────┤
        │                         │            │             │
        │                         │   ┌────────┼────────┐    │
        │                         │   │        │        │    │
        │                         │   │  Parallel Fetch │    │
        │                         │   │                 │    │
        │                         │   ▼        ▼        ▼    │
        │                         │ ┌────┐  ┌────┐  ┌────┐   │
        │                         │ │Git │  │Todo│  │Kanb│   │
        │                         │ │    │  │ist │  │an  │   │──► External
        │                         │ └──┬─┘  └──┬─┘  └──┬─┘   │    APIs
        │                         │    │       │       │     │
        │                         │    └───────┼───────┘     │
        │                         │            │             │
        │                         │            ▼             │
        │                         │    ┌─────────────┐       │
        │                         │    │  Aggregate  │       │
        │                         │    │   Results   │       │
        │                         │    └──────┬──────┘       │
        │                         │           │              │
        │                         │           ▼              │
        │                         │    ┌─────────────┐       │
        │                         │    │Store to DB  │───────┼──► PostgreSQL
        │                         │    │(snapshots)  │       │
        │                         │    └──────┬──────┘       │
        │                         │           │              │
        │◄────────────────────────│───────────┘              │
        │   JSON Response         │                          │
        │                         │                          │
```

### Planning Chat Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Planning Chat Message Flow                      │
└─────────────────────────────────────────────────────────────────────┘

  Browser                Flask                Gateway               AI
     │                     │                     │                   │
     │  POST /planning/    │                     │                   │
     │  session (start)    │                     │                   │
     │────────────────────►│                     │                   │
     │                     │                     │                   │
     │                     │──► INSERT session   │                   │
     │                     │    to PostgreSQL    │                   │
     │                     │                     │                   │
     │◄────────────────────│                     │                   │
     │  {session_id: 42}   │                     │                   │
     │                     │                     │                   │
     │  WebSocket Connect  │                     │                   │
     │────────────────────────────────────────►  │                   │
     │                     │                     │                   │
     │  chat.send          │                     │                   │
     │  {message: "..."}   │                     │                   │
     │────────────────────────────────────────►  │                   │
     │                     │                     │                   │
     │                     │                     │──────────────────►│
     │                     │                     │  Process message  │
     │                     │                     │                   │
     │                     │                     │◄──────────────────│
     │                     │                     │  Stream response  │
     │                     │                     │                   │
     │◄────────────────────────────────────────  │                   │
     │  chat event         │                     │                   │
     │  {kind: "chunk"}    │                     │                   │
     │                     │                     │                   │
     │  POST /planning/    │                     │                   │
     │  message            │                     │                   │
     │────────────────────►│                     │                   │
     │                     │──► INSERT message   │                   │
     │                     │    to PostgreSQL    │                   │
     │                     │                     │                   │
```

### Analytics Snapshot Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Analytics Snapshot Flow                          │
└─────────────────────────────────────────────────────────────────────┘

    Time                     Dashboard                    PostgreSQL
      │                          │                            │
      │   Every 5 min            │                            │
      │   (auto-refresh)         │                            │
      ▼                          │                            │
 ┌─────────┐                     │                            │
 │ Trigger │────────────────────►│                            │
 │ Refresh │                     │                            │
 └─────────┘                     │                            │
                                 │                            │
                                 │  Fetch all sources         │
                                 │───────────────►            │
                                 │                            │
                                 │◄───────────────            │
                                 │  Aggregate data            │
                                 │                            │
                                 │                            │
                                 │  store_git_snapshot()      │
                                 │───────────────────────────►│
                                 │                            │
                                 │  INSERT git_snapshots      │
                                 │                            │────►
                                 │                            │
                                 │  store_todoist_snapshot()  │
                                 │───────────────────────────►│
                                 │                            │
                                 │  INSERT todoist_snapshots  │
                                 │                            │────►
                                 │                            │
                                 │  update_daily_stats()      │
                                 │───────────────────────────►│
                                 │                            │
                                 │  UPSERT daily_stats        │
                                 │                            │────►
                                 │                            │
```

---

## Sequence Diagrams

### Initial Page Load

```
┌──────┐          ┌──────┐          ┌────────┐
│Browser│         │Flask │          │External│
└───┬───┘         └───┬──┘          └───┬────┘
    │                 │                  │
    │  GET /          │                  │
    │────────────────►│                  │
    │                 │                  │
    │  index.html     │                  │
    │◄────────────────│                  │
    │                 │                  │
    │  Parse HTML     │                  │
    │  Load Chart.js  │                  │
    │                 │                  │
    │  refreshAll()   │                  │
    │                 │                  │
    │  GET /api/      │                  │
    │  dashboard      │                  │
    │────────────────►│                  │
    │                 │                  │
    │                 │  fetch_git()     │
    │                 │─────────────────►│ (subprocess)
    │                 │◄─────────────────│
    │                 │                  │
    │                 │  fetch_todoist() │
    │                 │─────────────────►│ (HTTPS)
    │                 │◄─────────────────│
    │                 │                  │
    │                 │  fetch_kanban()  │
    │                 │─────────────────►│ (HTTP)
    │                 │◄─────────────────│
    │                 │                  │
    │  JSON Response  │                  │
    │◄────────────────│                  │
    │                 │                  │
    │  Render cards   │                  │
    │  Update status  │                  │
    │                 │                  │
```

### Planning Session Lifecycle

```
┌──────┐     ┌──────┐     ┌───────┐     ┌────────┐
│Browser│    │Flask │     │Gateway│     │Postgres│
└───┬───┘    └───┬──┘     └───┬───┘     └───┬────┘
    │            │            │             │
    │  Start     │            │             │
    │  Session   │            │             │
    │───────────►│            │             │
    │            │            │             │
    │            │  INSERT    │             │
    │            │────────────────────────►│
    │            │            │             │
    │            │◄────────────────────────│
    │            │  session_id             │
    │◄───────────│            │             │
    │            │            │             │
    │  Connect   │            │             │
    │  WebSocket │            │             │
    │───────────────────────►│             │
    │            │            │             │
    │  Ack       │            │             │
    │◄───────────────────────│             │
    │            │            │             │
    │            │            │             │
    │  [User sends messages, │             │
    │   AI responds,         │             │
    │   Messages logged]     │             │
    │            │            │             │
    │  End       │            │             │
    │  Session   │            │             │
    │───────────►│            │             │
    │            │            │             │
    │            │  UPDATE    │             │
    │            │  session   │             │
    │            │────────────────────────►│
    │            │            │             │
    │◄───────────│            │             │
    │  Stats     │            │             │
    │            │            │             │
    │  Close WS  │            │             │
    │───────────────────────►│             │
    │            │            │             │
```

---

## Database Architecture

### Schema Relationships

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Database Schema                               │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          SNAPSHOT TABLES                             │
│  (Time-series data for analytics)                                   │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │
│  │dashboard_git_  │  │dashboard_      │  │dashboard_      │        │
│  │snapshots       │  │todoist_        │  │kanban_         │        │
│  │                │  │snapshots       │  │snapshots       │        │
│  │ • repo_name    │  │ • total_tasks  │  │ • backlog_cnt  │        │
│  │ • commit_count │  │ • overdue_tasks│  │ • ready_count  │        │
│  │ • is_dirty     │  │ • by_project   │  │ • in_progress  │        │
│  │ • snapshot_at  │  │ • snapshot_at  │  │ • snapshot_at  │        │
│  └────────────────┘  └────────────────┘  └────────────────┘        │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                   dashboard_daily_stats                     │    │
│  │  (Aggregated daily metrics)                                 │    │
│  │                                                             │    │
│  │  • stat_date (PK)                                          │    │
│  │  • git_total_commits, git_active_repos                     │    │
│  │  • todoist_completed, todoist_added                        │    │
│  │  • kanban_completed, kanban_added                          │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         PLANNING TABLES                              │
│  (Session tracking and message logs)                                │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                   planning_sessions                         │    │
│  │  • id (PK)                                                  │    │
│  │  • started_at, ended_at, duration_seconds                  │    │
│  │  • initial_context (JSONB)                                 │    │
│  │  • final_state (JSONB)                                     │    │
│  │  • messages_count, actions_count                           │    │
│  └──────────────────────────┬─────────────────────────────────┘    │
│                              │                                      │
│              ┌───────────────┴───────────────┐                     │
│              │                               │                     │
│              ▼                               ▼                     │
│  ┌────────────────────────┐    ┌────────────────────────┐         │
│  │   planning_messages    │    │   planning_actions     │         │
│  │                        │    │                        │         │
│  │  • id (PK)             │    │  • id (PK)             │         │
│  │  • session_id (FK)     │    │  • session_id (FK)     │         │
│  │  • role (user/asst)    │    │  • action_type         │         │
│  │  • content             │    │  • target_type/id      │         │
│  │  • tokens_used         │    │  • details (JSONB)     │         │
│  │  • sent_at             │    │  • action_at           │         │
│  └────────────────────────┘    └────────────────────────┘         │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                  planning_daily_stats                       │    │
│  │  • stat_date (PK)                                          │    │
│  │  • sessions_count, total_duration_seconds                  │    │
│  │  • total_messages, tasks_planned/completed/deferred        │    │
│  │  • planning_accuracy                                       │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Integration Architecture

### External API Integration

```
┌─────────────────────────────────────────────────────────────────────┐
│                    External API Integration                          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                           Flask Server                               │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      Integration Layer                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│         │              │              │              │              │
│         ▼              ▼              ▼              ▼              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐       │
│  │  Todoist  │  │  Linear   │  │  Weather  │  │  Kanban   │       │
│  │  Client   │  │  Client   │  │  Client   │  │  Client   │       │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘       │
│        │              │              │              │               │
└────────┼──────────────┼──────────────┼──────────────┼───────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Todoist   │  │   Linear    │  │   wttr.in   │  │   Kanban    │
│   REST API  │  │  GraphQL    │  │   Weather   │  │   Local     │
│             │  │             │  │             │  │             │
│  HTTPS      │  │  HTTPS      │  │  HTTPS      │  │  HTTP       │
│  Bearer     │  │  API Key    │  │  No Auth    │  │  No Auth    │
│  Token      │  │  Header     │  │             │  │             │
│             │  │             │  │             │  │             │
│ api.todoist │  │ api.linear  │  │  wttr.in    │  │ localhost   │
│ .com        │  │ .app        │  │             │  │ :8888       │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
```

### Error Handling Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Error Handling Per Integration                   │
└─────────────────────────────────────────────────────────────────────┘

Integration      Timeout    Retry    Fallback
─────────────────────────────────────────────────────────────────────
Todoist          10s        No       Return empty + error status
Linear           10s        No       Return empty + error status
Weather          5s         No       Return error status
Kanban (API)     3s         No       Fallback to PostgreSQL
Kanban (DB)      5s         No       Return error status
Git (local)      5s/repo    No       Skip repo, continue others
Gateway (WS)     N/A        Auto     Reconnect on disconnect
```

---

## Deployment Architecture

### Local Development

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Local Development Setup                           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         Mac Mini (Local)                             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      User Space                              │   │
│  │                                                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │   │
│  │  │  Browser    │  │  Terminal   │  │  VS Code    │         │   │
│  │  │             │  │             │  │             │         │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │   │
│  │                                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     Background Services                      │   │
│  │                                                              │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐   │   │
│  │  │Dashboard  │ │Kanban     │ │Clawdbot   │ │PostgreSQL │   │   │
│  │  │Server     │ │Server     │ │Gateway    │ │           │   │   │
│  │  │:8889      │ │:8888      │ │:18789     │ │:5432      │   │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘   │   │
│  │                                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                       File System                            │   │
│  │                                                              │   │
│  │  ~/clawd/projects/project-dashboard/                        │   │
│  │  ~/clawd/jeeves-kanban/                                     │   │
│  │  ~/clawd/projects/* (git repos)                             │   │
│  │                                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Production Deployment (Future)

```
┌─────────────────────────────────────────────────────────────────────┐
│                   Production Deployment (Future)                     │
└─────────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │   Tailscale │
                              │   Network   │
                              └──────┬──────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           │                         │                         │
           ▼                         ▼                         ▼
   ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
   │   Mac Mini    │        │    Unraid     │        │   Mobile      │
   │   (Gateway)   │        │   (Services)  │        │   (Client)    │
   │               │        │               │        │               │
   │ • Clawdbot    │◄──────►│ • Dashboard   │◄──────►│ • Safari/     │
   │ • PostgreSQL  │        │ • Kanban      │        │   Chrome      │
   │               │        │ • Nginx       │        │               │
   └───────────────┘        └───────────────┘        └───────────────┘
```

---

## Security Architecture

### Authentication & Authorization

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Security Model                                    │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  Component              │  Auth Method         │  Scope              │
├─────────────────────────┼──────────────────────┼─────────────────────┤
│  Dashboard Server       │  None (local only)   │  Read/Write local   │
│  Kanban API             │  None (local only)   │  Full CRUD          │
│  Clawdbot Gateway       │  Token (localStorage)│  Chat + Tools       │
│  Todoist API            │  Bearer Token        │  Read Tasks         │
│  Linear API             │  API Key             │  Read Issues        │
│  PostgreSQL             │  Local socket        │  Full access        │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Protection

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Data Protection                                   │
└─────────────────────────────────────────────────────────────────────┘

Data Type              Storage              Protection
─────────────────────────────────────────────────────────────────────
API Tokens             config.yaml          File permissions (600)
                       (gitignored)

Gateway Token          localStorage         Browser same-origin

Task Data              PostgreSQL           Local access only

Chat History           PostgreSQL           Local access only

Snapshots              PostgreSQL           No sensitive data
```

### Network Security

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Network Boundaries                                │
└─────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────┐
                    │        TRUSTED ZONE         │
                    │      (localhost only)       │
                    │                             │
                    │  Dashboard ◄──► Kanban      │
                    │      │            │         │
                    │      ▼            ▼         │
                    │   Gateway ◄──► PostgreSQL   │
                    │                             │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────┴───────────────┐
                    │        EXTERNAL ZONE        │
                    │      (HTTPS only)           │
                    │                             │
                    │  Todoist   Linear   wttr.in │
                    │                             │
                    └─────────────────────────────┘
```

---

*Last updated: 2026-01-30*
