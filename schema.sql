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

-- Inbox digest snapshots
CREATE TABLE IF NOT EXISTS dashboard_inbox_snapshots (
    id SERIAL PRIMARY KEY,
    account VARCHAR(255) NOT NULL,
    account_name VARCHAR(100),
    total_unread INTEGER DEFAULT 0,
    urgent_count INTEGER DEFAULT 0,
    from_people_count INTEGER DEFAULT 0,
    newsletter_count INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'ok',
    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inbox_snapshots_time ON dashboard_inbox_snapshots(snapshot_at);
CREATE INDEX IF NOT EXISTS idx_inbox_snapshots_account ON dashboard_inbox_snapshots(account);

-- School email snapshots
CREATE TABLE IF NOT EXISTS dashboard_school_snapshots (
    id SERIAL PRIMARY KEY,
    child VARCHAR(100) NOT NULL,
    email_count INTEGER DEFAULT 0,
    action_count INTEGER DEFAULT 0,
    high_urgency INTEGER DEFAULT 0,
    medium_urgency INTEGER DEFAULT 0,
    low_urgency INTEGER DEFAULT 0,
    info_count INTEGER DEFAULT 0,
    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_school_snapshots_time ON dashboard_school_snapshots(snapshot_at);
CREATE INDEX IF NOT EXISTS idx_school_snapshots_child ON dashboard_school_snapshots(child);

-- School email actions log (individual actions for analytics)
CREATE TABLE IF NOT EXISTS dashboard_school_actions (
    id SERIAL PRIMARY KEY,
    child VARCHAR(100),
    action_type VARCHAR(50),  -- 'task', 'event', 'notification'
    urgency VARCHAR(20),
    title TEXT,
    due_date DATE,
    source_email_subject TEXT,
    todoist_task_id VARCHAR(100),
    calendar_event_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_school_actions_time ON dashboard_school_actions(created_at);
CREATE INDEX IF NOT EXISTS idx_school_actions_child ON dashboard_school_actions(child);

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
    inbox_total_unread INTEGER DEFAULT 0,
    inbox_urgent INTEGER DEFAULT 0,
    school_emails_processed INTEGER DEFAULT 0,
    school_actions_created INTEGER DEFAULT 0,
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

-- =============================================================================
-- Days Since Tracking
-- =============================================================================

-- Track "days since" events
CREATE TABLE IF NOT EXISTS days_since_events (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    icon VARCHAR(50) DEFAULT 'calendar',
    category VARCHAR(50) DEFAULT 'personal',
    warning_days INTEGER DEFAULT 7,
    alert_days INTEGER DEFAULT 14,
    last_occurred DATE,
    notes TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- History of occurrences
CREATE TABLE IF NOT EXISTS days_since_history (
    id SERIAL PRIMARY KEY,
    event_code VARCHAR(50) REFERENCES days_since_events(code) ON DELETE CASCADE,
    occurred_at DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert default "days since" events from Nick's list
INSERT INTO days_since_events (code, name, icon, category, warning_days, alert_days, sort_order) VALUES
    ('date_night', 'Date Night', 'heart', 'relationships', 14, 21, 1),
    ('shave', 'Shave', 'scissors', 'self_care', 3, 5, 2),
    ('haircut', 'Haircut', 'scissors', 'self_care', 28, 42, 3),
    ('exercise', 'Exercise', 'dumbbell', 'health', 2, 4, 4),
    ('family_trip', 'Family Trip', 'car', 'relationships', 30, 60, 5),
    ('facetime_grandparents', 'FaceTime Granny & Grandpa', 'video', 'relationships', 7, 14, 6),
    ('message_friends', 'Message Friends', 'message-circle', 'relationships', 7, 14, 7),
    ('day_off', 'Day Off Work', 'coffee', 'self_care', 14, 21, 8)
ON CONFLICT (code) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_days_since_history_event ON days_since_history(event_code);
CREATE INDEX IF NOT EXISTS idx_days_since_history_date ON days_since_history(occurred_at DESC);

-- =============================================================================
-- Configuration Tables (Database-Driven Settings)
-- =============================================================================

-- Activity types for XP logging (replaces hardcoded xp_map)
CREATE TABLE IF NOT EXISTS activity_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    area_code VARCHAR(20) NOT NULL REFERENCES life_areas(code),
    base_xp INTEGER NOT NULL DEFAULT 10,
    icon VARCHAR(50),
    color VARCHAR(20),
    duration_bonus BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default activity types (migrated from hardcoded xp_map)
INSERT INTO activity_types (code, name, description, area_code, base_xp, icon, duration_bonus, sort_order) VALUES
    ('workout', 'Workout', 'General workout or gym session', 'fitness', 50, 'dumbbell', TRUE, 1),
    ('walk', 'Walk', 'Walking or hiking activity', 'fitness', 25, 'footprints', TRUE, 2),
    ('meal', 'Meal Logged', 'Log a healthy meal', 'nutrition', 10, 'utensils', FALSE, 3),
    ('meditation', 'Meditation', 'Mindfulness or meditation session', 'mindfulness', 25, 'brain', TRUE, 4),
    ('journal', 'Journal Entry', 'Writing in journal or diary', 'mindfulness', 15, 'book-open', FALSE, 5),
    ('hobby', 'Hobby Time', 'Creative or hobby activity', 'mindfulness', 30, 'palette', TRUE, 6),
    ('reading', 'Reading', 'Reading books or articles', 'learning', 15, 'book', TRUE, 7),
    ('social', 'Social Activity', 'General social interaction', 'social', 20, 'users', FALSE, 8),
    ('date', 'Date Night', 'Romantic date activity', 'social', 40, 'heart', FALSE, 9),
    ('family', 'Family Time', 'Quality time with family', 'social', 30, 'home', FALSE, 10),
    ('chore', 'Household Chore', 'Completing household tasks', 'finance', 15, 'check-square', FALSE, 11),
    ('finance_task', 'Finance Task', 'Managing finances or budgeting', 'finance', 20, 'wallet', FALSE, 12)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    area_code = EXCLUDED.area_code,
    base_xp = EXCLUDED.base_xp,
    icon = EXCLUDED.icon,
    duration_bonus = EXCLUDED.duration_bonus,
    sort_order = EXCLUDED.sort_order,
    updated_at = NOW();

CREATE INDEX IF NOT EXISTS idx_activity_types_area ON activity_types(area_code);
CREATE INDEX IF NOT EXISTS idx_activity_types_active ON activity_types(active) WHERE active = TRUE;

-- Game configuration (replaces hardcoded Defaults class constants)
CREATE TABLE IF NOT EXISTS game_config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    data_type VARCHAR(20) DEFAULT 'integer',
    description TEXT,
    category VARCHAR(50) DEFAULT 'general',
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default game configuration
INSERT INTO game_config (key, value, data_type, description, category) VALUES
    ('DURATION_BONUS_PER_10MIN', '5', 'integer', 'XP bonus per 10 minutes of activity duration', 'xp'),
    ('DURATION_BONUS_MAX', '25', 'integer', 'Maximum XP bonus from activity duration', 'xp'),
    ('BUDGET_UNDER_XP', '10', 'integer', 'XP awarded for each budget category under target', 'xp'),
    ('DAILY_XP_CAP_DEFAULT', '200', 'integer', 'Default daily XP cap per area', 'xp'),
    ('COMMIT_XP_MULTIPLIER', '5', 'integer', 'XP per git commit', 'xp'),
    ('COMMIT_XP_MAX', '100', 'integer', 'Maximum XP from commits per day', 'xp'),
    ('TASK_COMPLETE_XP', '10', 'integer', 'XP per completed task', 'xp'),
    ('TASK_COMPLETE_XP_MAX', '100', 'integer', 'Maximum XP from tasks per day', 'xp'),
    ('SPRINT_COMPLETE_XP', '100', 'integer', 'XP for completing an overnight sprint', 'xp'),
    ('STREAK_FREEZE_DEFAULT', '3', 'integer', 'Default number of streak freeze tokens', 'streaks'),
    ('LEVEL_FORMULA_VERSION', '1', 'integer', 'Current level calculation formula version', 'levels')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    description = EXCLUDED.description,
    updated_at = NOW();

-- Kanban columns configuration (replaces hardcoded column definitions)
CREATE TABLE IF NOT EXISTS kanban_columns (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    title VARCHAR(100) NOT NULL,
    label VARCHAR(200),
    icon VARCHAR(50),
    color VARCHAR(20),
    wip_limit INTEGER,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert default kanban columns
INSERT INTO kanban_columns (code, title, label, icon, sort_order) VALUES
    ('backlog', 'Backlog', 'Ideas & Future Work', 'inbox', 1),
    ('ready', 'Ready', 'Queued & Prioritized', 'list', 2),
    ('in-progress', 'Active', 'Currently Working', 'play', 3),
    ('review', 'Review', 'Pending Approval', 'eye', 4),
    ('done', 'Complete', 'Finished & Shipped', 'check-circle', 5)
ON CONFLICT (code) DO UPDATE SET
    title = EXCLUDED.title,
    label = EXCLUDED.label,
    icon = EXCLUDED.icon,
    sort_order = EXCLUDED.sort_order;

-- XP calculation rules for automated dashboard XP (replaces frontend JS logic)
CREATE TABLE IF NOT EXISTS xp_rules (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    source VARCHAR(50) NOT NULL,
    area_code VARCHAR(20) NOT NULL REFERENCES life_areas(code),
    rule_type VARCHAR(20) NOT NULL DEFAULT 'count',
    condition JSONB,
    xp_per_unit INTEGER NOT NULL DEFAULT 1,
    max_xp INTEGER,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert default XP rules
INSERT INTO xp_rules (code, name, description, source, area_code, rule_type, condition, xp_per_unit, max_xp) VALUES
    ('commits_today', 'Daily Commits', 'XP for git commits made today', 'git', 'work', 'count', '{"field": "commit_count"}', 5, 100),
    ('tasks_completed', 'Tasks Completed', 'XP for completing Todoist tasks', 'todoist', 'work', 'count', '{"field": "completed_today"}', 10, 100),
    ('sprint_complete', 'Sprint Complete', 'XP for completing an overnight sprint', 'sprint', 'work', 'boolean', '{"field": "status", "value": "completed"}', 100, 100),
    ('health_steps', 'Steps Goal', 'XP for meeting step goal', 'health', 'health', 'threshold', '{"field": "steps", "threshold": 10000}', 25, 25),
    ('health_exercise', 'Exercise Goal', 'XP for meeting exercise goal', 'health', 'fitness', 'threshold', '{"field": "exercise_minutes", "threshold": 30}', 30, 30),
    ('health_stand', 'Stand Goal', 'XP for meeting stand goal', 'health', 'health', 'threshold', '{"field": "stand_hours", "threshold": 12}', 15, 15),
    ('budget_under', 'Budget Adherence', 'XP for staying under budget', 'monzo', 'finance', 'count', '{"field": "budgets_under"}', 10, 100)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    xp_per_unit = EXCLUDED.xp_per_unit,
    max_xp = EXCLUDED.max_xp;

CREATE INDEX IF NOT EXISTS idx_xp_rules_source ON xp_rules(source);
CREATE INDEX IF NOT EXISTS idx_xp_rules_active ON xp_rules(active) WHERE active = TRUE;

-- Priority levels configuration
CREATE TABLE IF NOT EXISTS priority_levels (
    id SERIAL PRIMARY KEY,
    level INTEGER UNIQUE NOT NULL,
    code VARCHAR(10) NOT NULL,
    name VARCHAR(50) NOT NULL,
    color VARCHAR(20),
    emoji VARCHAR(10),
    sort_order INTEGER DEFAULT 0
);

-- Insert default priority levels (Todoist/Linear style)
INSERT INTO priority_levels (level, code, name, color, emoji, sort_order) VALUES
    (4, 'p1', 'Urgent', '#ef4444', '🔴', 1),
    (3, 'p2', 'High', '#f97316', '🟠', 2),
    (2, 'p3', 'Medium', '#3b82f6', '🔵', 3),
    (1, 'p4', 'Low', '#6b7280', '⚪', 4)
ON CONFLICT (level) DO UPDATE SET
    name = EXCLUDED.name,
    color = EXCLUDED.color;

-- =============================================================================
-- Email Automation Tables
-- =============================================================================

-- Notification history for tracking all sent notifications
CREATE TABLE IF NOT EXISTS notification_history (
    id SERIAL PRIMARY KEY,
    channel VARCHAR(50) NOT NULL,      -- 'telegram', 'slack'
    source VARCHAR(50) NOT NULL,       -- 'school', 'inbox', 'combined'
    title TEXT NOT NULL,
    body TEXT,
    priority VARCHAR(20) NOT NULL,     -- 'urgent', 'digest', 'info'
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    message_id VARCHAR(100)            -- External message ID if available
);

CREATE INDEX IF NOT EXISTS idx_notification_history_channel ON notification_history(channel);
CREATE INDEX IF NOT EXISTS idx_notification_history_source ON notification_history(source);
CREATE INDEX IF NOT EXISTS idx_notification_history_sent ON notification_history(sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_notification_history_priority ON notification_history(priority);

-- Scheduled job run tracking
CREATE TABLE IF NOT EXISTS scheduled_job_runs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(100) NOT NULL,      -- 'school_email', 'inbox_digest', 'daily_combined'
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- 'running', 'success', 'failed'
    trigger_type VARCHAR(20),          -- 'scheduled', 'manual', 'http'
    result JSONB,                       -- Job-specific result data
    error_message TEXT,
    duration_seconds DECIMAL(10,2)
);

CREATE INDEX IF NOT EXISTS idx_job_runs_job ON scheduled_job_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_job_runs_started ON scheduled_job_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_runs_status ON scheduled_job_runs(status);

-- Email fetch operation logs (detailed IMAP operation tracking)
CREATE TABLE IF NOT EXISTS email_fetch_logs (
    id SERIAL PRIMARY KEY,
    account VARCHAR(255) NOT NULL,
    operation VARCHAR(50) NOT NULL,      -- 'auth', 'fetch', 'error', 'timeout', etc.
    details TEXT,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_email_fetch_logs_account ON email_fetch_logs(account);
CREATE INDEX IF NOT EXISTS idx_email_fetch_logs_time ON email_fetch_logs(logged_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_fetch_logs_success ON email_fetch_logs(success);

-- Detailed inbox message cache (optional - for analytics)
CREATE TABLE IF NOT EXISTS inbox_message_cache (
    id SERIAL PRIMARY KEY,
    account VARCHAR(255) NOT NULL,
    message_id VARCHAR(255) NOT NULL,
    subject TEXT,
    from_name VARCHAR(255),
    from_email VARCHAR(255),
    date_header VARCHAR(100),
    is_urgent BOOLEAN DEFAULT FALSE,
    is_from_person BOOLEAN DEFAULT FALSE,
    body_text TEXT,                       -- Full email body for processing
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account, message_id)
);

CREATE INDEX IF NOT EXISTS idx_inbox_cache_account ON inbox_message_cache(account);
CREATE INDEX IF NOT EXISTS idx_inbox_cache_seen ON inbox_message_cache(last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_inbox_cache_body_fts
    ON inbox_message_cache USING gin(to_tsvector('english', body_text));

-- Email attachments with extracted content
CREATE TABLE IF NOT EXISTS email_attachments (
    id SERIAL PRIMARY KEY,
    account VARCHAR(255) NOT NULL,
    message_id VARCHAR(255) NOT NULL,
    filename VARCHAR(500) NOT NULL,
    content_type VARCHAR(100),
    size_bytes INTEGER,
    extracted_text TEXT,              -- PDF/text content extracted
    extraction_status VARCHAR(20),    -- 'success', 'failed', 'skipped'
    extraction_error TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account, message_id, filename)
);

CREATE INDEX IF NOT EXISTS idx_attachments_account ON email_attachments(account);
CREATE INDEX IF NOT EXISTS idx_attachments_message ON email_attachments(message_id);
CREATE INDEX IF NOT EXISTS idx_attachments_type ON email_attachments(content_type);
CREATE INDEX IF NOT EXISTS idx_attachments_text ON email_attachments USING gin(to_tsvector('english', extracted_text));
