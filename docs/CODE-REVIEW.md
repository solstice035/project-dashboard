# Project Dashboard - Code Review

**Reviewer:** Jeeves  
**Date:** 2026-01-30  
**Scope:** Full end-to-end review of server.py, database.py, index.html, and tests

---

## Executive Summary

| Category | Score | Notes |
|----------|-------|-------|
| **Code Quality** | 8/10 | Well-structured, consistent patterns |
| **Security** | 7/10 | Good basics, some improvements needed |
| **Error Handling** | 8/10 | Comprehensive, graceful degradation |
| **Performance** | 7/10 | Good parallelization, some optimization opportunities |
| **Maintainability** | 8/10 | Clear separation, good documentation |
| **Test Coverage** | 8/10 | 80% coverage, good scenarios |

**Overall: 7.7/10** - Production-ready with minor improvements recommended.

---

## 1. Code Quality

### ✅ Strengths

**Clear Module Organization**
```
server.py    - API routes and data fetchers
database.py  - All database operations
index.html   - Self-contained frontend
```

**Consistent Patterns**
- All fetchers follow the same return structure: `{status, data, error}`
- Consistent error handling with try/except blocks
- Uniform JSON response format

**Good Use of Type Hints**
```python
def fetch_git_repos() -> dict[str, Any]:
def get_git_trends(days: int = 30) -> list[dict]:
```

**Well-Documented Functions**
```python
def fetch_weather() -> dict:
    """Fetch current weather."""
```

### ⚠️ Issues & Fixes

**Issue 1: Magic Strings**
```python
# Current
if result['status'] == 'ok':
col = task.get('column', 'unknown')

# Recommended: Use constants
class Status:
    OK = 'ok'
    ERROR = 'error'
    NOT_CONFIGURED = 'not_configured'

class KanbanColumn:
    BACKLOG = 'backlog'
    READY = 'ready'
    IN_PROGRESS = 'in-progress'
```

**Issue 2: Hardcoded Values**
```python
# Current (server.py line 570)
resp = requests.get('https://wttr.in/London?format=j1', timeout=5)

# Recommended: Move to config
config['weather']['location'] = 'London'
```

**Issue 3: Long Functions**
`fetch_git_repos()` is 80+ lines. Consider breaking into smaller functions:
```python
def _scan_repo_branch(repo_dir: Path) -> Optional[str]
def _get_repo_commits(repo_dir: Path, since: str) -> list[str]
def _check_repo_status(repo_dir: Path) -> dict
```

---

## 2. Security

### ✅ Strengths

**No Secret Exposure in API**
```python
@app.route('/api/config')
def get_config_status():
    # Returns configured: bool, not actual tokens
    return jsonify({
        'todoist': {'configured': bool(config['todoist'].get('token'))}
    })
```

**Config File Gitignored**
- `config.yaml` contains secrets
- `config.example.yaml` provided as template

**Local-Only by Default**
- Gateway token for WebSocket auth
- No CORS enabled by default

### ⚠️ Issues & Fixes

**Issue 1: SQL Injection Risk (Low)**
```python
# Current (server.py line 812)
cur.execute("""
    SELECT id, started_at, ended_at, duration_seconds...
    FROM planning_sessions
    WHERE started_at > NOW() - INTERVAL '%s days'
""", (days,))
```
While parameterized, the `%s` inside `INTERVAL` string is unconventional.

**Fix:**
```python
# Safer: Use timedelta calculation in Python
from_date = datetime.now() - timedelta(days=days)
cur.execute("""
    SELECT ... FROM planning_sessions
    WHERE started_at > %s
""", (from_date,))
```

**Issue 2: No Rate Limiting**
```python
# Add rate limiting for production
from flask_limiter import Limiter
limiter = Limiter(app, key_func=get_remote_address)

@app.route('/api/dashboard')
@limiter.limit("30 per minute")
def get_dashboard():
```

**Issue 3: Gateway Token Exposed in Frontend**
```javascript
// Current (index.html)
const DEFAULT_GATEWAY_TOKEN = 'f2f8d0074aa8f2bf972bfa072ebdb45cb54d00fd8337f3a7';
```
**Risk:** Token visible in browser source code.

**Fix:** Proxy through backend or use environment-based injection:
```javascript
const DEFAULT_GATEWAY_TOKEN = window.__GATEWAY_TOKEN__ || '';
// Inject via server-side template
```

**Issue 4: No Input Validation on Planning Endpoints**
```python
# Current
data = request.get_json() or {}
action = data.get('action')

# Recommended: Add schema validation
from marshmallow import Schema, fields, validate

class PlanningSessionSchema(Schema):
    action = fields.Str(required=True, validate=validate.OneOf(['start', 'end']))
    session_id = fields.Int()
```

---

## 3. Error Handling

### ✅ Strengths

**Graceful Degradation**
```python
# Kanban falls back to PostgreSQL when API unavailable
try:
    resp = requests.get(api_url, timeout=3)
except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
    logger.info("Kanban API unavailable, falling back to PostgreSQL")
```

