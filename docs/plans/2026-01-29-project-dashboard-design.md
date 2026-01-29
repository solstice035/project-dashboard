# Project Intelligence Dashboard - Design Document

**Date:** 2026-01-29  
**Status:** Approved  
**Author:** Jeeves + Nick

---

## Overview

A web-based dashboard for monitoring dev project status across multiple sources. Runs locally on the network, provides at-a-glance visibility into active work.

## Requirements

### Data Sources
- **Git repos** (~/clawd/projects): Commits (7d), branch status, uncommitted changes
- **Todoist**: Tasks filtered by specific projects (exclude work)
- **Linear.app**: Issues by status, assigned issues, project backlog
- **Kanban board**: In-progress and ready tasks from localhost:8888

### User Experience
- **Web UI** at localhost:8889
- **Dark mode** dev aesthetic (deep navy, teal/cyan accents, coral alerts)
- **Hybrid refresh**: Auto-poll every 5 minutes + manual refresh button
- **Responsive**: 4-column grid on desktop, stacks on mobile

---

## Architecture

### Stack
- **Backend:** Python Flask API
- **Frontend:** Single HTML file with embedded JS/CSS
- **Database:** None (live pulls from sources)
- **Port:** 8889

### Data Flow
```
Browser → GET /api/dashboard → Flask
                                  ↓
                    ┌─────────────┼─────────────┐
                    ↓             ↓             ↓
                 Todoist       Linear         Git
                   API          API         (local)
                    ↓             ↓             ↓
                    └─────────────┼─────────────┘
                                  ↓
                         Kanban API (8888)
                                  ↓
                          JSON Response
                                  ↓
                         Render in Browser
```

---

## UI Design

### Header
- Title: "Project Dashboard"
- Last refresh timestamp
- Manual refresh button (with spinner)
- Source status indicators (green/orange dots)

### Main Grid
```
┌─────────────────┬─────────────────┐
│   🚀 ACTIVE     │   📋 TODOIST    │
│   Git repos     │   Today/Overdue │
│   with changes  │   by project    │
├─────────────────┼─────────────────┤
│   📊 LINEAR     │   🎯 KANBAN     │
│   Issues by     │   In Progress   │
│   status        │   + Ready       │
└─────────────────┴─────────────────┘
```

### Card Contents

**Git Card:**
- Repo name
- Current branch
- Commits in last 7 days
- ⚠️ indicator if dirty working tree

**Todoist Card:**
- Task name
- Due date (with overdue highlighting)
- Priority flag (🔴🟠🟡)
- Project tag

**Linear Card:**
- Issue ID + title
- Status badge (backlog/in-progress/done)
- Assignee avatar

**Kanban Card:**
- Task title
- Column badge
- Tags

### Visual Style
- Background: #1a1a2e (deep navy)
- Cards: Subtle borders, slight transparency
- Accents: Teal/cyan for status, coral for alerts
- Typography: Monospace for git/code, Inter/system sans-serif elsewhere
- Inspired by Kanban board but distinct (solid colours vs gradients)

---

## Error Handling

### Source Failures
- Card shows warning state (orange border)
- Error message displayed
- Other cards continue working
- Header indicator turns orange
- Retry on next refresh cycle

### Empty States
- Git: "All quiet 😴" + last commit date
- Todoist: "Clear day! 🎉"
- Linear: "Backlog empty"
- Kanban: "Nothing in progress"

### Loading States
- Skeleton cards with pulse animation
- Individual card loading on single-source refresh

### Missing Config
- Linear API key missing → Setup instructions in card
- Todoist token invalid → Re-auth prompt
- Graceful degradation: works with available sources

---

## Project Structure
```
project-dashboard/
├── server.py           # Flask backend
├── index.html          # Frontend (self-contained)
├── config.yaml         # API keys (gitignored)
├── config.example.yaml # Template
├── requirements.txt
├── start-server.sh
├── stop-server.sh
├── tests/
│   ├── test_git.py
│   ├── test_todoist.py
│   ├── test_linear.py
│   └── test_api.py
├── docs/
│   └── plans/
│       └── 2026-01-29-project-dashboard-design.md
└── README.md
```

---

## Configuration

### config.yaml
```yaml
todoist:
  token: "your-token"
  projects:
    - "Personal"
    - "Home"
    # Exclude work projects

linear:
  api_key: "lin_api_xxx"
  team_id: "your-team"

git:
  scan_paths:
    - ~/clawd/projects
  
kanban:
  api_url: "http://localhost:8888/api/tasks"

server:
  port: 8889
  refresh_interval: 300  # 5 minutes
```

---

## Testing Strategy

### Unit Tests
- `test_git.py`: Git repo scanning, commit parsing, dirty detection
- `test_todoist.py`: API response parsing, filtering by project
- `test_linear.py`: API response parsing, status mapping
- `test_api.py`: Flask endpoint, aggregation, error responses

### Integration Tests
- Full dashboard fetch with mocked external APIs
- Error scenarios (source timeouts, invalid responses)

### Manual Testing
- Visual check on desktop and mobile
- Verify all source indicators
- Test refresh behaviour

---

## Deployment

### Local Setup
1. Clone repo
2. Copy `config.example.yaml` to `config.yaml`
3. Add API keys
4. `pip install -r requirements.txt`
5. `./start-server.sh`

### Auto-Start (macOS)
- LaunchAgent plist for auto-start on boot
- Logs to ~/clawd/logs/project-dashboard.log

### Network Access
- Accessible at `http://[mac-mini-ip]:8889`
- Or configure hostname like `http://mini.local:8889`

---

## Implementation Plan

1. **Phase 1: Backend API**
   - Flask server setup
   - Git repo scanner
   - Todoist integration
   - Kanban integration
   - Aggregation endpoint

2. **Phase 2: Frontend**
   - HTML/CSS structure
   - Dark mode styling
   - Card components
   - Refresh logic

3. **Phase 3: Linear Integration**
   - API key setup
   - Issue fetching
   - Status mapping

4. **Phase 4: Polish**
   - Error handling
   - Loading states
   - Empty states
   - Responsive design

5. **Phase 5: Testing**
   - Unit tests
   - Integration tests
   - Manual QA

6. **Phase 6: Deployment**
   - GitHub repo
   - Auto-start service
   - Documentation

---

## Open Questions

- [ ] Which Todoist projects to include? (Nick to specify)
- [ ] Linear team/project IDs? (Setup during implementation)
- [ ] Preferred hostname for network access?

---

*Design approved: 2026-01-29*
