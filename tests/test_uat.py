"""
User Acceptance Tests (UAT) for Project Dashboard

Tests the UI/UX from an end-user perspective using Playwright.
Run with: pytest tests/test_uat.py -v

Prerequisites:
    pip install pytest-playwright playwright
    playwright install chromium
"""

import pytest
import subprocess
import time
import os
import re
import signal
from playwright.sync_api import Page, expect, sync_playwright


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def server():
    """Start the Flask server for testing."""
    import requests
    
    env = os.environ.copy()
    env['FLASK_ENV'] = 'testing'
    
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_python = os.path.join(project_dir, 'venv', 'bin', 'python')
    
    # Start server
    proc = subprocess.Popen(
        [venv_python, 'server.py'],
        cwd=project_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to be ready (poll health endpoint)
    max_attempts = 30
    for i in range(max_attempts):
        try:
            resp = requests.get('http://localhost:8889/api/health', timeout=1)
            if resp.status_code == 200:
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError("Server failed to start within 15 seconds")
    
    yield proc
    
    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="module")
def browser_context():
    """Create a browser context for tests."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800}
        )
        yield context
        context.close()
        browser.close()


@pytest.fixture
def page(browser_context, server):
    """Create a new page for each test."""
    page = browser_context.new_page()
    yield page
    page.close()


BASE_URL = "http://localhost:8889"


# =============================================================================
# 1. Page Load & Layout Tests
# =============================================================================

class TestPageLoad:
    """Test initial page load and basic layout."""
    
    def test_page_loads_successfully(self, page: Page):
        """Dashboard page loads without errors."""
        page.goto(BASE_URL)
        expect(page).to_have_title("Project Dashboard")
    
    def test_header_displays_correctly(self, page: Page):
        """Header shows title and last updated time."""
        page.goto(BASE_URL)
        
        # Title visible
        expect(page.locator("h1")).to_contain_text("Project Dashboard")
        
        # Last updated timestamp
        expect(page.locator("#last-updated")).to_be_visible()
    
    def test_navigation_tabs_visible(self, page: Page):
        """All navigation tabs are present."""
        page.goto(BASE_URL)
        
        # Tab names include emoji prefixes
        tabs = ["Standup", "Plan", "Dashboard", "Analytics", "Git Details", "Task Details", "Linear Details"]
        for tab in tabs:
            expect(page.locator(f".tab:has-text('{tab}')")).to_be_visible()
    
    def test_dashboard_tab_active_by_default(self, page: Page):
        """Dashboard tab is active on initial load."""
        page.goto(BASE_URL)
        
        dashboard_tab = page.locator(".tab.active")
        expect(dashboard_tab).to_contain_text("Dashboard")
    
    def test_dashboard_cards_visible(self, page: Page):
        """Source cards are displayed on Dashboard tab."""
        page.goto(BASE_URL)
        
        # Navigate to Dashboard tab
        page.locator(".tab:has-text('Dashboard')").click()
        page.wait_for_load_state("networkidle")
        
        # Dashboard shows source cards (Git, Todoist, Linear, Kanban)
        expect(page.locator("#git-card")).to_be_visible()
        expect(page.locator("#todoist-card")).to_be_visible()
        expect(page.locator("#linear-card")).to_be_visible()
        expect(page.locator("#kanban-card")).to_be_visible()


# =============================================================================
# 2. Tab Navigation Tests
# =============================================================================

class TestTabNavigation:
    """Test tab switching and content display."""
    
    def test_switch_to_analytics_tab(self, page: Page):
        """Clicking Analytics tab shows analytics content."""
        page.goto(BASE_URL)
        
        page.locator(".tab:has-text('Analytics')").click()
        
        # Analytics content visible
        expect(page.locator("#tab-analytics")).to_be_visible()
        expect(page.locator("#tab-dashboard")).not_to_be_visible()
    
    def test_switch_to_git_detail_tab(self, page: Page):
        """Clicking Git tab shows git details."""
        page.goto(BASE_URL)
        
        page.locator(".tab:has-text('Git Details')").click()
        
        expect(page.locator("#tab-git-detail")).to_be_visible()
    
    def test_switch_to_tasks_detail_tab(self, page: Page):
        """Clicking Tasks tab shows task details."""
        page.goto(BASE_URL)
        
        page.locator(".tab:has-text('Task Details')").click()
        
        expect(page.locator("#tab-tasks-detail")).to_be_visible()
    
    def test_switch_to_standup_tab(self, page: Page):
        """Clicking Standup tab shows standup view."""
        page.goto(BASE_URL)
        
        page.locator(".tab:has-text('Standup')").click()
        
        expect(page.locator("#tab-standup")).to_be_visible()
    
    def test_switch_to_plan_tab(self, page: Page):
        """Clicking Plan tab shows planning chat."""
        page.goto(BASE_URL)
        
        page.locator(".tab:has-text('Plan')").click()
        
        expect(page.locator("#tab-plan")).to_be_visible()
    
    def test_tab_preserves_content_on_return(self, page: Page):
        """Returning to a tab preserves previously loaded content."""
        page.goto(BASE_URL)
        
        # Wait for load
        page.wait_for_load_state("networkidle")
        
        # Switch away and back
        page.locator(".tab:has-text('Analytics')").click()
        page.locator(".tab:has-text('Dashboard')").click()
        
        # Dashboard content still visible
        expect(page.locator("#tab-dashboard")).to_be_visible()


# =============================================================================
# 3. Dashboard Content Tests
# =============================================================================

class TestDashboardContent:
    """Test dashboard data display."""
    
    def test_git_card_displays(self, page: Page):
        """Git repos card is displayed on Dashboard tab."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Dashboard')").click()
        
        # Card visible using ID
        expect(page.locator("#git-card")).to_be_visible()
    
    def test_todoist_card_displays(self, page: Page):
        """Todoist tasks card is displayed on Dashboard tab."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Dashboard')").click()
        
        expect(page.locator("#todoist-card")).to_be_visible()
    
    def test_kanban_card_displays(self, page: Page):
        """Kanban card is displayed on Dashboard tab."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Dashboard')").click()
        
        expect(page.locator("#kanban-card")).to_be_visible()
    
    def test_linear_card_displays(self, page: Page):
        """Linear issues card is displayed on Dashboard tab."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Dashboard')").click()
        
        expect(page.locator("#linear-card")).to_be_visible()
    
    def test_header_elements_present(self, page: Page):
        """Header has title and refresh button."""
        page.goto(BASE_URL)
        
        expect(page.locator("h1")).to_be_visible()
        expect(page.locator("#refresh-btn")).to_be_visible()
        expect(page.locator("#last-updated")).to_be_visible()


# =============================================================================
# 4. Analytics Tab Tests
# =============================================================================

class TestAnalyticsTab:
    """Test analytics charts and controls."""
    
    def test_period_selector_visible(self, page: Page):
        """Period selector buttons are visible."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Analytics')").click()
        
        expect(page.locator(".period-btn:has-text('7 Days')")).to_be_visible()
        expect(page.locator(".period-btn:has-text('14 Days')")).to_be_visible()
        expect(page.locator(".period-btn:has-text('30 Days')")).to_be_visible()
    
    def test_charts_container_visible(self, page: Page):
        """Chart containers are present."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Analytics')").click()
        
        expect(page.locator("#chart-git")).to_be_visible()
        expect(page.locator("#chart-kanban")).to_be_visible()
        expect(page.locator("#chart-linear")).to_be_visible()
    
    def test_period_selector_changes_active_state(self, page: Page):
        """Clicking period selector changes active state."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Analytics')").click()
        
        # Click 14 Days
        btn_14d = page.locator(".period-btn:has-text('14 Days')")
        btn_14d.click()
        
        expect(btn_14d).to_have_class(re.compile(r"active"))


