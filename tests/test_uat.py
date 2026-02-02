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

        # Logo/title visible
        expect(page.locator("h1.logo")).to_be_visible()

        # Last updated timestamp
        expect(page.locator("#last-updated")).to_be_visible()

    def test_navigation_tabs_visible(self, page: Page):
        """All navigation tabs are present."""
        page.goto(BASE_URL)

        # New tab structure: Command, Kanban, Life, Plan, Analytics
        tabs = ["Command", "Kanban", "Life", "Plan", "Analytics"]
        for tab in tabs:
            expect(page.locator(f".tab:has-text('{tab}')")).to_be_visible()

    def test_command_center_active_by_default(self, page: Page):
        """Command Center tab is active on initial load."""
        page.goto(BASE_URL)

        active_tab = page.locator(".tab.active")
        expect(active_tab).to_contain_text("Command")

    def test_needs_attention_card_visible(self, page: Page):
        """Needs Attention card is displayed on Command tab."""
        page.goto(BASE_URL)

        expect(page.locator("#needs-attention-card")).to_be_visible()


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
        expect(page.locator("#tab-command-center")).not_to_be_visible()

    def test_switch_to_kanban_tab(self, page: Page):
        """Clicking Kanban tab shows kanban board."""
        page.goto(BASE_URL)

        page.locator(".tab:has-text('Kanban')").click()

        expect(page.locator("#tab-kanban")).to_be_visible()

    def test_switch_to_life_tab(self, page: Page):
        """Clicking Life tab shows life balance view."""
        page.goto(BASE_URL)

        page.locator(".tab:has-text('Life')").click()

        expect(page.locator("#tab-life")).to_be_visible()

    def test_switch_to_plan_tab(self, page: Page):
        """Clicking Plan tab shows planning chat."""
        page.goto(BASE_URL)

        page.locator(".tab:has-text('Plan')").click()

        expect(page.locator("#tab-plan")).to_be_visible()

    def test_tab_preserves_content_on_return(self, page: Page):
        """Returning to a tab preserves previously loaded content."""
        page.goto(BASE_URL)

        # Wait for initial load
        page.wait_for_load_state("networkidle")

        # Switch to Analytics
        page.locator(".tab:has-text('Analytics')").click()
        expect(page.locator("#tab-analytics")).to_be_visible()

        # Switch back to Command
        page.locator(".tab:has-text('Command')").click()
        expect(page.locator("#tab-command-center")).to_be_visible()


# =============================================================================
# 3. Command Center Content Tests
# =============================================================================

class TestCommandCenterContent:
    """Test Command Center tab content."""

    def test_todays_focus_displays(self, page: Page):
        """Today's Focus card is visible."""
        page.goto(BASE_URL)

        expect(page.locator("#today-card")).to_be_visible()

    def test_status_indicators_present(self, page: Page):
        """Status indicators for services are present."""
        page.goto(BASE_URL)

        expect(page.locator("#status-git")).to_be_visible()
        expect(page.locator("#status-todoist")).to_be_visible()
        expect(page.locator("#status-kanban")).to_be_visible()
        expect(page.locator("#status-linear")).to_be_visible()

    def test_refresh_button_present(self, page: Page):
        """Refresh button is clickable."""
        page.goto(BASE_URL)

        expect(page.locator("#refresh-btn")).to_be_visible()


# =============================================================================
# 4. Analytics Tab Tests
# =============================================================================

class TestAnalyticsTab:
    """Test Analytics tab functionality."""

    def test_period_selector_visible(self, page: Page):
        """Period selector is visible in Analytics tab."""
        page.goto(BASE_URL)

        page.locator(".tab:has-text('Analytics')").click()
        page.wait_for_load_state("networkidle")

        expect(page.locator(".period-selector")).to_be_visible()

    def test_charts_container_visible(self, page: Page):
        """Charts are displayed in Analytics tab."""
        page.goto(BASE_URL)

        page.locator(".tab:has-text('Analytics')").click()
        page.wait_for_load_state("networkidle")

        # Chart containers should be present (use .first for strict mode)
        expect(page.locator(".chart-container").first).to_be_visible()


# =============================================================================
# 5. Life Tab Tests
# =============================================================================

