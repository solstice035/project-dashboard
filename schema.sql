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
