# Health & Fitness Integrations Research

## Apple Health Integration

### Challenge
Apple Health data is stored locally on iPhone and not accessible via API. Need workarounds.

### Possible Approaches

1. **Apple Shortcuts Automation**
   - Create iOS Shortcut that exports daily health summary
   - Trigger via automation at end of day
   - Send data to webhook endpoint
   - Metrics: Steps, Sleep, Active Calories, Heart Rate

2. **Health Export Apps**
   - Apps like "Health Auto Export" can export data on schedule
   - Export to iCloud Drive, then sync to local
   - Parse CSV/JSON files

3. **HealthKit via Swift/Node**
   - Build a small iOS app that reads HealthKit
   - Syncs to backend API
   - Most reliable but requires development

### Recommended: Shortcut + Webhook
```
Shortcut:
1. Get health samples (Steps) for Today
2. Get health samples (Sleep Analysis) for Last Night
3. Get health samples (Active Energy) for Today
4. Create JSON with metrics
5. POST to https://dashboard.local/api/health/sync
```

## Hevy App Integration

### About Hevy
- Popular workout tracking app
- Tracks exercises, sets, reps, weight
- Personal records tracking
- Has mobile app (iOS/Android)

### API Status
- **No official public API** as of research
- Data can be exported manually (CSV)
- Community has reverse-engineered some endpoints

### Possible Approaches

1. **CSV Export Parsing**
   - Export workout history from Hevy
   - Parse CSV to extract:
     - Workout date/time
     - Exercises performed
     - Volume (sets × reps × weight)
     - Personal records

2. **Automation via Shortcuts**
   - Hevy doesn't have direct Shortcuts support
   - Could use screen scraping (unreliable)

3. **Manual Entry + Quick Actions**
   - Dashboard button: "Log Workout"
   - Quick entry: duration, exercises count
   - Award XP based on manual log

### Recommended: Manual + CSV Import
- Quick "Log Workout" button for daily tracking
- Periodic CSV import for detailed analysis
- PR detection from CSV data

## Foodnoms Integration

### About Foodnoms
- Food/nutrition tracking app
- Barcode scanning
- Macro tracking (calories, protein, carbs, fat)
- iOS app with Apple Health sync

### API Status
- **No public API** discovered
- Data syncs to Apple Health (can get from there)
- Export options: Unknown

### Possible Approaches

1. **Via Apple Health**
   - Foodnoms writes to Health app
   - Pull nutrition data from Health export
   - Metrics: Calories, Protein, Carbs, Fat

2. **Manual Entry**
   - Dashboard button: "Log Meal"
   - Quick entry: meal name, rough calories
   - Award XP for logging

### Recommended: Apple Health + Manual
- Get data via Apple Health export
- Manual "Log Meal" for quick XP
- Focus on logging consistency, not precision

## Implementation Plan

### Phase 1: Manual Entry (Quick Wins)
- [ ] "Log Workout" button → Fitness XP
- [ ] "Log Meal" button → Nutrition XP
- [ ] "Log Meditation" button → Mindfulness XP
- [ ] "Log Reading" button → Learning XP

### Phase 2: Apple Shortcut Integration
- [ ] Create health export Shortcut
- [ ] Webhook endpoint for health data
- [ ] Auto-sync steps, sleep, calories
- [ ] Award Health XP automatically

### Phase 3: CSV Import Tools
- [ ] Hevy CSV parser
- [ ] Import workout history
- [ ] PR detection and achievements
- [ ] Historical XP backfill

### Phase 4: Advanced
- [ ] Calendar integration for Social events
- [ ] Monzo integration for Finance tracking
- [ ] Book tracking (Goodreads API?)
- [ ] Meditation app integration

## Quick Win Endpoints

```python
# Manual activity logging
@app.route('/api/life/log', methods=['POST'])
def log_activity():
    """Quick log for manual activities"""
    data = request.get_json()
    activity_type = data.get('type')  # workout, meal, meditation, reading
    duration = data.get('duration')    # minutes
    notes = data.get('notes')
    
    xp_map = {
        'workout': 50,
        'meal': 10,
        'meditation': 25,
        'reading': 15,
        'social': 20
    }
    
    # Award XP and update streak
    ...
```

## Database: Daily Metrics Import

```sql
-- For health data import
UPDATE daily_metrics SET
    steps = %s,
    sleep_hours = %s,
    active_calories = %s,
    resting_hr = %s
WHERE date = CURRENT_DATE;

-- Award XP based on metrics
-- Steps: 10k = 50 XP
-- Sleep 7h+ = 30 XP
-- etc.
```

---

*Research notes for overnight sprint 2026-01-31*