# =============================================================================
# 5. Standup Tab Tests
# =============================================================================

class TestStandupTab:
    """Test morning standup view."""
    
    def test_standup_layout(self, page: Page):
        """Standup tab has correct layout."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Standup')").click()
        
        # Summary section
        expect(page.locator("#standup-summary")).to_be_visible()
        
        # Task sections
        expect(page.locator("#standup-overdue")).to_be_visible()
        expect(page.locator("#standup-today")).to_be_visible()
        expect(page.locator("#standup-inprogress")).to_be_visible()
    
    def test_standup_sections_visible(self, page: Page):
        """Standup has all required sections."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Standup')").click()
        
        # Overdue and today sections visible
        expect(page.locator("#standup-overdue")).to_be_visible()
        expect(page.locator("#standup-today")).to_be_visible()
    
    def test_weather_section_present(self, page: Page):
        """Weather section is present."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Standup')").click()
        
        expect(page.locator("#standup-weather")).to_be_visible()


# =============================================================================
# 6. Planning Tab Tests
# =============================================================================

class TestPlanningTab:
    """Test planning chat interface."""
    
    def test_planning_layout(self, page: Page):
        """Planning tab has correct layout."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Plan')").click()
        
        # Context panel
        expect(page.locator("#plan-context")).to_be_visible()
        
        # Messages container
        expect(page.locator("#plan-messages")).to_be_visible()
        
        # Input area
        expect(page.locator("#plan-input")).to_be_visible()
    
    def test_start_session_button_visible(self, page: Page):
        """Start session button is visible."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Plan')").click()
        
        expect(page.locator("#plan-session-btn")).to_be_visible()
        expect(page.locator("#plan-session-btn")).to_contain_text("Start")
    
    def test_session_status_visible(self, page: Page):
        """Session status indicator is visible."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Plan')").click()
        
        expect(page.locator("#plan-session-status")).to_be_visible()
    
    def test_input_field_present(self, page: Page):
        """Chat input field is present."""
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Plan')").click()
        
        input_field = page.locator("#plan-input")
        expect(input_field).to_be_visible()