**Comprehensive Logging**
```python
logger.error(f"Failed to store git snapshot: {e}")
logger.warning(f"Weather fetch failed: {e}")
```

**Consistent Error Response Format**
```python
return jsonify({'error': 'Database not available'}), 503
return jsonify({'error': str(e)}), 500
```

### ⚠️ Issues & Fixes

**Issue 1: Bare Exception Catching**
```python
# Current (multiple places)
except Exception as e:
    result['status'] = 'error'

# Recommended: Be more specific
except (requests.RequestException, json.JSONDecodeError) as e:
except psycopg2.Error as e:
```

**Issue 2: Missing Connection Cleanup in Some Paths**
```python
# Current pattern (server.py line 700)
try:
    conn = psycopg2.connect(...)
    # ... operations
finally:
    if 'conn' in locals():
        conn.close()

# Recommended: Use context manager consistently
with get_connection() as conn:
    cur = conn.cursor()
    # ... operations
```

**Issue 3: No Retry Logic for Transient Failures**
```python
# Recommended: Add tenacity for retries
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1))
def fetch_todoist():
    ...
```

---

## 4. Performance

### ✅ Strengths

**Parallel Data Fetching**
```python
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {
        executor.submit(fetch_git_repos): 'git',
        executor.submit(fetch_todoist): 'todoist',
        executor.submit(fetch_kanban): 'kanban',
        executor.submit(fetch_linear): 'linear'
    }
```

**Timeouts on All External Calls**
```python
resp = requests.get(api_url, timeout=3)
subprocess.run(..., timeout=5)
```

**Database Connection Pooling Ready**
```python
# Current: Single connections
# database.py ready for pooling upgrade
```

### ⚠️ Issues & Fixes

**Issue 1: No Response Caching**
```python
# Recommended: Add caching for expensive operations
from functools import lru_cache
from cachetools import TTLCache

weather_cache = TTLCache(maxsize=1, ttl=300)  # 5 min cache

def fetch_weather():
    if 'data' in weather_cache:
        return weather_cache['data']
    # ... fetch
    weather_cache['data'] = result
    return result
```

**Issue 2: N+1 Query Potential in Git Scanning**
```python
# Current: Sequential subprocess calls per repo
for repo_dir in expanded_path.iterdir():
    # 4 subprocess calls per repo
    subprocess.run(['git', '-C', str(repo_dir), 'branch', ...])
    subprocess.run(['git', '-C', str(repo_dir), 'log', ...])
    subprocess.run(['git', '-C', str(repo_dir), 'status', ...])
    subprocess.run(['git', '-C', str(repo_dir), 'rev-list', ...])

# Recommended: Batch or parallelize
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(scan_single_repo, repo) for repo in repos]
```

**Issue 3: Frontend Loads All Data on Tab Switch**
```javascript
// Current: Loads standup data every time tab is clicked
if (tabId === 'standup') loadStandup();

// Recommended: Cache and check freshness
const CACHE_TTL = 60000; // 1 minute
let standupCache = { data: null, timestamp: 0 };

if (tabId === 'standup') {
    if (Date.now() - standupCache.timestamp > CACHE_TTL) {
        loadStandup();
    }
}
```

**Issue 4: Large Payload Responses**
```python
# Current: Returns all tasks
'tasks': fetch_todoist().get('tasks', [])[:20]

# Recommended: Add pagination
@app.route('/api/tasks')
def get_tasks():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    # ... paginate
```

---

## 5. Maintainability

### ✅ Strengths

**Self-Documenting Code**
```python
def get_standup():
    """Get morning standup data - tasks, calendar, weather, projects."""
```

**Separation of Concerns**
- `server.py`: HTTP layer
- `database.py`: Data persistence
- `index.html`: Presentation

**Comprehensive Documentation**
- README.md with quick start
- USER-GUIDE.md for end users
- TECHNICAL.md for developers
- DESIGN.md for UI/UX
- ARCHITECTURE.md with diagrams

### ⚠️ Issues & Fixes

**Issue 1: Monolithic index.html (1400+ lines)**
```html
<!-- Current: Everything in one file -->

<!-- Recommended: Split into modules -->
<script src="js/api.js"></script>
<script src="js/dashboard.js"></script>
<script src="js/planning.js"></script>
<script src="js/charts.js"></script>
```

**Issue 2: No API Versioning**
```python
# Current
@app.route('/api/dashboard')

# Recommended
@app.route('/api/v1/dashboard')
```

**Issue 3: Database Schema Migrations**
```sql
-- Current: Manual SQL execution
-- Recommended: Use Alembic for migrations

# alembic.ini
# alembic/versions/001_initial.py
```

**Issue 4: Missing Health Check Details**
```python
# Current
return jsonify({'status': 'ok', 'timestamp': ...})

# Recommended: Include dependency health
return jsonify({
    'status': 'ok',
    'dependencies': {
        'database': check_db_health(),
        'kanban': check_kanban_health(),
        'todoist': check_todoist_health()
    }
})
```

---

## 6. Test Coverage Analysis

### Current Coverage: 80%

**Well-Tested Areas:**
- ✅ All API endpoints
- ✅ Error scenarios (503, 400, 500)
- ✅ Input validation
- ✅ Database unavailable fallbacks

