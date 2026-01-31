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

-- Linear issue snapshots
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

-- =============================================================================
-- Overnight Sprint Tables
-- =============================================================================

-- Overnight sprints (one per night)
CREATE TABLE IF NOT EXISTS overnight_sprints (
    id SERIAL PRIMARY KEY,
    sprint_date DATE NOT NULL UNIQUE,
    task_id VARCHAR(100),
    task_title TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, in-progress, completed, blocked
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    
    -- Quality gates (stored as individual booleans for easy querying)
    gate_tests_passing BOOLEAN DEFAULT FALSE,
    gate_no_lint_errors BOOLEAN DEFAULT FALSE,
    gate_docs_updated BOOLEAN DEFAULT FALSE,
    gate_committed BOOLEAN DEFAULT FALSE,
    gate_self_validated BOOLEAN DEFAULT FALSE,
    gate_happy_path BOOLEAN DEFAULT FALSE,
    gate_edge_cases BOOLEAN DEFAULT FALSE,
    gate_pal_reviewed BOOLEAN DEFAULT FALSE,
    
    -- Counts
    tasks_completed INTEGER DEFAULT 0,
    tasks_total INTEGER DEFAULT 0,
    gates_passed INTEGER DEFAULT 0,
    
    -- Block info
    block_reason TEXT,
    
    -- Source file reference
    obsidian_path TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_overnight_sprints_date ON overnight_sprints(sprint_date DESC);
CREATE INDEX IF NOT EXISTS idx_overnight_sprints_status ON overnight_sprints(status);

-- Overnight sprint activity log
CREATE TABLE IF NOT EXISTS overnight_activity (
    id SERIAL PRIMARY KEY,
    sprint_id INTEGER REFERENCES overnight_sprints(id) ON DELETE CASCADE,
    activity_at TIMESTAMP NOT NULL,
    activity_type VARCHAR(50) NOT NULL,  -- start, progress, complete, decision, block
    what TEXT NOT NULL,
    why TEXT,
    outcome TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_overnight_activity_sprint ON overnight_activity(sprint_id);
CREATE INDEX IF NOT EXISTS idx_overnight_activity_time ON overnight_activity(activity_at);

-- Overnight sprint decisions
CREATE TABLE IF NOT EXISTS overnight_decisions (
    id SERIAL PRIMARY KEY,
    sprint_id INTEGER REFERENCES overnight_sprints(id) ON DELETE CASCADE,
    decided_at TIMESTAMP NOT NULL,
    question TEXT NOT NULL,
    context TEXT,
    decision TEXT NOT NULL,
    rationale TEXT,
    confidence VARCHAR(20),  -- high, medium, low
    pal_responses JSONB,
    consensus TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_overnight_decisions_sprint ON overnight_decisions(sprint_id);

-- Overnight sprint deviations
CREATE TABLE IF NOT EXISTS overnight_deviations (
    id SERIAL PRIMARY KEY,
    sprint_id INTEGER REFERENCES overnight_sprints(id) ON DELETE CASCADE,
    deviated_at TIMESTAMP NOT NULL,
    original_scope TEXT,
    deviation TEXT NOT NULL,
    reason TEXT,
    flagged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_overnight_deviations_sprint ON overnight_deviations(sprint_id);

-- =============================================================================
-- Life Balance & Gamification Tables
-- =============================================================================

-- Life areas (8 pillars)
CREATE TABLE IF NOT EXISTS life_areas (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(50) NOT NULL,
    icon VARCHAR(50),
    color VARCHAR(20),
    daily_xp_cap INTEGER DEFAULT 200,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert default life areas
INSERT INTO life_areas (code, name, icon, color, daily_xp_cap, sort_order) VALUES
    ('work', 'Work', 'briefcase', '#3b82f6', 200, 1),
    ('health', 'Health', 'heart', '#ef4444', 150, 2),
    ('fitness', 'Fitness', 'dumbbell', '#f97316', 200, 3),
    ('nutrition', 'Nutrition', 'apple', '#22c55e', 150, 4),
    ('learning', 'Learning', 'book-open', '#8b5cf6', 150, 5),
    ('social', 'Social', 'users', '#ec4899', 100, 6),
    ('finance', 'Finance', 'wallet', '#14b8a6', 100, 7),
    ('mindfulness', 'Mindfulness', 'brain', '#6366f1', 100, 8)
ON CONFLICT (code) DO NOTHING;

-- Daily XP earned per area
CREATE TABLE IF NOT EXISTS life_xp (
    id SERIAL PRIMARY KEY,
    area_code VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    xp_earned INTEGER DEFAULT 0,
    activities JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(area_code, date)
);

CREATE INDEX IF NOT EXISTS idx_life_xp_date ON life_xp(date DESC);
CREATE INDEX IF NOT EXISTS idx_life_xp_area ON life_xp(area_code);

-- Total XP and level (cached for performance)
CREATE TABLE IF NOT EXISTS life_totals (
    id SERIAL PRIMARY KEY,
    area_code VARCHAR(20) NOT NULL UNIQUE,
    total_xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default totals
INSERT INTO life_totals (area_code, total_xp, level) VALUES
    ('work', 0, 1), ('health', 0, 1), ('fitness', 0, 1), ('nutrition', 0, 1),
    ('learning', 0, 1), ('social', 0, 1), ('finance', 0, 1), ('mindfulness', 0, 1),
    ('total', 0, 1)
ON CONFLICT (area_code) DO NOTHING;

-- Achievements definitions
CREATE TABLE IF NOT EXISTS achievements (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(50),
    xp_reward INTEGER DEFAULT 0,
    area_code VARCHAR(20),
    criteria JSONB,
    rarity VARCHAR(20) DEFAULT 'common',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert some default achievements
INSERT INTO achievements (code, name, description, icon, xp_reward, area_code, rarity) VALUES
    ('early_bird', 'Early Bird', 'Complete a task before 9am', 'sunrise', 50, 'work', 'common'),
    ('night_owl', 'Night Owl', 'Make a commit after midnight', 'moon', 25, 'work', 'common'),
    ('marathon', 'Marathon', 'Walk 10,000+ steps in a day', 'footprints', 75, 'health', 'common'),
    ('iron_will', 'Iron Will', 'Maintain a 7-day workout streak', 'trophy', 200, 'fitness', 'rare'),
    ('bookworm', 'Bookworm', 'Finish reading a book', 'book', 150, 'learning', 'uncommon'),
    ('zen_master', 'Zen Master', '30-day meditation streak', 'leaf', 500, 'mindfulness', 'epic'),
    ('first_commit', 'First Commit', 'Make your first commit', 'git-commit', 25, 'work', 'common'),
    ('sprint_complete', 'Sprint Complete', 'Complete an overnight sprint', 'rocket', 100, 'work', 'uncommon'),
    ('social_butterfly', 'Social Butterfly', 'Attend 5 social events in a week', 'party-popper', 100, 'social', 'uncommon'),
    ('meal_prep', 'Meal Prep', 'Log all meals for a week', 'utensils', 75, 'nutrition', 'uncommon')
ON CONFLICT (code) DO NOTHING;

-- User earned achievements
CREATE TABLE IF NOT EXISTS user_achievements (
    id SERIAL PRIMARY KEY,
    achievement_code VARCHAR(50) NOT NULL UNIQUE,
    earned_at TIMESTAMP DEFAULT NOW(),
    notified BOOLEAN DEFAULT FALSE
);

-- Streaks tracking
CREATE TABLE IF NOT EXISTS streaks (
    id SERIAL PRIMARY KEY,
    activity VARCHAR(50) NOT NULL UNIQUE,
    area_code VARCHAR(20),
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_activity_date DATE,
    freeze_tokens INTEGER DEFAULT 3,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default streaks to track
INSERT INTO streaks (activity, area_code, current_streak) VALUES
    ('workout', 'fitness', 0),
    ('meditation', 'mindfulness', 0),
    ('reading', 'learning', 0),
    ('meal_logging', 'nutrition', 0),
    ('task_complete', 'work', 0),
    ('steps_10k', 'health', 0)
ON CONFLICT (activity) DO NOTHING;

-- Daily aggregated metrics from all sources
CREATE TABLE IF NOT EXISTS daily_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    -- Health metrics
    steps INTEGER,
    sleep_hours DECIMAL(4,2),
    resting_hr INTEGER,
    active_calories INTEGER,
    -- Fitness metrics
    workouts INTEGER DEFAULT 0,
    workout_minutes INTEGER,
    personal_records INTEGER DEFAULT 0,
    -- Nutrition metrics
    calories_consumed INTEGER,
    protein_grams INTEGER,
    meals_logged INTEGER DEFAULT 0,
    -- Work metrics
    tasks_completed INTEGER DEFAULT 0,
    commits INTEGER DEFAULT 0,
    sprints_completed INTEGER DEFAULT 0,
    -- Learning metrics
    pages_read INTEGER DEFAULT 0,
    courses_progress INTEGER DEFAULT 0,
    notes_created INTEGER DEFAULT 0,
    -- Mindfulness metrics
    meditation_minutes INTEGER DEFAULT 0,
    journal_entries INTEGER DEFAULT 0,
    -- Social metrics
    events_attended INTEGER DEFAULT 0,
    messages_sent INTEGER DEFAULT 0,
    -- Finance metrics
    budget_adherence DECIMAL(5,2),
    savings_rate DECIMAL(5,2),
    -- Meta
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(date DESC);

-- Goals per area (weekly/daily targets)
CREATE TABLE IF NOT EXISTS life_goals (
    id SERIAL PRIMARY KEY,
    area_code VARCHAR(20) NOT NULL,
    metric VARCHAR(50) NOT NULL,
    target_value INTEGER NOT NULL,
    period VARCHAR(20) DEFAULT 'daily',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(area_code, metric, period)
);

-- Insert default goals
INSERT INTO life_goals (area_code, metric, target_value, period) VALUES
    ('health', 'steps', 10000, 'daily'),
    ('health', 'sleep_hours', 7, 'daily'),
    ('fitness', 'workouts', 4, 'weekly'),
    ('fitness', 'workout_minutes', 30, 'daily'),
    ('nutrition', 'meals_logged', 3, 'daily'),
    ('nutrition', 'protein_grams', 150, 'daily'),
    ('learning', 'pages_read', 20, 'daily'),
    ('mindfulness', 'meditation_minutes', 10, 'daily'),
    ('work', 'tasks_completed', 5, 'daily'),
    ('social', 'events_attended', 2, 'weekly')
ON CONFLICT (area_code, metric, period) DO NOTHING;
