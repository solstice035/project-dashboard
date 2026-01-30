-- Project Dashboard Analytics Schema
-- Database: nick (PostgreSQL)

-- Git commit snapshots
CREATE TABLE IF NOT EXISTS dashboard_git_snapshots (
    id SERIAL PRIMARY KEY,
    repo_name VARCHAR(255) NOT NULL,
    branch VARCHAR(255),
    commit_count INTEGER DEFAULT 0,
    is_dirty BOOLEAN DEFAULT FALSE,
    ahead INTEGER DEFAULT 0,
    behind INTEGER DEFAULT 0,
    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_git_snapshots_repo ON dashboard_git_snapshots(repo_name);
CREATE INDEX IF NOT EXISTS idx_git_snapshots_time ON dashboard_git_snapshots(snapshot_at);

-- Todoist task snapshots
CREATE TABLE IF NOT EXISTS dashboard_todoist_snapshots (
    id SERIAL PRIMARY KEY,
    total_tasks INTEGER DEFAULT 0,
    overdue_tasks INTEGER DEFAULT 0,
    today_tasks INTEGER DEFAULT 0,
    completed_today INTEGER DEFAULT 0,
    by_project JSONB,
    by_priority JSONB,
    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_todoist_snapshots_time ON dashboard_todoist_snapshots(snapshot_at);

-- Kanban board snapshots
CREATE TABLE IF NOT EXISTS dashboard_kanban_snapshots (
    id SERIAL PRIMARY KEY,
    backlog_count INTEGER DEFAULT 0,
    ready_count INTEGER DEFAULT 0,
    in_progress_count INTEGER DEFAULT 0,
    review_count INTEGER DEFAULT 0,
    done_count INTEGER DEFAULT 0,
    total_tasks INTEGER DEFAULT 0,
    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kanban_snapshots_time ON dashboard_kanban_snapshots(snapshot_at);

-- Linear issue snapshots (for future)
CREATE TABLE IF NOT EXISTS dashboard_linear_snapshots (
    id SERIAL PRIMARY KEY,
    total_issues INTEGER DEFAULT 0,
    by_status JSONB,
    by_assignee JSONB,
    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_linear_snapshots_time ON dashboard_linear_snapshots(snapshot_at);

-- Daily aggregates for quick trend queries
CREATE TABLE IF NOT EXISTS dashboard_daily_stats (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    git_total_commits INTEGER DEFAULT 0,
    git_active_repos INTEGER DEFAULT 0,
    git_dirty_repos INTEGER DEFAULT 0,
    todoist_completed INTEGER DEFAULT 0,
    todoist_added INTEGER DEFAULT 0,
    todoist_overdue INTEGER DEFAULT 0,
    kanban_completed INTEGER DEFAULT 0,
    kanban_added INTEGER DEFAULT 0,
    linear_completed INTEGER DEFAULT 0,
    linear_added INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON dashboard_daily_stats(stat_date);

-- Planning sessions (chat-based planning with Jeeves)
CREATE TABLE IF NOT EXISTS planning_sessions (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMP,
    duration_seconds INTEGER,
    initial_context JSONB,  -- tasks, calendar at session start
    final_state JSONB,      -- what was decided/changed
    messages_count INTEGER DEFAULT 0,
    actions_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_planning_sessions_started ON planning_sessions(started_at);

-- Planning actions (individual task changes during planning)
CREATE TABLE IF NOT EXISTS planning_actions (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES planning_sessions(id) ON DELETE CASCADE,
    action_at TIMESTAMP NOT NULL DEFAULT NOW(),
    action_type VARCHAR(50) NOT NULL,  -- 'defer', 'complete', 'prioritize', 'add', 'drop', 'reschedule'
    target_type VARCHAR(50),           -- 'todoist', 'kanban', 'calendar'
    target_id VARCHAR(255),
    target_title TEXT,
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_planning_actions_session ON planning_actions(session_id);
CREATE INDEX IF NOT EXISTS idx_planning_actions_type ON planning_actions(action_type);
CREATE INDEX IF NOT EXISTS idx_planning_actions_time ON planning_actions(action_at);

-- Chat messages in planning sessions
CREATE TABLE IF NOT EXISTS planning_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES planning_sessions(id) ON DELETE CASCADE,
    sent_at TIMESTAMP NOT NULL DEFAULT NOW(),
    role VARCHAR(20) NOT NULL,  -- 'user', 'assistant'
    content TEXT NOT NULL,
    tokens_used INTEGER
);

CREATE INDEX IF NOT EXISTS idx_planning_messages_session ON planning_messages(session_id);

-- Planning daily summaries (for trends)
CREATE TABLE IF NOT EXISTS planning_daily_stats (
    stat_date DATE PRIMARY KEY,
    sessions_count INTEGER DEFAULT 0,
    total_duration_seconds INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    tasks_planned INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    tasks_deferred INTEGER DEFAULT 0,
    tasks_added INTEGER DEFAULT 0,
    planning_accuracy FLOAT,  -- completed / planned
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_planning_daily_date ON planning_daily_stats(stat_date);