**Gaps Identified:**

| Area | Coverage | Recommendation |
|------|----------|----------------|
| WebSocket chat | 0% | Add mock WebSocket tests |
| Frontend JS | 0% | Add Jest/Vitest tests |
| Linear GraphQL | Partial | Add response parsing tests |
| Edge cases | Partial | Add boundary condition tests |

### Recommended Additional Tests

```python
# test_edge_cases.py

def test_empty_git_scan_path():
    """Handle non-existent scan paths gracefully."""

def test_todoist_empty_response():
    """Handle empty task list."""

def test_planning_session_timeout():
    """Handle session that was never ended."""

def test_concurrent_planning_sessions():
    """Handle multiple simultaneous sessions."""

def test_very_long_task_content():
    """Handle task content over 10KB."""
```

---

## 7. Frontend Review

### ✅ Strengths

- Clean dark mode aesthetic
- Responsive grid layout
- Consistent component styling
- Good use of CSS custom properties

### ⚠️ Issues & Fixes

**Issue 1: No Error Boundary for WebSocket**
```javascript
// Current: Basic error handling
ws.onerror = (error) => {
    console.error('Gateway error:', error);
};

// Recommended: Auto-reconnect with backoff
let reconnectAttempts = 0;
const MAX_RECONNECT = 5;

ws.onclose = () => {
    if (reconnectAttempts < MAX_RECONNECT) {
        setTimeout(() => {
            reconnectAttempts++;
            connectGateway();
        }, Math.pow(2, reconnectAttempts) * 1000);
    }
};
```

**Issue 2: Memory Leak in Charts**
```javascript
// Current: Charts may not be destroyed
let gitChart = null;

// Recommended: Destroy before recreating
if (gitChart) {
    gitChart.destroy();
}
gitChart = new Chart(ctx, config);
```

**Issue 3: No Loading States for Quick Actions**
```javascript
// Recommended: Disable during processing
function sendQuickAction(action) {
    document.querySelectorAll('.quick-action').forEach(b => b.disabled = true);
    // ... send
    // Re-enable on response
}
```

**Issue 4: XSS Risk in Dynamic Content**
```javascript
// Current: Direct HTML insertion
content.innerHTML = data.tasks.map(t => `<div>${t.content}</div>`).join('');

// Recommended: Escape user content
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
content.innerHTML = data.tasks.map(t => `<div>${escapeHtml(t.content)}</div>`).join('');
```

---

## 8. Recommendations Summary

### 🔴 High Priority (Security/Stability)

1. **Move gateway token to backend proxy** - Don't expose in frontend
2. **Add input validation** with schema validation library
3. **Escape HTML in dynamic content** - XSS prevention
4. **Add rate limiting** for API endpoints

### 🟡 Medium Priority (Performance/Reliability)

5. **Add response caching** for weather and standup
6. **Implement WebSocket reconnection** with exponential backoff
7. **Add database connection pooling** for high load
8. **Parallelize git repo scanning** per-repo

### 🟢 Low Priority (Maintainability)

9. **Split index.html** into separate JS modules
10. **Add API versioning** (/api/v1/)
11. **Implement Alembic migrations** for schema changes
12. **Add frontend unit tests** with Jest/Vitest

---

## 9. Action Items

### Immediate (This Session)

- [x] Document all findings
- [ ] Fix XSS vulnerability in task rendering
- [ ] Add basic input validation

### Short-term (This Week)

- [ ] Move gateway token to backend
- [ ] Add rate limiting
- [ ] Implement caching layer

### Long-term (Backlog)

- [ ] Split frontend into modules
- [ ] Add WebSocket reconnection
- [ ] Database connection pooling
- [ ] Frontend test coverage

---

## 10. Code Samples for Fixes

### Fix 1: XSS Prevention (High Priority)

```javascript
// Add to index.html
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Use in all dynamic content
content.innerHTML = data.tasks.map(t => `
    <div class="item">
        <div class="item-title">${escapeHtml(t.content)}</div>
    </div>
`).join('');
```

### Fix 2: Input Validation (High Priority)

```python
# Add to server.py
from functools import wraps

def validate_json(*required_fields):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json()
            if not data:
                return jsonify({'error': 'JSON body required'}), 400
            missing = [f for f in required_fields if f not in data]
            if missing:
                return jsonify({'error': f'Missing fields: {missing}'}), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/api/planning/message', methods=['POST'])
@validate_json('session_id', 'role', 'content')
def log_planning_message():
    ...
```

### Fix 3: Caching Layer (Medium Priority)

```python
# Add to server.py
from cachetools import TTLCache

_cache = TTLCache(maxsize=100, ttl=300)

def cached(key_func, ttl=300):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = key_func(*args, **kwargs)
            if key in _cache:
                return _cache[key]
            result = f(*args, **kwargs)
            _cache[key] = result
            return result
        return wrapper
    return decorator

@cached(lambda: 'weather', ttl=300)
def fetch_weather():
    ...
```

---

*Review completed: 2026-01-30 07:45 GMT*
