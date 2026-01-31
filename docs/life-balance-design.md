# Life Balance Dashboard - Design Document

## Overview
Transform the Project Dashboard into a holistic Life Balance dashboard with gamification, health integrations, and visualizations.

## Life Areas (8 Pillars)

| Area | Description | Data Sources | XP Activities |
|------|-------------|--------------|---------------|
| **Work** | Productivity & career | Git, Linear, Todoist | Tasks completed, commits, sprints |
| **Health** | Physical wellbeing | Apple Health, Sleep | Steps, sleep hours, resting HR |
| **Fitness** | Exercise & strength | Hevy, Apple Health | Workouts, PRs, consistency |
| **Nutrition** | Diet & hydration | Foodnoms | Meals logged, macros, calories |
| **Learning** | Knowledge & growth | Books, courses, notes | Pages read, courses completed |
| **Social** | Relationships | Calendar, messages | Events attended, connections |
| **Finance** | Money management | Monzo (existing) | Savings, budget adherence |
| **Mindfulness** | Mental health | Meditation apps | Sessions, streak days |

## Gamification System

### XP Calculation
- Each area has independent XP
- Total Life XP = sum of all areas
- Daily XP cap per area to prevent burnout gaming

### XP Sources
```yaml
work:
  task_complete: 10xp
  commit: 5xp
  sprint_complete: 100xp
  pr_merged: 25xp

health:
  steps_10k: 50xp
  sleep_7h: 30xp
  low_resting_hr: 20xp

fitness:
  workout_complete: 50xp
  personal_record: 100xp
  streak_day: 10xp

nutrition:
  meal_logged: 10xp
  protein_goal: 20xp
  calorie_target: 15xp

learning:
  book_pages_10: 15xp
  course_lesson: 25xp
  note_created: 10xp
```

### Levels
| Level | XP Required | Title |
|-------|-------------|-------|
| 1 | 0 | Novice |
| 5 | 500 | Apprentice |
| 10 | 2,000 | Journeyman |
| 20 | 10,000 | Expert |
| 50 | 50,000 | Master |
| 100 | 200,000 | Legend |

### Achievements
- **Early Bird**: Complete task before 9am (50xp)
- **Night Owl**: Commit after midnight (25xp)
- **Marathon**: 10k+ steps (75xp)
- **Iron Will**: 7-day workout streak (200xp)
- **Bookworm**: Finish a book (150xp)
- **Zen Master**: 30-day meditation streak (500xp)

### Streaks
- Track consecutive days for each activity
- Bonus XP multiplier: streak_days * 0.1 (max 2x)
- Streak freeze tokens (use to preserve streak on miss)

## Visualizations

### Progress Rings (Apple Watch style)
- Outer ring: Daily goal progress
- Inner rings: Sub-metrics
- Color-coded by area

### Radar Chart (Life Balance)
- 8 axes for 8 life areas
- Percentage fill based on weekly goals
- Target overlay for ideal balance

### Heat Maps
- GitHub-style contribution graph
- Show activity density by day
- Color intensity = XP earned

### Sparklines
- 7-day trends for each metric
- Inline in cards

## Database Schema