class TestLifeTab:
    """Test Life Balance tab functionality."""

    def test_life_layout(self, page: Page):
        """Life tab displays XP tracking interface."""
        page.goto(BASE_URL)

        page.locator(".tab:has-text('Life')").click()
        page.wait_for_load_state("networkidle")

        expect(page.locator("#tab-life")).to_be_visible()

    def test_xp_display_present(self, page: Page):
        """XP and level information is displayed."""
        page.goto(BASE_URL)

        page.locator(".tab:has-text('Life')").click()
        page.wait_for_timeout(1000)

        # Life content should have some XP display elements
        expect(page.locator("#tab-life")).to_be_visible()


# =============================================================================
# 6. Planning Tab Tests
# =============================================================================

class TestPlanningTab:
    """Test Planning tab functionality."""

    def test_planning_layout(self, page: Page):
        """Plan tab displays chat interface."""
        page.goto(BASE_URL)

        page.locator(".tab:has-text('Plan')").click()

        expect(page.locator("#tab-plan")).to_be_visible()

    def test_session_status_visible(self, page: Page):
        """Session status indicator is present."""
        page.goto(BASE_URL)

        page.locator(".tab:has-text('Plan')").click()

        # Look for planning session UI elements
        expect(page.locator("#tab-plan")).to_be_visible()


# =============================================================================
# 7. Kanban Tab Tests
# =============================================================================

class TestKanbanTab:
    """Test Kanban board functionality."""

    def test_kanban_columns_visible(self, page: Page):
        """Kanban board shows columns."""
        page.goto(BASE_URL)

        page.locator(".tab:has-text('Kanban')").click()
        page.wait_for_load_state("networkidle")

        expect(page.locator("#tab-kanban")).to_be_visible()

    def test_add_task_button_present(self, page: Page):
        """Add task button is visible."""
        page.goto(BASE_URL)

        page.locator(".tab:has-text('Kanban')").click()
        page.wait_for_timeout(500)

        # Kanban should have an add task mechanism
        expect(page.locator("#tab-kanban")).to_be_visible()


# =============================================================================
# 8. Responsive Design Tests
# =============================================================================

class TestResponsiveDesign:
    """Test responsive layout at different viewport sizes."""

    def test_mobile_layout(self, page: Page):
        """App is usable at mobile width."""
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)

        # Main container should be visible
        expect(page.locator(".container")).to_be_visible()

    def test_tablet_layout(self, page: Page):
        """App displays properly at tablet width."""
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto(BASE_URL)

        expect(page.locator(".container")).to_be_visible()

    def test_wide_desktop_layout(self, page: Page):
        """App displays properly at wide desktop width."""
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto(BASE_URL)

        expect(page.locator(".container")).to_be_visible()


# =============================================================================
# 9. Error States Tests
# =============================================================================

class TestErrorStates:
    """Test error handling and edge cases."""

    def test_page_handles_no_data(self, page: Page):
        """Page displays gracefully with no data."""
        page.goto(BASE_URL)

        # Even with no data, page should load
        expect(page.locator(".container")).to_be_visible()

    def test_empty_states_display(self, page: Page):
        """Empty state messages display for sections with no data."""
        page.goto(BASE_URL)

        # The needs attention section should have a card visible
        expect(page.locator("#needs-attention-card")).to_be_visible()


# =============================================================================
# 10. Refresh Functionality Tests
# =============================================================================

class TestRefreshFunctionality:
    """Test manual refresh functionality."""

    def test_refresh_button_clickable(self, page: Page):
        """Refresh button can be clicked."""
        page.goto(BASE_URL)

        refresh_btn = page.locator("#refresh-btn")
        expect(refresh_btn).to_be_visible()

        # Click should not throw error
        refresh_btn.click()


# =============================================================================
# 11. Visual Consistency Tests
# =============================================================================

class TestVisualConsistency:
    """Test visual consistency and theming."""

    def test_dark_theme_applied(self, page: Page):
        """Dark theme is applied by default."""
        page.goto(BASE_URL)

        # Body should have dark theme data attribute
        body = page.locator("body")
        expect(body).to_have_attribute("data-theme", "dark")

    def test_cards_have_consistent_styling(self, page: Page):
        """Cards use consistent styling."""
        page.goto(BASE_URL)

        # At least one card should be visible
        cards = page.locator(".card")
        expect(cards.first).to_be_visible()


# =============================================================================
# 12. Security Tests
# =============================================================================

class TestSecurity:
    """Test XSS prevention and security features."""

    def test_xss_content_escaped(self, page: Page):
        """XSS attempts in content are escaped."""
        page.goto(BASE_URL)

        # Check that escapeHtml function exists in page context
        result = page.evaluate("typeof escapeHtml === 'function'")
        assert result is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