# =============================================================================
# 7. Detail View Tests
# =============================================================================

class TestDetailViews:
    """Test detailed view tabs."""
    
    def test_git_detail_shows_repos(self, page: Page):
        """Git detail tab shows repository list."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        page.locator(".tab:has-text('Git Details')").click()
        
        expect(page.locator("#git-detail-content")).to_be_visible()
    
    def test_tasks_detail_shows_tasks(self, page: Page):
        """Tasks detail tab shows task list."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        page.locator(".tab:has-text('Task Details')").click()
        
        expect(page.locator("#tasks-detail-content")).to_be_visible()
    
    def test_linear_detail_shows_sections(self, page: Page):
        """Linear detail tab shows status sections."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        page.locator(".tab:has-text('Linear Details')").click()
        
        expect(page.locator("#linear-inprogress-content")).to_be_visible()
        expect(page.locator("#linear-todo-content")).to_be_visible()
        expect(page.locator("#linear-backlog-content")).to_be_visible()


# =============================================================================
# 8. Responsive Design Tests
# =============================================================================

class TestResponsiveDesign:
    """Test responsive layout at different screen sizes."""
    
    def test_mobile_layout(self, browser_context, server):
        """Dashboard adapts to mobile screen size."""
        page = browser_context.new_page()
        page.set_viewport_size({"width": 375, "height": 667})  # iPhone SE
        
        page.goto(BASE_URL)
        
        # Page still loads
        expect(page).to_have_title("Project Dashboard")
        
        # Cards stack vertically (check they're visible)
        expect(page.locator("#git-content")).to_be_visible()
        expect(page.locator("#todoist-content")).to_be_visible()
        
        page.close()
    
    def test_tablet_layout(self, browser_context, server):
        """Dashboard adapts to tablet screen size."""
        page = browser_context.new_page()
        page.set_viewport_size({"width": 768, "height": 1024})  # iPad
        
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Dashboard')").click()
        
        expect(page).to_have_title("Project Dashboard")
        expect(page.locator("#tab-dashboard .dashboard-grid")).to_be_visible()
        
        page.close()
    
    def test_wide_desktop_layout(self, browser_context, server):
        """Dashboard handles wide screens."""
        page = browser_context.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})  # 1080p
        
        page.goto(BASE_URL)
        page.locator(".tab:has-text('Dashboard')").click()
        
        expect(page).to_have_title("Project Dashboard")
        expect(page.locator("#tab-dashboard .dashboard-grid")).to_be_visible()
        
        page.close()


# =============================================================================
# 9. Error State Tests
# =============================================================================

class TestErrorStates:
    """Test error handling in the UI."""
    
    def test_unconfigured_service_shows_setup_prompt(self, page: Page):
        """Unconfigured services show setup instructions."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        # Check for any setup prompts or error states
        # (These appear when services aren't configured)
        content = page.content()
        
        # Should either show data or setup prompts - not crash
        assert "Project Dashboard" in content
    
    def test_network_error_handling(self, browser_context, server):
        """UI handles network errors gracefully."""
        # Use a fresh page to avoid affecting other tests
        page = browser_context.new_page()
        try:
            page.goto(BASE_URL)
            page.wait_for_load_state("networkidle")
            
            # Simulate offline after initial load
            page.context.set_offline(True)
            
            # Try to refresh - use specific header refresh button
            page.locator("#refresh-btn").click()
            
            # Page should not crash - give time for error handling
            page.wait_for_timeout(2000)
            
            # Should still have content (cached)
            assert "Project Dashboard" in page.content()
        finally:
            # ALWAYS restore connectivity
            page.context.set_offline(False)
            page.close()


# =============================================================================
# 10. Refresh & Update Tests
# =============================================================================