```sql
-- Life areas and goals
CREATE TABLE life_areas (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    icon VARCHAR(50),
    color VARCHAR(20),
    daily_xp_cap INTEGER DEFAULT 200,
    created_at TIMESTAMP DEFAULT NOW()
);

-- User XP and levels
CREATE TABLE life_xp (
    id SERIAL PRIMARY KEY,
    area_id INTEGER REFERENCES life_areas(id),
    date DATE NOT NULL,
    xp_earned INTEGER DEFAULT 0,
    activities JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(area_id, date)
);

-- Achievements
CREATE TABLE achievements (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(50),
    xp_reward INTEGER DEFAULT 0,
    criteria JSONB
);

-- User achievements
CREATE TABLE user_achievements (
    id SERIAL PRIMARY KEY,
    achievement_id INTEGER REFERENCES achievements(id),
    earned_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(achievement_id)
);

-- Streaks
CREATE TABLE streaks (
    id SERIAL PRIMARY KEY,
    activity VARCHAR(50) NOT NULL UNIQUE,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_activity_date DATE,
    freeze_tokens INTEGER DEFAULT 3
);

-- Daily metrics (aggregated from integrations)
CREATE TABLE daily_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    steps INTEGER,
    sleep_hours DECIMAL(4,2),
    calories INTEGER,
    protein INTEGER,
    workouts INTEGER,
    tasks_completed INTEGER,
    commits INTEGER,
    pages_read INTEGER,
    meditation_minutes INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Integration Strategy

### Apple Health (via Shortcuts/Export)
- Use Apple Shortcuts to export daily summary
- Webhook or file drop to ingest
- Metrics: steps, sleep, heart rate, workouts

### Hevy (API or Export)
- Check for official API
- Fallback: CSV export parsing
- Metrics: workouts, exercises, PRs, volume

### Foodnoms (Export)
- Likely CSV/JSON export
- Metrics: meals, calories, macros

### Calendar (Google)
- Already have `gog` skill
- Metrics: events, social gatherings

### Gmail (via gog)
- Already integrated
- Metrics: emails processed, response time

## UI Components

### Life Tab Layout
```
┌─────────────────────────────────────────────────────────────┐
│  🎮 LIFE DASHBOARD                          Level 12 · 4,250 XP │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────┐  ┌─────────────────────────────┐  │
│  │   PROGRESS RINGS    │  │      LIFE BALANCE RADAR     │  │
│  │      (Today)        │  │         (This Week)         │  │
│  │   ◉◉◉◉◉◉◉◉        │  │                             │  │
│  │   Steps | Workout   │  │     Work    Health          │  │
│  │   Sleep | Focus     │  │        ╲   ╱                │  │
│  └─────────────────────┘  │         ╲ ╱                 │  │
│                           │    Learn ─●─ Fitness        │  │
│  ┌─────────────────────┐  │         ╱ ╲                 │  │
│  │    TODAY'S XP       │  │        ╱   ╲                │  │
│  │    +125 XP          │  │   Social   Nutrition        │  │
│  │   ▓▓▓▓▓▓▓░░░ 62%   │  └─────────────────────────────┘  │
│  └─────────────────────┘                                    │
│                                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │ 💼 Work │ │ 🏃 Fit  │ │ 📚 Learn│ │ 🧘 Mind │          │
│  │ 45/100  │ │ 80/100  │ │ 30/100  │ │ 0/50    │          │
│  │ ████░░  │ │ ████████│ │ ███░░░  │ │ ░░░░░░  │          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
│                                                             │
│  🔥 STREAKS                        🏆 RECENT ACHIEVEMENTS   │
│  Workout: 5 days                   ⭐ Early Bird (today)    │
│  Meditation: 0 days                ⭐ Iron Will (yesterday)  │
│  Reading: 12 days                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Core UI (Tonight)
- [x] Life tab HTML structure
- [x] Progress rings component
- [x] XP display with level
- [x] Area cards with progress bars
- [ ] Mock data for testing

### Phase 2: Database & API
- [ ] Create database tables
- [ ] Life XP API endpoints
- [ ] Achievement system

### Phase 3: Visualizations
- [ ] Progress rings with Canvas/SVG
- [ ] Radar chart with Chart.js
- [ ] Heat map component
- [ ] Sparklines

### Phase 4: Integrations
- [ ] Apple Health shortcut
- [ ] Hevy research
- [ ] Foodnoms research
- [ ] Calendar events for social

### Phase 5: Gamification Polish
- [ ] Achievement notifications
- [ ] Level up animations
- [ ] Streak warnings
- [ ] Daily summary

---

*Design document for overnight sprint 2026-01-31*
