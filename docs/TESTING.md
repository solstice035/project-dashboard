# Project Dashboard - Testing Guide

## Test Suites

The dashboard has three types of tests:

| Suite | Purpose | Location |
|-------|---------|----------|
| **Unit Tests** | API endpoints, database operations | `tests/test_api.py`, `tests/test_analytics.py` |
| **Integration Tests** | End-to-end data flow | `tests/test_integration.py` |
| **UAT Tests** | User interface and experience | `tests/test_uat.py` |

---

## Quick Start

```bash
cd ~/clawd/projects/project-dashboard
source venv/bin/activate

# Run all tests
pytest -v

# Run specific suite
pytest tests/test_api.py -v
pytest tests/test_uat.py -v

# Run with coverage
pytest --cov=. --cov-report=html
```

---

## Unit Tests

### API Tests (`test_api.py`)

Tests all REST endpoints:
- `/api/health` - Health check
- `/api/dashboard` - Main dashboard data
- `/api/standup` - Morning standup
- `/api/analytics` - Historical trends
- `/api/planning/*` - Planning sessions

### Analytics Tests (`test_analytics.py`)

Tests historical data and trends:
- Git commit trends
- Kanban flow metrics
- Linear issue tracking

### Planning Tests (`test_planning.py`)

Tests planning session management:
- Session creation and lifecycle
- Message logging
- Chat history retrieval

---

## Integration Tests

### `test_integration.py`

End-to-end tests for complete workflows:
- Dashboard data aggregation
- Multiple service integration
- Error recovery scenarios

---

## User Acceptance Tests (UAT)

### `test_uat.py`

Browser-based tests using Playwright. Tests the actual user interface.

### Prerequisites

```bash
# Install Playwright (in venv)
source venv/bin/activate
pip install pytest-playwright playwright
playwright install chromium
```

### Running UAT Tests

```bash
# Headless (default)
pytest tests/test_uat.py -v

# With browser visible (for debugging)
pytest tests/test_uat.py -v --headed

# Specific test class
pytest tests/test_uat.py::TestTabNavigation -v

# Single test
pytest tests/test_uat.py::TestPageLoad::test_page_loads_successfully -v
```

### Test Categories

#### 1. Page Load & Layout
- Page loads successfully
- Header displays correctly
- Navigation tabs visible
- Dashboard tab active by default
- Stat cards visible

#### 2. Tab Navigation
- Switch between all tabs
- Content visibility after switch
- Content preservation on return

#### 3. Dashboard Content
- All cards display (Git, Todoist, Kanban, Linear)
- Status indicators present
- Auto-refresh controls visible

#### 4. Analytics Tab
- Period selector visible
- Charts render
- Period changes update data

#### 5. Standup Tab
- Correct layout (summary, tasks, weather)
- Refresh button works
- Task sections display

#### 6. Planning Tab
- Context panel visible
- Chat interface present
- Session controls work
- Input disabled without session

#### 7. Detail Views
- Git detail shows repos
- Tasks detail shows tasks
- Linear detail shows by status

#### 8. Responsive Design
- Mobile layout (375px)
- Tablet layout (768px)
- Wide desktop (1920px)

#### 9. Error States
- Unconfigured services show setup prompt
- Network errors handled gracefully

#### 10. Refresh Functionality
- Manual refresh works
- Auto-refresh toggle works

#### 11. Keyboard Navigation
- Tab navigation works
- Enter activates buttons

#### 12. Visual Consistency
- Dark theme applied
- Cards have consistent styling
- Status indicators have correct colors

#### 13. Data Rendering
- Priority icons display
- Empty states appropriate
- XSS content escaped

#### 14. Interactions
- Hover effects work
- Clickable elements have pointer cursor

---

## Writing New Tests

### API Test Template

```python
def test_endpoint_returns_expected_data(client):
    """Description of what we're testing."""
    response = client.get('/api/endpoint')
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'expected_key' in data
```

### UAT Test Template

```python
def test_user_can_perform_action(self, page: Page):
    """Description of user flow."""
    page.goto(BASE_URL)
    
    # User action
    page.get_by_role("button", name="Action").click()
    
    # Verify result
    expect(page.locator("#result")).to_be_visible()
```

---

## Coverage Targets

| Module | Target | Current |
|--------|--------|---------|
| server.py | 80% | ~75% |
| database.py | 80% | ~80% |
| index.html (JS) | 60% | N/A (Playwright covers UX) |

---

## Continuous Integration

For CI/CD, run:

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium --with-deps

# Run all tests
pytest -v --tb=short

# Generate coverage report
pytest --cov=. --cov-report=xml
```

---

## Troubleshooting

### "No module named pytest"
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### "playwright not installed"
```bash
pip install pytest-playwright playwright
playwright install chromium
```

### Tests timeout
```bash
# Increase timeout
pytest tests/test_uat.py -v --timeout=60
```

### Server not starting in tests
Check that port 5050 is not already in use:
```bash
lsof -i :5050
```

### Flaky tests
Run with retry:
```bash
pip install pytest-rerunfailures
pytest tests/test_uat.py -v --reruns 2
```