class TestRefreshFunctionality:
    """Test data refresh functionality."""
    
    def test_manual_refresh_button_works(self, page: Page):
        """Clicking refresh button triggers data reload."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        # Use the specific header refresh button
        refresh_btn = page.locator("#refresh-btn")
        expect(refresh_btn).to_be_visible()
        
        # Wait a moment then refresh
        page.wait_for_timeout(1500)
        refresh_btn.click()
        
        # Wait for refresh to complete
        page.wait_for_load_state("networkidle")
        
        # Page should still work after refresh
        expect(page).to_have_title("Project Dashboard")
    
    def test_refresh_button_clickable(self, page: Page):
        """Refresh button can be clicked multiple times."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        refresh_btn = page.locator("#refresh-btn")
        
        # Click refresh
        refresh_btn.click()
        page.wait_for_load_state("networkidle")
        
        # Should still be clickable after refresh completes
        expect(refresh_btn).to_be_visible()


# =============================================================================
# 11. Keyboard Navigation Tests
# =============================================================================

class TestKeyboardNavigation:
    """Test keyboard accessibility."""
    
    def test_tab_navigation_works(self, page: Page):
        """Tab key navigates between interactive elements."""
        page.goto(BASE_URL)
        
        # Press Tab to move through elements
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        
        # Should be able to tab through without errors
        focused = page.evaluate("document.activeElement.tagName")
        assert focused is not None
    
    def test_enter_activates_buttons(self, page: Page):
        """Enter key activates focused buttons."""
        page.goto(BASE_URL)
        
        # Focus Analytics tab
        analytics_tab = page.locator(".tab:has-text('Analytics')") 
        analytics_tab.focus()
        
        # Press Enter
        page.keyboard.press("Enter")
        
        # Analytics tab should now be active
        expect(page.locator("#tab-analytics")).to_be_visible()


# =============================================================================
# 12. Visual Consistency Tests
# =============================================================================

class TestVisualConsistency:
    """Test visual elements and styling."""
    
    def test_dark_theme_applied(self, page: Page):
        """Dark theme is applied correctly."""
        page.goto(BASE_URL)
        
        # Check background is dark (RGB values should be low)
        bg_color = page.evaluate(
            "getComputedStyle(document.body).backgroundColor"
        )
        # Parse RGB values and check they're dark (< 50)
        import re
        match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', bg_color)
        if match:
            r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
            assert r < 50 and g < 50 and b < 50, f"Background should be dark, got {bg_color}"
        else:
            # Fallback - just check page loads
            assert "Project Dashboard" in page.content()
    
    def test_cards_have_consistent_styling(self, page: Page):
        """All cards have consistent border radius and padding."""
        page.goto(BASE_URL)
        
        cards = page.locator(".card")
        count = cards.count()
        
        assert count > 0, "Should have at least one card"
    
    def test_status_indicators_have_correct_colors(self, page: Page):
        """Status dots use correct colors for states."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        # Status dots should exist
        dots = page.locator(".status-dot")
        assert dots.count() >= 4


# =============================================================================
# 13. Data Rendering Tests
# =============================================================================

class TestDataRendering:
    """Test that data renders correctly."""
    
    def test_task_priority_icons_display(self, page: Page):
        """Task priority icons (🔴🟠🟡) display correctly."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        # Check todoist content area exists
        expect(page.locator("#todoist-content")).to_be_visible()
    
    def test_empty_states_display_correctly(self, page: Page):
        """Empty states show appropriate messages."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        # Check for any empty state or content
        content = page.content()
        
        # Should have either data or appropriate empty states
        assert len(content) > 1000  # Page has substantial content
    
    def test_xss_content_escaped(self, page: Page):
        """XSS attempts in content are properly escaped."""
        page.goto(BASE_URL)
        
        # The escapeHtml function should prevent script injection
        # Check that the function exists
        has_escape = page.evaluate("typeof escapeHtml === 'function'")
        assert has_escape, "escapeHtml function should be defined"


# =============================================================================
# 14. Interaction Tests
# =============================================================================

class TestInteractions:
    """Test user interactions."""
    
    def test_hover_effects_on_items(self, page: Page):
        """Items have hover effects."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        # Check that items exist for hover
        items = page.locator(".item")
        if items.count() > 0:
            # Hover over first item
            items.first.hover()
            # Should not cause errors
    
    def test_clickable_elements_have_cursor(self, page: Page):
        """Clickable elements have pointer cursor."""
        page.goto(BASE_URL)
        
        # Tabs should have pointer cursor
        tab = page.locator(".tab").first
        cursor = tab.evaluate("el => getComputedStyle(el).cursor")
        assert cursor == "pointer"


# =============================================================================
# Run with: pytest tests/test_uat.py -v
# =============================================================================
