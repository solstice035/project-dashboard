# Standup & Planning Chat - Design Document

**Created:** 2026-01-30
**Status:** In Development

## Overview

Add a focused planning interface to the Project Dashboard that combines:
1. Morning standup view (tasks, calendar, projects)
2. Context-aware chat with Jeeves for planning
3. Live updates when actions are taken
4. PostgreSQL logging for analytics

## User Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Project Dashboard                                          │
├─────────────────────────────────────────────────────────────┤
│  [Overview] [Git] [Todoist] [Kanban] [Standup] [Plan]      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────┐  ┌─────────────────────────────┐  │
│  │  📋 Today's Focus   │  │  💬 Planning Chat           │  │
│  │                     │  │                             │  │
│  │  ⚠️ Overdue (3)     │  │  [Context loaded...]        │  │
│  │  • Task A           │  │                             │  │
│  │  • Task B           │  │  You: Push tyres to tomorrow│  │
│  │                     │  │                             │  │
│  │  📅 Today (5)       │  │  Jeeves: Done! Moved to     │  │
│  │  • Meeting 10:00    │  │  tomorrow. Anything else?   │  │
│  │  • Task C           │  │                             │  │
│  │  • Task D           │  │  You: What should I focus   │  │
│  │                     │  │  on first?                  │  │
│  │  🚀 In Progress     │  │                             │  │
│  │  • Dashboard build  │  │  Jeeves: Based on deadlines │  │
│  │                     │  │  and priorities...          │  │
│  │  [Refresh]          │  │                             │  │
│  └─────────────────────┘  │  [________________] [Send]  │  │
│                           └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Architecture

### Frontend (index.html)

**New Tabs:**
- `Standup` - Morning briefing view
- `Plan` - Split view with standup + chat

**WebSocket Connection:**
- Connect to Clawdbot Gateway at `ws://localhost:18789`
- Use RPC: `chat.send`, `chat.history`, `chat.abort`
- Handle streaming responses via event listeners

**Live Updates:**
- After chat action, poll `/api/dashboard` to refresh task lists
- Or: WebSocket event from Jeeves triggers refresh

### Backend (server.py)

**New Endpoints:**

```python
# Get standup data (morning briefing format)
GET /api/standup
Returns: { weather, tasks, calendar, kanban, generated_at }

# Log planning session
POST /api/planning/session
Body: { action: "start" | "end", context: {...} }

# Log planning action  
POST /api/planning/action
Body: { session_id, action_type, target, details }

# Get planning analytics
GET /api/planning/analytics
Returns: { sessions, actions, trends }
```

### Database Schema

```sql
-- Planning sessions
CREATE TABLE planning_sessions (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMP,
    duration_seconds INTEGER,
    context JSONB,  -- tasks shown, calendar events
    outcome JSONB   -- what was decided
);

-- Planning actions (task changes during planning)
CREATE TABLE planning_actions (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES planning_sessions(id),
    action_at TIMESTAMP NOT NULL DEFAULT NOW(),
    action_type VARCHAR(50),  -- 'defer', 'complete', 'prioritize', 'add', 'drop'
    target_type VARCHAR(50),  -- 'todoist', 'kanban'
    target_id VARCHAR(100),
    details JSONB
);

-- Daily planning summaries (aggregated)
CREATE TABLE planning_daily_stats (
    date DATE PRIMARY KEY,
    sessions_count INTEGER DEFAULT 0,
    total_duration_seconds INTEGER DEFAULT 0,
    tasks_planned INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    tasks_deferred INTEGER DEFAULT 0,
    planning_accuracy FLOAT  -- completed / planned
);
```

### Chat Context Injection

When starting a planning session, inject context:

```javascript
const context = {
    date: "2026-01-30",
    overdue: [...tasks],
    today: [...tasks],
    calendar: [...events],
    inProgress: [...kanbanTasks]
};

// Send to Clawdbot with system context
chatSend({
    message: userMessage,
    systemContext: `Planning session context:\n${JSON.stringify(context, null, 2)}`
});
```

## Analytics Queries

```sql
-- Planning accuracy over time
SELECT 
    date,
    tasks_planned,
    tasks_completed,
    ROUND(planning_accuracy * 100) as accuracy_pct
FROM planning_daily_stats
ORDER BY date DESC
LIMIT 30;

-- Most deferred tasks
SELECT 
    details->>'task_content' as task,
    COUNT(*) as defer_count
FROM planning_actions
WHERE action_type = 'defer'
GROUP BY details->>'task_content'
ORDER BY defer_count DESC
LIMIT 10;

-- Average planning time
SELECT 
    AVG(duration_seconds) / 60 as avg_minutes,
    COUNT(*) as sessions
FROM planning_sessions
WHERE ended_at IS NOT NULL;
```

## Implementation Plan

### Phase 1: Standup Tab (30 min)
- [ ] Add `/api/standup` endpoint
- [ ] Create Standup tab UI
- [ ] Display tasks, calendar, kanban summary

### Phase 2: Database Schema (15 min)
- [ ] Add planning tables to schema.sql
- [ ] Add database functions to database.py

### Phase 3: Planning Chat UI (1 hour)
- [ ] Add Plan tab with split view
- [ ] WebSocket connection to Gateway
- [ ] Message send/receive with streaming
- [ ] Context injection on session start

### Phase 4: Live Updates (30 min)
- [ ] Detect task changes in chat
- [ ] Trigger standup refresh
- [ ] Visual feedback on changes

### Phase 5: Analytics (30 min)
- [ ] Log sessions and actions
- [ ] Add `/api/planning/analytics` endpoint
- [ ] Basic analytics display

## Security Notes

- Gateway token stored in localStorage (user must provide)
- No sensitive data in planning logs (task IDs only, not content details unless needed)
- Rate limiting on chat to prevent abuse

## Future Enhancements

- Voice input for planning ("Hey Jeeves, what's my day look like?")
- Calendar integration (block time for focused tasks)
- Smart suggestions ("You usually defer this task, want to drop it?")
- Weekly review integration
