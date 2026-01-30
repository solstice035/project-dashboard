/* =============================================================================
   Project Dashboard - Main Application JavaScript
   ============================================================================= */

// =============================================================================
// Global State
// =============================================================================
let refreshInterval = 300000;
let refreshTimer = null;
let currentPeriod = 7;
let dashboardData = null;
let gitChart = null;
let kanbanChart = null;
let linearChart = null;
let standupData = null;
let overnightSprints = [];
let selectedSprintId = null;

// Planning state
let planSessionId = null;
let planSocket = null;
const DEFAULT_GATEWAY_TOKEN = 'f2f8d0074aa8f2bf972bfa072ebdb45cb54d00fd8337f3a7';
let gatewayToken = localStorage.getItem('gateway_token') || DEFAULT_GATEWAY_TOKEN;
let currentAssistantMessage = null;

// Attention badge state
let attentionItems = {
    overdue: [],
    dirty: [],
    blocked: []
};

// =============================================================================
// Utilities
// =============================================================================

/**
 * Escape HTML to prevent XSS - ALL user-generated content MUST pass through this
 */
function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') return unsafe;
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/**
 * Create a Lucide icon element (safe - no user input)
 */
function icon(name, className) {
    const cls = className ? ' class="icon ' + className + '"' : ' class="icon"';
    return '<i data-lucide="' + name + '"' + cls + '></i>';
}

/**
 * Initialize Lucide icons after DOM updates
 */
function refreshIcons() {
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

/**
 * Get priority class based on priority number
 */
function getPriorityClass(priority) {
    switch (priority) {
        case 4: return 'p1';
        case 3: return 'p2';
        case 2: return 'p3';
        default: return 'p4';
    }
}

/**
 * Format date for display
 */
function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

// =============================================================================
// Modal System
// =============================================================================

/**
 * Open a modal with the given content
 */
function openModal(title, content, iconName) {
    const overlay = document.getElementById('modal-overlay');
    const modalTitle = overlay.querySelector('.modal-title');
    const modalBody = overlay.querySelector('.modal-body');

    // Title is escaped, icon is safe
    modalTitle.innerHTML = iconName ? icon(iconName) + ' ' + escapeHtml(title) : escapeHtml(title);
    // Content is pre-escaped by caller
    modalBody.innerHTML = content;

    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
    refreshIcons();
}

/**
 * Close the modal
 */
function closeModal() {
    const overlay = document.getElementById('modal-overlay');
    overlay.classList.remove('open');
    document.body.style.overflow = '';
}

/**
 * Initialize modal event listeners
 */
function initModal() {
    const overlay = document.getElementById('modal-overlay');
    if (!overlay) return;

    const closeBtn = overlay.querySelector('.modal-close');

    if (closeBtn) {
        closeBtn.addEventListener('click', closeModal);
    }

    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            closeModal();
        }
    });

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && overlay.classList.contains('open')) {
            closeModal();
        }
    });
}

// =============================================================================
// Attention Badge
// =============================================================================

/**
 * Update the attention badge with current counts
 */
function updateAttentionBadge() {
    const badge = document.getElementById('attention-badge');
    if (!badge) return;

    const countEl = badge.querySelector('.count');
    const dropdown = document.getElementById('attention-dropdown');

    const total = attentionItems.overdue.length + attentionItems.dirty.length + attentionItems.blocked.length;

    if (total === 0) {
        badge.classList.add('hidden');
        return;
    }

    badge.classList.remove('hidden');
    if (countEl) countEl.textContent = total;

    // Build dropdown content - all user content is escaped
    let html = '';

    if (attentionItems.overdue.length > 0) {
        html += '<div class="attention-dropdown-section">';
        html += '<div class="attention-dropdown-title">' + icon('alert-triangle') + ' Overdue (' + attentionItems.overdue.length + ')</div>';
        attentionItems.overdue.slice(0, 3).forEach(function(item) {
            html += '<div class="attention-dropdown-item" onclick="switchTab(\'command-center\'); closeAttentionDropdown();">' + escapeHtml(item.content || item.title) + '</div>';
        });
        html += '</div>';
    }

    if (attentionItems.dirty.length > 0) {
        html += '<div class="attention-dropdown-section">';
        html += '<div class="attention-dropdown-title">' + icon('git-branch') + ' Uncommitted (' + attentionItems.dirty.length + ')</div>';
        attentionItems.dirty.slice(0, 3).forEach(function(item) {
            html += '<div class="attention-dropdown-item" onclick="openRepoModal(\'' + escapeHtml(item.name) + '\'); closeAttentionDropdown();">' + escapeHtml(item.name) + '</div>';
        });
        html += '</div>';
    }

    if (dropdown) {
        dropdown.innerHTML = html;
    }
    refreshIcons();
}

/**
 * Toggle attention dropdown
 */
function toggleAttentionDropdown() {
    const dropdown = document.getElementById('attention-dropdown');
    if (dropdown) dropdown.classList.toggle('open');
}

/**
 * Close attention dropdown
 */
function closeAttentionDropdown() {
    const dropdown = document.getElementById('attention-dropdown');
    if (dropdown) dropdown.classList.remove('open');
}

// =============================================================================
// Tab Navigation
// =============================================================================

/**
 * Switch to a different tab
 */
function switchTab(tabId) {
    // Update tab buttons
    document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
    var activeTab = document.querySelector('.tab[data-tab="' + tabId + '"]');
    if (activeTab) activeTab.classList.add('active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });
    var activeContent = document.getElementById('tab-' + tabId);
    if (activeContent) activeContent.classList.add('active');

    // Load data for specific tabs
    switch (tabId) {
        case 'command-center':
            loadStandup();
            break;
        case 'plan':
            loadPlanContext();
            loadStandup();
            break;
        case 'analytics':
            loadAnalytics();
            break;
    }

    refreshIcons();
}

/**
 * Switch analytics sub-tab
 */
function switchAnalyticsSubTab(subTabId) {
    document.querySelectorAll('.sub-tab').forEach(function(t) { t.classList.remove('active'); });
    if (event && event.target) event.target.classList.add('active');

    document.querySelectorAll('.analytics-sub-content').forEach(function(c) { c.classList.remove('active'); });
    var subContent = document.getElementById('analytics-' + subTabId);
    if (subContent) subContent.classList.add('active');

    switch (subTabId) {
        case 'git':
            renderGitDetails();
            break;
        case 'tasks':
            renderTasksDetails();
            break;
        case 'linear':
            renderLinearDetails();
            break;
    }
}

// =============================================================================
// Data Fetching
// =============================================================================

/**
 * Set status indicator
 */
function setStatus(source, status) {
    var el = document.getElementById('status-' + source);
    if (el) el.className = 'status-dot ' + status;
}

/**
 * Refresh all dashboard data
 */
async function refreshAll() {
    var btn = document.getElementById('refresh-btn');
    var iconEl = btn ? btn.querySelector('[data-lucide]') : null;
    if (btn) btn.disabled = true;
    if (iconEl) iconEl.classList.add('spinner');

    ['git', 'todoist', 'kanban', 'linear'].forEach(function(s) {
        setStatus(s, 'loading');
    });

    try {
        var response = await fetch('/api/dashboard');
        dashboardData = await response.json();

        if (dashboardData.refresh_interval) {
            refreshInterval = dashboardData.refresh_interval * 1000;
        }

        var lastUpdatedEl = document.getElementById('last-updated');
        if (lastUpdatedEl) {
            lastUpdatedEl.textContent = 'Updated: ' + new Date(dashboardData.timestamp).toLocaleTimeString();
        }

        renderGit(dashboardData.sources.git);
        renderTodoist(dashboardData.sources.todoist);
        renderKanban(dashboardData.sources.kanban);
        renderLinear(dashboardData.sources.linear);

        updateAttentionFromData();
        
        // Populate new dashboard sections
        populateNeedsAttention();
        populateInProgress();
        populateReadyItems();
        populateActivitySummary();
        updateGitSummary();

    } catch (error) {
        console.error('Error:', error);
        var lastUpdatedEl = document.getElementById('last-updated');
        if (lastUpdatedEl) lastUpdatedEl.textContent = 'Error loading';
    } finally {
        if (btn) btn.disabled = false;
        if (iconEl) iconEl.classList.remove('spinner');
        if (refreshTimer) clearTimeout(refreshTimer);
        refreshTimer = setTimeout(refreshAll, refreshInterval);
    }
}

/**
 * Update attention items from dashboard data
 */
function updateAttentionFromData() {
    if (!dashboardData) return;

    attentionItems.overdue = (dashboardData.sources.todoist && dashboardData.sources.todoist.tasks)
        ? dashboardData.sources.todoist.tasks.filter(function(t) { return t.is_overdue; })
        : [];

    attentionItems.dirty = (dashboardData.sources.git && dashboardData.sources.git.repos)
        ? dashboardData.sources.git.repos.filter(function(r) { return r.is_dirty; })
        : [];

    attentionItems.blocked = [];

    updateAttentionBadge();
}

/**
 * Load analytics data
 */
async function loadAnalytics() {
    try {
        var resp = await fetch('/api/analytics/trends?days=' + currentPeriod);
        var data = await resp.json();
        renderCharts(data);
        updateStats(data);
    } catch (e) {
        console.error('Analytics error:', e);
    }
}

/**
 * Set analytics period
 */
function setPeriod(days) {
    currentPeriod = days;
    document.querySelectorAll('.period-btn').forEach(function(b) { b.classList.remove('active'); });
    if (event && event.target) event.target.classList.add('active');
    loadAnalytics();
}

// =============================================================================
// Render Functions - Dashboard Cards
// =============================================================================

/**
 * Render git repositories - all user content is escaped
 */
function renderGit(data) {
    var content = document.getElementById('git-content');
    var count = document.getElementById('git-count');
    if (!content) return;

    if (data.status === 'error') {
        setStatus('git', 'error');
        content.innerHTML = '<div class="error-message">' + icon('alert-circle') + ' ' + escapeHtml(data.error) + '</div>';
        refreshIcons();
        return;
    }
    setStatus('git', 'ok');

    if (!data.repos || !data.repos.length) {
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">' + icon('folder-open') + '</div><div class="empty-state-text">No repositories found</div></div>';
        if (count) count.textContent = '0';
        refreshIcons();
        return;
    }

    var active = data.repos.filter(function(r) { return r.commit_count > 0 || r.is_dirty; });
    if (count) count.textContent = active.length + ' active';

    var displayRepos = data.repos.slice(0, 5);
    var hasMore = data.repos.length > 5;

    var html = '';
    displayRepos.forEach(function(repo) {
        var cls = repo.is_dirty ? 'item item-warning' : 'item';
        var meta = [];
        if (repo.branch) meta.push('<span class="tag">' + icon('git-branch') + ' ' + escapeHtml(repo.branch) + '</span>');
        if (repo.commit_count) meta.push(repo.commit_count + ' commits');
        if (repo.is_dirty) meta.push(icon('alert-triangle') + ' uncommitted');

        html += '<div class="' + cls + '" onclick="openRepoModal(\'' + escapeHtml(repo.name) + '\')">';
        html += '<div class="item-header"><div class="item-title">' + icon('folder-git-2') + ' ' + escapeHtml(repo.name) + '</div></div>';
        html += '<div class="item-meta">' + meta.join(' · ') + '</div>';
        html += '</div>';
    });

    if (hasMore) {
        html += '<div class="card-footer">';
        html += '<button class="view-all-btn" onclick="switchTab(\'analytics\'); setTimeout(function() { switchAnalyticsSubTab(\'git\'); }, 100);">';
        html += icon('chevron-right') + ' View all ' + data.repos.length + ' repositories</button></div>';
    }

    content.innerHTML = html;
    refreshIcons();
}

/**
 * Render Todoist tasks - all user content is escaped
 */
function renderTodoist(data) {
    var content = document.getElementById('todoist-content');
    var count = document.getElementById('todoist-count');
    if (!content) return;

    if (data.status === 'not_configured') {
        setStatus('todoist', 'warning');
        content.innerHTML = '<div class="setup-prompt">' + icon('settings') + ' Add token to <code>config.yaml</code></div>';
        refreshIcons();
        return;
    }
    if (data.status === 'error') {
        setStatus('todoist', 'error');
        content.innerHTML = '<div class="error-message">' + icon('alert-circle') + ' ' + escapeHtml(data.error) + '</div>';
        refreshIcons();
        return;
    }
    setStatus('todoist', 'ok');

    if (!data.tasks || !data.tasks.length) {
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">' + icon('check-circle') + '</div><div class="empty-state-text">All clear!</div></div>';
        if (count) count.textContent = '0';
        refreshIcons();
        return;
    }

    var overdue = data.tasks.filter(function(t) { return t.is_overdue; }).length;
    var todayCount = data.tasks.filter(function(t) { return t.is_today; }).length;
    if (count) {
        count.textContent = overdue ? overdue + ' overdue' : todayCount + ' today';
        if (overdue) {
            count.classList.add('urgent');
        } else {
            count.classList.remove('urgent');
        }
    }

    var displayTasks = data.tasks.slice(0, 5);
    var hasMore = data.tasks.length > 5;

    var html = '';
    displayTasks.forEach(function(task) {
        var cls = task.is_overdue ? 'item item-urgent' : task.is_today ? 'item item-active' : 'item';
        var priorityClass = getPriorityClass(task.priority);
        var dueClass = task.is_overdue ? 'overdue' : task.is_today ? 'today' : '';

        html += '<div class="' + cls + '" onclick="openTaskModal(\'' + task.id + '\')">';
        html += '<div class="item-header">';
        html += '<span class="item-priority ' + priorityClass + '"></span>';
        html += '<div class="item-title">' + escapeHtml(task.content) + '</div>';
        if (task.due_date) {
            html += '<span class="item-due ' + dueClass + '">' + formatDate(task.due_date) + '</span>';
        }
        html += '</div>';
        html += '<div class="item-meta"><span class="tag">' + icon('folder') + ' ' + escapeHtml(task.project) + '</span></div>';
        html += '</div>';
    });

    if (hasMore) {
        html += '<div class="card-footer">';
        html += '<button class="view-all-btn" onclick="switchTab(\'analytics\'); setTimeout(function() { switchAnalyticsSubTab(\'tasks\'); }, 100);">';
        html += icon('chevron-right') + ' View all ' + data.tasks.length + ' tasks</button></div>';
    }

    content.innerHTML = html;
    refreshIcons();
}

/**
 * Render Kanban board - all user content is escaped
 */
function renderKanban(data) {
    var content = document.getElementById('kanban-content');
    var count = document.getElementById('kanban-count');
    if (!content) return;

    if (data.status === 'unavailable') {
        setStatus('kanban', 'warning');
        content.innerHTML = '<div class="setup-prompt">' + icon('server') + ' Start board at <code>localhost:8888</code></div>';
        refreshIcons();
        return;
    }
    if (data.status === 'error') {
        setStatus('kanban', 'error');
        content.innerHTML = '<div class="error-message">' + icon('alert-circle') + ' ' + escapeHtml(data.error) + '</div>';
        refreshIcons();
        return;
    }
    setStatus('kanban', 'ok');

    var inProgress = data.by_column['in-progress'] || [];
    var ready = data.by_column['ready'] || [];
    if (count) count.textContent = inProgress.length + ' active';

    if (!inProgress.length && !ready.length) {
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">' + icon('coffee') + '</div><div class="empty-state-text">Nothing in progress</div></div>';
        refreshIcons();
        return;
    }

    var html = '';
    if (inProgress.length) {
        html += '<div class="context-section-title">' + icon('play-circle') + ' In Progress</div>';
        inProgress.slice(0, 3).forEach(function(t) {
            html += '<div class="item item-active" onclick="openKanbanModal(\'' + t.id + '\')">';
            html += '<div class="item-title">' + escapeHtml(t.title) + '</div></div>';
        });
    }
    if (ready.length) {
        html += '<div class="context-section-title" style="margin-top: var(--spacing-md);">' + icon('circle') + ' Ready</div>';
        ready.slice(0, 2).forEach(function(t) {
            html += '<div class="item" onclick="openKanbanModal(\'' + t.id + '\')">';
            html += '<div class="item-title">' + escapeHtml(t.title) + '</div></div>';
        });
    }
    content.innerHTML = html;
    refreshIcons();
}

/**
 * Render Linear issues - all user content is escaped
 */
function renderLinear(data) {
    var content = document.getElementById('linear-content');
    var count = document.getElementById('linear-count');
    if (!content) return;

    if (data.status === 'not_configured') {
        setStatus('linear', 'warning');
        content.innerHTML = '<div class="setup-prompt">' + icon('settings') + ' Add API key to <code>config.yaml</code></div>';
        if (count) count.textContent = '-';
        refreshIcons();
        return;
    }
    if (data.status === 'error') {
        setStatus('linear', 'error');
        content.innerHTML = '<div class="error-message">' + icon('alert-circle') + ' ' + escapeHtml(data.error) + '</div>';
        refreshIcons();
        return;
    }
    setStatus('linear', 'ok');

    if (!data.issues || !data.issues.length) {
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">' + icon('inbox') + '</div><div class="empty-state-text">No assigned issues</div></div>';
        if (count) count.textContent = '0';
        refreshIcons();
        return;
    }

    var inProgress = data.issues.filter(function(i) { return i.state_type === 'started'; }).length;
    if (count) count.textContent = inProgress ? inProgress + ' active' : data.issues.length + ' total';

    var displayIssues = data.issues.slice(0, 5);
    var hasMore = data.issues.length > 5;

    var html = '';
    displayIssues.forEach(function(issue) {
        var cls = issue.state_type === 'started' ? 'item item-active' : 'item';
        var priorityClass = getPriorityClass(issue.priority);

        html += '<div class="' + cls + '" onclick="openLinearModal(\'' + issue.id + '\')">';
        html += '<div class="item-header">';
        html += '<span class="item-priority ' + priorityClass + '"></span>';
        html += '<div class="item-title">' + escapeHtml(issue.identifier) + ' ' + escapeHtml(issue.title) + '</div>';
        html += '</div>';
        html += '<div class="item-meta">';
        html += '<span class="tag">' + escapeHtml(issue.state) + '</span>';
        if (issue.project) html += '<span class="tag">' + escapeHtml(issue.project) + '</span>';
        html += '</div></div>';
    });

    if (hasMore) {
        html += '<div class="card-footer">';
        html += '<button class="view-all-btn" onclick="switchTab(\'analytics\'); setTimeout(function() { switchAnalyticsSubTab(\'linear\'); }, 100);">';
        html += icon('chevron-right') + ' View all ' + data.issues.length + ' issues</button></div>';
    }

    content.innerHTML = html;
    refreshIcons();
}

// =============================================================================
// Modal Content Functions - all user content is escaped
// =============================================================================

function openRepoModal(repoName) {
    if (!dashboardData || !dashboardData.sources.git || !dashboardData.sources.git.repos) return;

    var repo = dashboardData.sources.git.repos.find(function(r) { return r.name === repoName; });
    if (!repo) return;

    var commits = '';
    if (repo.commits) {
        repo.commits.forEach(function(c) {
            var parts = c.split(' ');
            var hash = parts[0];
            var msg = parts.slice(1).join(' ');
            commits += '<div class="commit"><span class="commit-hash">' + escapeHtml(hash) + '</span> ' + escapeHtml(msg) + '</div>';
        });
    }

    var content = '<div class="item-meta" style="margin-bottom: var(--spacing-lg);">';
    content += '<span class="tag">' + icon('git-branch') + ' ' + escapeHtml(repo.branch || 'unknown') + '</span>';
    content += ' ' + repo.commit_count + ' commits';
    if (repo.is_dirty) content += ' <span class="tag" style="color: var(--color-warning);">' + icon('alert-triangle') + ' uncommitted changes</span>';
    if (repo.ahead) content += ' <span class="tag">' + icon('arrow-up') + ' ' + repo.ahead + ' ahead</span>';
    if (repo.behind) content += ' <span class="tag">' + icon('arrow-down') + ' ' + repo.behind + ' behind</span>';
    content += '</div>';
    if (commits) content += '<div style="margin-top: var(--spacing-lg);"><strong>Recent commits:</strong>' + commits + '</div>';

    openModal(repo.name, content, 'folder-git-2');
}

function openTaskModal(taskId) {
    if (!dashboardData || !dashboardData.sources.todoist || !dashboardData.sources.todoist.tasks) return;

    var task = dashboardData.sources.todoist.tasks.find(function(t) { return t.id === taskId; });
    if (!task) return;

    var priorityClass = getPriorityClass(task.priority);

    var content = '<div style="margin-bottom: var(--spacing-lg);">';
    content += '<div class="item-meta" style="margin-bottom: var(--spacing-md);">';
    content += '<span class="item-priority ' + priorityClass + '" style="width: 12px; height: 12px;"></span>';
    content += ' Priority ' + (5 - task.priority);
    content += '</div>';
    content += '<div class="item-meta">';
    content += '<span class="tag">' + icon('folder') + ' ' + escapeHtml(task.project) + '</span>';
    if (task.due_date) {
        var dueClass = task.is_overdue ? 'priority-4' : '';
        content += ' <span class="tag ' + dueClass + '">' + icon('calendar') + ' ' + escapeHtml(task.due_date) + '</span>';
    }
    content += '</div></div>';
    if (task.url) {
        content += '<a href="' + escapeHtml(task.url) + '" target="_blank" class="view-all-btn" style="width: auto; display: inline-flex;">' + icon('external-link') + ' Open in Todoist</a>';
    }

    openModal(task.content, content, 'clipboard-list');
}

function openKanbanModal(cardId) {
    if (!dashboardData || !dashboardData.sources.kanban || !dashboardData.sources.kanban.tasks) return;

    var card = dashboardData.sources.kanban.tasks.find(function(t) { return t.id === cardId; });
    if (!card) return;

    var content = '<div class="item-meta" style="margin-bottom: var(--spacing-lg);">';
    content += '<span class="tag">' + escapeHtml(card.column) + '</span>';
    if (card.tags && card.tags.length) {
        card.tags.forEach(function(tag) {
            content += '<span class="tag">' + escapeHtml(tag) + '</span>';
        });
    }
    content += '</div>';
    if (card.description) {
        content += '<p style="color: var(--text-secondary);">' + escapeHtml(card.description) + '</p>';
    }

    openModal(card.title, content, 'trello');
}

function openLinearModal(issueId) {
    if (!dashboardData || !dashboardData.sources.linear || !dashboardData.sources.linear.issues) return;

    var issue = dashboardData.sources.linear.issues.find(function(i) { return i.id === issueId; });
    if (!issue) return;

    var priorityClass = getPriorityClass(issue.priority);

    var content = '<div class="item-meta" style="margin-bottom: var(--spacing-lg);">';
    content += '<span class="item-priority ' + priorityClass + '" style="width: 12px; height: 12px;"></span>';
    content += ' <span class="tag">' + escapeHtml(issue.state) + '</span>';
    if (issue.project) content += ' <span class="tag">' + escapeHtml(issue.project) + '</span>';
    if (issue.due_date) content += ' <span class="tag">' + icon('calendar') + ' ' + escapeHtml(issue.due_date) + '</span>';
    content += '</div>';

    openModal(issue.identifier + ' ' + issue.title, content, 'bar-chart-3');
}

// =============================================================================
// Detail Views (for Analytics sub-tabs) - all user content is escaped
// =============================================================================

function renderGitDetails() {
    var content = document.getElementById('git-detail-content');
    if (!content) return;

    if (!dashboardData || !dashboardData.sources.git || !dashboardData.sources.git.repos) {
        content.innerHTML = '<div class="empty-state">' + icon('refresh-cw') + ' Load dashboard first</div>';
        refreshIcons();
        return;
    }

    var html = '';
    dashboardData.sources.git.repos.forEach(function(repo) {
        var cls = repo.is_dirty ? 'item item-warning' : 'item';
        var commits = '';
        if (repo.commits) {
            repo.commits.forEach(function(c) {
                var parts = c.split(' ');
                var hash = parts[0];
                var msg = parts.slice(1).join(' ');
                commits += '<div class="commit"><span class="commit-hash">' + escapeHtml(hash) + '</span> ' + escapeHtml(msg) + '</div>';
            });
        }

        html += '<div class="' + cls + '">';
        html += '<div class="item-title">' + icon('folder-git-2') + ' ' + escapeHtml(repo.name) + '</div>';
        html += '<div class="item-meta">';
        html += '<span class="tag">' + icon('git-branch') + ' ' + escapeHtml(repo.branch || 'unknown') + '</span>';
        html += ' ' + repo.commit_count + ' commits';
        if (repo.is_dirty) html += ' ' + icon('alert-triangle') + ' dirty';
        if (repo.ahead) html += ' ' + icon('arrow-up') + ' ' + repo.ahead;
        if (repo.behind) html += ' ' + icon('arrow-down') + ' ' + repo.behind;
        html += '</div>';
        html += commits;
        html += '</div>';
    });

    content.innerHTML = html;
    refreshIcons();
}

function renderTasksDetails() {
    var content = document.getElementById('tasks-detail-content');
    if (!content) return;

    if (!dashboardData || !dashboardData.sources.todoist || !dashboardData.sources.todoist.tasks) {
        content.innerHTML = '<div class="empty-state">' + icon('refresh-cw') + ' Load dashboard first</div>';
        refreshIcons();
        return;
    }

    var html = '';
    dashboardData.sources.todoist.tasks.forEach(function(task) {
        var cls = task.is_overdue ? 'item item-urgent' : task.is_today ? 'item item-active' : 'item';
        var priorityClass = getPriorityClass(task.priority);

        html += '<div class="' + cls + '">';
        html += '<div class="item-header">';
        html += '<span class="item-priority ' + priorityClass + '"></span>';
        html += '<div class="item-title">' + escapeHtml(task.content) + '</div>';
        html += '</div>';
        html += '<div class="item-meta">';
        html += '<span class="tag">' + icon('folder') + ' ' + escapeHtml(task.project) + '</span>';
        html += ' ' + (task.due_date ? 'Due: ' + escapeHtml(task.due_date) : 'No due date');
        html += '</div></div>';
    });

    content.innerHTML = html;
    refreshIcons();
}

function renderLinearDetails() {
    var inProgressContent = document.getElementById('linear-inprogress-content');
    var todoContent = document.getElementById('linear-todo-content');
    var backlogContent = document.getElementById('linear-backlog-content');

    if (!dashboardData || !dashboardData.sources.linear || !dashboardData.sources.linear.issues) {
        var emptyHtml = '<div class="empty-state">' + icon('refresh-cw') + ' Load dashboard first</div>';
        if (inProgressContent) inProgressContent.innerHTML = emptyHtml;
        if (todoContent) todoContent.innerHTML = emptyHtml;
        if (backlogContent) backlogContent.innerHTML = emptyHtml;
        refreshIcons();
        return;
    }

    var linear = dashboardData.sources.linear;
    var issues = linear.issues || [];
    var byStatus = linear.by_status || {};

    var inProgress = issues.filter(function(i) { return i.state_type === 'started'; }).length;
    var todo = (byStatus['Todo'] || []).length;
    var backlog = (byStatus['Backlog'] || []).length;

    var totalEl = document.getElementById('linear-stat-total');
    var inProgressEl = document.getElementById('linear-stat-inprogress');
    var todoEl = document.getElementById('linear-stat-todo');
    var backlogEl = document.getElementById('linear-stat-backlog');

    if (totalEl) totalEl.textContent = issues.length;
    if (inProgressEl) inProgressEl.textContent = inProgress;
    if (todoEl) todoEl.textContent = todo;
    if (backlogEl) backlogEl.textContent = backlog;

    function renderIssueList(issueList) {
        if (!issueList || !issueList.length) return '<div class="empty-state">' + icon('inbox') + ' None</div>';
        var html = '';
        issueList.forEach(function(issue) {
            var priorityClass = getPriorityClass(issue.priority);
            html += '<div class="item">';
            html += '<div class="item-header">';
            html += '<span class="item-priority ' + priorityClass + '"></span>';
            html += '<div class="item-title">' + escapeHtml(issue.identifier) + ' ' + escapeHtml(issue.title) + '</div>';
            html += '</div>';
            html += '<div class="item-meta">';
            if (issue.project) html += '<span class="tag">' + escapeHtml(issue.project) + '</span>';
            if (issue.due_date) html += ' Due: ' + escapeHtml(issue.due_date);
            html += '</div></div>';
        });
        return html;
    }

    var inProgressIssues = issues.filter(function(i) { return i.state_type === 'started'; });
    if (inProgressContent) inProgressContent.innerHTML = renderIssueList(inProgressIssues);
    if (todoContent) todoContent.innerHTML = renderIssueList(byStatus['Todo']);
    if (backlogContent) backlogContent.innerHTML = renderIssueList(byStatus['Backlog']);
    refreshIcons();
}

// =============================================================================
// Charts
// =============================================================================

function updateStats(data) {
    var gitData = data.git || [];
    var totalCommits = gitData.reduce(function(sum, d) { return sum + (d.total_commits || 0); }, 0);
    var activeRepos = gitData.length > 0 ? gitData[gitData.length - 1].repos_with_activity || 0 : 0;

    var commitsEl = document.getElementById('stat-commits');
    var activeReposEl = document.getElementById('stat-active-repos');
    if (commitsEl) commitsEl.textContent = totalCommits;
    if (activeReposEl) activeReposEl.textContent = activeRepos;

    if (dashboardData) {
        var todayTasks = dashboardData.sources.todoist && dashboardData.sources.todoist.tasks
            ? dashboardData.sources.todoist.tasks.filter(function(t) { return t.is_today; }).length
            : 0;
        var inProgressCol = dashboardData.sources.kanban && dashboardData.sources.kanban.by_column
            ? dashboardData.sources.kanban.by_column['in-progress'] || {}
            : {};
        var inProgress = Object.keys(inProgressCol).length;

        var tasksEl = document.getElementById('stat-tasks');
        var kanbanEl = document.getElementById('stat-kanban');
        if (tasksEl) tasksEl.textContent = todayTasks;
        if (kanbanEl) kanbanEl.textContent = inProgress;
    }
}

function renderCharts(data) {
    var gitData = data.git || [];
    var kanbanData = data.kanban || [];
    var linearData = data.linear || [];

    // Git Chart - bar chart for daily commits
    var gitCanvas = document.getElementById('chart-git');
    if (gitCanvas) {
        var gitCtx = gitCanvas.getContext('2d');
        if (gitChart) gitChart.destroy();

        gitChart = new Chart(gitCtx, {
            type: 'bar',
            data: {
                labels: gitData.map(function(d) { return new Date(d.date).toLocaleDateString('en-GB', {day: 'numeric', month: 'short'}); }),
                datasets: [{
                    label: 'Daily Commits',
                    data: gitData.map(function(d) { return d.total_commits || 0; }),
                    backgroundColor: 'rgba(56, 178, 172, 0.7)',
                    borderColor: '#38b2ac',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true, position: 'top', align: 'start', labels: { color: '#a0aec0', boxWidth: 12, padding: 16 } }
                },
                scales: {
                    x: { grid: { color: '#2d3748' }, ticks: { color: '#718096' } },
                    y: { grid: { color: '#2d3748' }, ticks: { color: '#718096' }, beginAtZero: true }
                }
            }
        });
    }

    // Kanban Chart
    var kanbanCanvas = document.getElementById('chart-kanban');
    if (kanbanCanvas) {
        var kanbanCtx = kanbanCanvas.getContext('2d');
        if (kanbanChart) kanbanChart.destroy();

        kanbanChart = new Chart(kanbanCtx, {
            type: 'line',
            data: {
                labels: kanbanData.map(function(d) { return new Date(d.date).toLocaleDateString('en-GB', {day: 'numeric', month: 'short'}); }),
                datasets: [
                    { label: 'Backlog', data: kanbanData.map(function(d) { return d.avg_backlog || 0; }), borderColor: '#718096', tension: 0.3 },
                    { label: 'Ready', data: kanbanData.map(function(d) { return d.avg_ready || 0; }), borderColor: '#68d391', tension: 0.3 },
                    { label: 'In Progress', data: kanbanData.map(function(d) { return d.avg_in_progress || 0; }), borderColor: '#0bc5ea', tension: 0.3 },
                    { label: 'Done', data: kanbanData.map(function(d) { return d.avg_done || 0; }), borderColor: '#b794f4', tension: 0.3 }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top', align: 'start', labels: { color: '#a0aec0', boxWidth: 12, padding: 16 } } },
                scales: {
                    x: { grid: { color: '#2d3748' }, ticks: { color: '#718096' } },
                    y: { grid: { color: '#2d3748' }, ticks: { color: '#718096' }, beginAtZero: true }
                }
            }
        });
    }

    // Linear Chart
    var linearCanvas = document.getElementById('chart-linear');
    if (linearCanvas) {
        var linearCtx = linearCanvas.getContext('2d');
        if (linearChart) linearChart.destroy();

        linearChart = new Chart(linearCtx, {
            type: 'line',
            data: {
                labels: linearData.map(function(d) { return new Date(d.date).toLocaleDateString('en-GB', {day: 'numeric', month: 'short'}); }),
                datasets: [
                    { label: 'Total Issues', data: linearData.map(function(d) { return d.avg_total || 0; }), borderColor: '#38b2ac', backgroundColor: 'rgba(56, 178, 172, 0.1)', fill: true, tension: 0.3 },
                    { label: 'In Progress', data: linearData.map(function(d) { return d.statuses ? d.statuses['In Progress'] || 0 : 0; }), borderColor: '#0bc5ea', tension: 0.3 },
                    { label: 'Todo', data: linearData.map(function(d) { return d.statuses ? d.statuses['Todo'] || 0 : 0; }), borderColor: '#f6ad55', tension: 0.3 },
                    { label: 'Backlog', data: linearData.map(function(d) { return d.statuses ? d.statuses['Backlog'] || 0 : 0; }), borderColor: '#718096', tension: 0.3 }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top', align: 'start', labels: { color: '#a0aec0', boxWidth: 12, padding: 16 } } },
                scales: {
                    x: { grid: { color: '#2d3748' }, ticks: { color: '#718096' } },
                    y: { grid: { color: '#2d3748' }, ticks: { color: '#718096' }, beginAtZero: true }
                }
            }
        });
    }
}

// =============================================================================
// Standup Functions - all user content is escaped
// =============================================================================

async function loadStandup() {
    try {
        var resp = await fetch('/api/standup');
        standupData = await resp.json();
        renderStandup(standupData);
    } catch (e) {
        console.error('Standup error:', e);
    }
}

function renderStandup(data) {
    var dateEl = document.getElementById('standup-date');
    if (dateEl) dateEl.textContent = data.day_name;

    var weatherEl = document.getElementById('standup-weather');
    if (weatherEl) {
        if (data.weather && data.weather.status === 'ok') {
            weatherEl.innerHTML = '<div style="font-size: 2rem; margin-bottom: 0.5rem;">' + escapeHtml(data.weather.condition) + '</div>' +
                '<div style="font-size: 1.5rem; color: var(--accent-teal);">' + escapeHtml(data.weather.temp_c) + '°C</div>' +
                '<div style="color: var(--text-muted); margin-top: 0.5rem;">' +
                icon('droplets') + ' ' + escapeHtml(data.weather.humidity) + '% · ' + icon('wind') + ' ' + escapeHtml(data.weather.wind_kph) + ' km/h</div>';
        } else {
            weatherEl.innerHTML = '<div class="empty-state">' + icon('cloud-off') + ' Weather unavailable</div>';
        }
    }

    var summaryEl = document.getElementById('standup-summary');
    if (summaryEl) {
        summaryEl.innerHTML = '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; text-align: center;">' +
            '<div><div style="font-size: 2rem; color: var(--color-urgent);">' + data.summary.overdue_count + '</div><div style="font-size: 0.75rem; color: var(--text-muted);">Overdue</div></div>' +
            '<div><div style="font-size: 2rem; color: var(--accent-teal);">' + data.summary.today_count + '</div><div style="font-size: 0.75rem; color: var(--text-muted);">Today</div></div>' +
            '<div><div style="font-size: 2rem; color: var(--accent-cyan);">' + data.summary.in_progress_count + '</div><div style="font-size: 0.75rem; color: var(--text-muted);">In Progress</div></div>' +
            '</div>';
    }

    var overdueCountEl = document.getElementById('standup-overdue-count');
    var overdueEl = document.getElementById('standup-overdue');
    if (overdueCountEl) overdueCountEl.textContent = data.tasks.overdue.length;
    if (overdueEl) {
        if (data.tasks.overdue.length) {
            var html = '';
            data.tasks.overdue.forEach(function(t) {
                html += '<div class="context-item overdue"><div>' + escapeHtml(t.content) + '</div>' +
                    '<div style="font-size: 0.75rem; color: var(--text-muted);">' + escapeHtml(t.project) + ' · ' + escapeHtml(t.due_date) + '</div></div>';
            });
            overdueEl.innerHTML = html;
        } else {
            overdueEl.innerHTML = '<div class="empty-state">' + icon('check-circle') + ' No overdue tasks!</div>';
        }
    }

    var todayCountEl = document.getElementById('standup-today-count');
    var todayEl = document.getElementById('standup-today');
    if (todayCountEl) todayCountEl.textContent = data.tasks.today.length;
    if (todayEl) {
        if (data.tasks.today.length) {
            var html = '';
            data.tasks.today.forEach(function(t) {
                var priorityClass = getPriorityClass(t.priority);
                html += '<div class="context-item today"><div><span class="item-priority ' + priorityClass + '" style="display: inline-block;"></span> ' + escapeHtml(t.content) + '</div>' +
                    '<div style="font-size: 0.75rem; color: var(--text-muted);">' + escapeHtml(t.project) + '</div></div>';
            });
            todayEl.innerHTML = html;
        } else {
            todayEl.innerHTML = '<div class="empty-state">No tasks scheduled for today</div>';
        }
    }

    var inProgressCountEl = document.getElementById('standup-inprogress-count');
    var inProgressEl = document.getElementById('standup-inprogress');
    if (inProgressCountEl) inProgressCountEl.textContent = data.kanban.in_progress.length;
    if (inProgressEl) {
        if (data.kanban.in_progress.length) {
            var html = '';
            data.kanban.in_progress.forEach(function(t) {
                html += '<div class="context-item in-progress"><div>' + escapeHtml(t.title) + '</div>';
                if (t.tags && t.tags.length) {
                    html += '<div style="font-size: 0.75rem; color: var(--text-muted);">' + t.tags.map(function(tag) { return escapeHtml(tag); }).join(', ') + '</div>';
                }
                html += '</div>';
            });
            inProgressEl.innerHTML = html;
        } else {
            inProgressEl.innerHTML = '<div class="empty-state">' + icon('coffee') + ' Nothing in progress</div>';
        }
    }

    refreshIcons();
}

// =============================================================================
// Planning Chat Functions - all user content is escaped
// =============================================================================

async function loadPlanContext() {
    try {
        var resp = await fetch('/api/standup');
        var data = await resp.json();
        renderPlanContext(data);
    } catch (e) {
        console.error('Plan context error:', e);
    }
}

function renderPlanContext(data) {
    var contextEl = document.getElementById('plan-context');
    if (!contextEl) return;

    var html = '';

    if (data.tasks.overdue.length) {
        html += '<div class="context-section"><div class="context-section-title">' + icon('alert-triangle') + ' Overdue (' + data.tasks.overdue.length + ')</div>';
        data.tasks.overdue.slice(0, 5).forEach(function(t) {
            html += '<div class="context-item overdue">' + escapeHtml(t.content) + '</div>';
        });
        html += '</div>';
    }

    if (data.tasks.today.length) {
        html += '<div class="context-section"><div class="context-section-title">' + icon('calendar') + ' Today (' + data.tasks.today.length + ')</div>';
        data.tasks.today.slice(0, 8).forEach(function(t) {
            var priorityClass = getPriorityClass(t.priority);
            html += '<div class="context-item today"><span class="item-priority ' + priorityClass + '" style="display: inline-block;"></span> ' + escapeHtml(t.content) + '</div>';
        });
        html += '</div>';
    }

    if (data.kanban.in_progress.length) {
        html += '<div class="context-section"><div class="context-section-title">' + icon('play-circle') + ' In Progress (' + data.kanban.in_progress.length + ')</div>';
        data.kanban.in_progress.forEach(function(t) {
            html += '<div class="context-item in-progress">' + escapeHtml(t.title) + '</div>';
        });
        html += '</div>';
    }

    if (data.kanban.ready.length) {
        html += '<div class="context-section"><div class="context-section-title">' + icon('circle') + ' Ready (' + data.kanban.ready.length + ')</div>';
        data.kanban.ready.slice(0, 5).forEach(function(t) {
            html += '<div class="context-item">' + escapeHtml(t.title) + '</div>';
        });
        html += '</div>';
    }

    contextEl.innerHTML = html || '<div class="empty-state">' + icon('inbox') + ' No context available</div>';
    refreshIcons();
}

async function togglePlanSession() {
    if (planSessionId) {
        await endPlanSession();
    } else {
        await startPlanSession();
    }
}

async function startPlanSession() {
    if (!gatewayToken) {
        gatewayToken = prompt('Enter Gateway token (from clawdbot config):');
        if (!gatewayToken) return;
        localStorage.setItem('gateway_token', gatewayToken);
    }

    try {
        var resp = await fetch('/api/planning/session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'start' })
        });
        var data = await resp.json();

        if (data.status === 'ok') {
            planSessionId = data.session_id;
            updateSessionUI(true);

            var messagesEl = document.getElementById('plan-messages');
            if (messagesEl) messagesEl.innerHTML = '';

            connectGateway();
            loadPlanContext();
        }
    } catch (e) {
        console.error('Start session error:', e);
        alert('Failed to start session: ' + e.message);
    }
}

async function endPlanSession() {
    if (!planSessionId) return;

    try {
        await fetch('/api/planning/session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'end', session_id: planSessionId })
        });

        if (planSocket) {
            planSocket.close();
            planSocket = null;
        }

        planSessionId = null;
        updateSessionUI(false);

    } catch (e) {
        console.error('End session error:', e);
    }
}

function updateSessionUI(active) {
    var statusEl = document.getElementById('plan-session-status');
    var btnEl = document.getElementById('plan-session-btn');
    var inputEl = document.getElementById('plan-input');
    var sendBtn = document.getElementById('plan-send-btn');

    if (active) {
        if (statusEl) statusEl.innerHTML = '<span class="connection-status connecting"><span class="dot"></span> Connecting...</span>';
        if (btnEl) btnEl.textContent = 'End Session';
        if (inputEl) inputEl.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
        document.querySelectorAll('.quick-action').forEach(function(b) { b.disabled = false; });
    } else {
        if (statusEl) statusEl.innerHTML = '<span class="connection-status disconnected"><span class="dot"></span> Not connected</span>';
        if (btnEl) btnEl.textContent = 'Start Session';
        if (inputEl) inputEl.disabled = true;
        if (sendBtn) sendBtn.disabled = true;
        document.querySelectorAll('.quick-action').forEach(function(b) { b.disabled = true; });
    }
}

function connectGateway() {
    var wsUrl = 'ws://localhost:18789?token=' + encodeURIComponent(gatewayToken);
    planSocket = new WebSocket(wsUrl);

    planSocket.onopen = function() {
        console.log('Gateway WebSocket connected');
        var statusEl = document.getElementById('plan-session-status');
        if (statusEl) statusEl.innerHTML = '<span class="connection-status connected"><span class="dot"></span> Connected</span>';
    };

    planSocket.onmessage = function(event) {
        try {
            var msg = JSON.parse(event.data);
            handleGatewayMessage(msg);
        } catch (e) {
            console.error('Gateway message parse error:', e);
        }
    };

    planSocket.onerror = function(error) {
        console.error('Gateway WebSocket error:', error);
        var statusEl = document.getElementById('plan-session-status');
        if (statusEl) statusEl.innerHTML = '<span class="connection-status disconnected"><span class="dot"></span> Error</span>';
    };

    planSocket.onclose = function(event) {
        console.log('Gateway WebSocket closed:', event.code, event.reason);
        var statusEl = document.getElementById('plan-session-status');
        if (statusEl && planSessionId) {
            statusEl.innerHTML = '<span class="connection-status disconnected"><span class="dot"></span> Disconnected</span>';
        }
    };
}

function handleGatewayMessage(msg) {
    if (msg.type === 'chat') {
        var event = msg.event || msg;

        if (event.kind === 'text' || event.kind === 'chunk') {
            if (!currentAssistantMessage) {
                currentAssistantMessage = addChatMessage('assistant', '');
            }
            var contentEl = currentAssistantMessage.querySelector('.message-content');
            if (contentEl) contentEl.textContent += event.text || '';
            scrollChat();
        }

        if (event.kind === 'done' || event.kind === 'end') {
            if (currentAssistantMessage) {
                var contentEl = currentAssistantMessage.querySelector('.message-content');
                if (contentEl) logPlanMessage('assistant', contentEl.textContent);
            }
            currentAssistantMessage = null;
            removeTypingIndicator();
        }

        if (event.kind === 'tool_start') {
            var statusEl = document.getElementById('plan-session-status');
            if (statusEl) statusEl.innerHTML = '<span class="connection-status connected"><span class="dot"></span> Using ' + escapeHtml(event.tool || 'tool') + '...</span>';
        }
    }

    if (msg.type === 'error') {
        addChatMessage('system', 'Error: ' + escapeHtml(msg.message || 'Unknown error'));
        removeTypingIndicator();
    }
}

function addChatMessage(role, content) {
    var messages = document.getElementById('plan-messages');
    if (!messages) return null;

    var div = document.createElement('div');
    div.className = 'chat-message ' + role;

    var contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content; // Use textContent for safety

    var timestampDiv = document.createElement('div');
    timestampDiv.className = 'timestamp';
    timestampDiv.textContent = new Date().toLocaleTimeString();

    div.appendChild(contentDiv);
    div.appendChild(timestampDiv);
    messages.appendChild(div);
    scrollChat();
    return div;
}

function addTypingIndicator() {
    removeTypingIndicator();
    var messages = document.getElementById('plan-messages');
    if (!messages) return;

    var div = document.createElement('div');
    div.id = 'typing-indicator';
    div.className = 'chat-message assistant';
    div.innerHTML = '<div class="chat-typing"><span></span><span></span><span></span></div>';
    messages.appendChild(div);
    scrollChat();
}

function removeTypingIndicator() {
    var indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
}

function scrollChat() {
    var messages = document.getElementById('plan-messages');
    if (messages) messages.scrollTop = messages.scrollHeight;
}

async function sendPlanMessage() {
    var input = document.getElementById('plan-input');
    if (!input) return;

    var message = input.value.trim();
    if (!message || !planSessionId) return;

    input.value = '';

    addChatMessage('user', message);
    logPlanMessage('user', message);

    addTypingIndicator();

    var context = standupData ? '\nCurrent planning context:\n- Overdue tasks: ' + (standupData.tasks && standupData.tasks.overdue ? standupData.tasks.overdue.length : 0) +
        '\n- Today\'s tasks: ' + (standupData.tasks && standupData.tasks.today ? standupData.tasks.today.length : 0) +
        '\n- In progress: ' + (standupData.kanban && standupData.kanban.in_progress ? standupData.kanban.in_progress.length : 0) +
        '\n\nOverdue: ' + (standupData.tasks && standupData.tasks.overdue ? standupData.tasks.overdue.slice(0, 5).map(function(t) { return t.content; }).join(', ') : 'None') +
        '\nToday: ' + (standupData.tasks && standupData.tasks.today ? standupData.tasks.today.slice(0, 5).map(function(t) { return t.content; }).join(', ') : 'None') +
        '\n' : '';

    if (planSocket && planSocket.readyState === WebSocket.OPEN) {
        var rpcMessage = {
            id: Date.now(),
            type: 'rpc',
            method: 'chat.send',
            params: {
                message: context + '\n\nUser request: ' + message,
                sessionKey: 'main'
            }
        };
        planSocket.send(JSON.stringify(rpcMessage));
    } else {
        removeTypingIndicator();
        addChatMessage('system', 'Not connected - click Start Session to reconnect');
    }
}

function sendQuickAction(action) {
    var input = document.getElementById('plan-input');
    if (input) {
        input.value = action;
        sendPlanMessage();
    }
}

async function logPlanMessage(role, content) {
    if (!planSessionId) return;
    try {
        await fetch('/api/planning/message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: planSessionId,
                role: role,
                content: content
            })
        });
    } catch (e) {
        console.error('Log message error:', e);
    }
}

// =============================================================================
// Overnight Sprint Functions - all user content is escaped
// =============================================================================

async function loadOvernight() {
    var content = document.getElementById('overnight-content');
    var history = document.getElementById('overnight-history');
    var dateBadge = document.getElementById('overnight-date');
    var historyCount = document.getElementById('overnight-history-count');

    if (!content || !history) return;

    try {
        var sprintsResp = await fetch('/api/overnight/sprints?limit=20');
        var sprintsData = await sprintsResp.json();
        overnightSprints = sprintsData.sprints || [];

        if (overnightSprints.length === 0) {
            history.innerHTML = '<div class="empty-state">' + icon('scroll') + ' No sprints yet</div>';
            content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">' + icon('moon') + '</div>' +
                '<div class="empty-state-text">No overnight sprints found</div>' +
                '<div class="empty-state-hint">Sprint logs are stored in ~/obsidian/claude/1-Projects/0-Dev/01-JeeveSprints/</div></div>';
            if (dateBadge) dateBadge.textContent = '-';
            if (historyCount) historyCount.textContent = '0';
            refreshIcons();
            return;
        }

        if (historyCount) historyCount.textContent = overnightSprints.length;

        var historyHtml = '';
        overnightSprints.forEach(function(s, idx) {
            var statusIcon = getStatusIcon(s.status);
            var isSelected = (idx === 0 && !selectedSprintId) || s.id === selectedSprintId;
            historyHtml += '<div class="sprint-history-item ' + (isSelected ? 'selected' : '') + '" onclick="selectSprint(\'' + s.id + '\')">';
            historyHtml += '<div class="item-title" style="display: flex; justify-content: space-between;"><span>' + escapeHtml(s.date) + '</span><span>' + statusIcon + '</span></div>';
            historyHtml += '<div class="item-meta" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">' + escapeHtml(s.task_title || 'Sprint') + '</div>';
            historyHtml += '<div class="item-meta">' + s.tasks_completed + '/' + s.tasks_total + ' tasks · ' + s.gates_passed + '/' + s.gates_total + ' gates</div>';
            historyHtml += '</div>';
        });
        history.innerHTML = historyHtml;

        if (!selectedSprintId && overnightSprints.length > 0) {
            selectedSprintId = overnightSprints[0].id;
        }

        renderSprintDetails(selectedSprintId);
        refreshIcons();

    } catch (e) {
        console.error('Overnight error:', e);
        content.innerHTML = '<div class="error-message">' + icon('alert-circle') + ' Failed to load overnight data: ' + escapeHtml(e.message) + '</div>';
        refreshIcons();
    }
}

function getStatusIcon(status) {
    switch (status) {
        case 'completed': return icon('check-circle', 'text-success');
        case 'in-progress': return icon('play-circle', 'text-info');
        case 'blocked': return icon('x-circle', 'text-urgent');
        case 'pending': return icon('clock', 'text-warning');
        default: return icon('help-circle');
    }
}

function selectSprint(sprintId) {
    selectedSprintId = sprintId;
    loadOvernight();
}

function renderSprintDetails(sprintId) {
    var content = document.getElementById('overnight-content');
    var dateBadge = document.getElementById('overnight-date');

    if (!content) return;

    var sprint = overnightSprints.find(function(s) { return s.id === sprintId; });
    if (!sprint) {
        content.innerHTML = '<div class="empty-state">' + icon('search') + ' Sprint not found</div>';
        refreshIcons();
        return;
    }

    if (dateBadge) dateBadge.textContent = sprint.date;

    var statusClass = '';
    if (sprint.status === 'completed') statusClass = 'completed';
    else if (sprint.status === 'in-progress') statusClass = 'in-progress';
    else if (sprint.status === 'blocked') statusClass = 'blocked';
    else if (sprint.status === 'pending') statusClass = 'pending';

    var progressPercent = sprint.tasks_total > 0 ? (sprint.tasks_completed / sprint.tasks_total * 100).toFixed(0) : 0;

    var html = '<div>';
    html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">';
    html += '<div><h3 style="margin: 0; font-size: 1.1rem;">' + escapeHtml(sprint.task_title || 'Overnight Sprint') + '</h3>';
    html += '<div style="font-size: 0.85rem; color: var(--text-muted);">Task: ' + escapeHtml(String(sprint.task_id) || 'N/A') + '</div></div>';
    html += '<div class="sprint-status-badge ' + statusClass + '">' + getStatusIcon(sprint.status) + ' ' + escapeHtml(sprint.status) + '</div>';
    html += '</div>';

    html += '<div style="margin-bottom: 1rem;">';
    html += '<div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">';
    html += '<span style="font-size: 0.8rem; color: var(--text-muted);">Progress</span>';
    html += '<span style="font-size: 0.8rem; color: var(--text-muted);">' + sprint.tasks_completed + '/' + sprint.tasks_total + '</span></div>';
    html += '<div class="progress-bar"><div class="progress-bar-fill" style="width: ' + progressPercent + '%;"></div></div></div>';

    html += '<div style="margin-bottom: 1.5rem;">';
    html += '<div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">Quality Gates: ' + sprint.gates_passed + '/' + sprint.gates_total + '</div>';
    html += '<div class="quality-gates">';

    var gateNames = ['tests_passing', 'no_lint_errors', 'docs_updated', 'committed_to_branch', 'self_validated', 'happy_path_works', 'edge_cases_handled', 'pal_reviewed'];
    var gateLabels = ['Tests', 'Lint', 'Docs', 'Committed', 'Validated', 'Happy Path', 'Edge Cases', 'PAL'];

    gateNames.forEach(function(gate, i) {
        var passed = sprint.quality_gates && sprint.quality_gates[gate];
        html += '<span class="quality-gate ' + (passed ? 'passed' : 'failed') + '">' + (passed ? icon('check') : icon('circle')) + ' ' + gateLabels[i] + '</span>';
    });

    html += '</div></div>';

    // Activity items
    if (sprint.items && sprint.items.length > 0) {
        html += '<div style="margin-bottom: 1.5rem;">';
        html += '<div style="font-size: 0.9rem; font-weight: 500; color: var(--text-muted); margin-bottom: 0.75rem;">' + icon('clipboard-list') + ' Activity Log</div>';

        sprint.items.forEach(function(item) {
            var itemIcon = item.status === 'completed' ? icon('check-circle', 'text-success') : icon('x-circle', 'text-urgent');
            var borderColor = item.status === 'completed' ? 'var(--accent-green)' : 'var(--accent-coral)';
            html += '<div class="item" style="border-left-color: ' + borderColor + ';">';
            html += '<div class="item-title">' + itemIcon + ' ' + escapeHtml(item.title) + '</div>';
            if (item.result) html += '<div class="item-meta">' + escapeHtml(item.result) + '</div>';
            html += '</div>';
        });

        html += '</div>';
    }

    // Decisions
    if (sprint.decisions && sprint.decisions.length > 0) {
        html += '<div style="margin-bottom: 1.5rem;">';
        html += '<div style="font-size: 0.9rem; font-weight: 500; color: var(--text-muted); margin-bottom: 0.75rem;">' + icon('lightbulb') + ' Decisions</div>';
        sprint.decisions.forEach(function(d) {
            var decisionText = typeof d === 'string' ? d : (d.decision || d.question || JSON.stringify(d));
            var rationale = typeof d === 'object' && d.rationale ? '<div class="item-meta">' + escapeHtml(d.rationale) + '</div>' : '';
            html += '<div class="item" style="border-left-color: var(--accent-purple);"><div class="item-title">' + escapeHtml(decisionText) + '</div>' + rationale + '</div>';
        });
        html += '</div>';
    }

    // Deviations
    if (sprint.deviations && sprint.deviations.length > 0) {
        html += '<div style="margin-bottom: 1.5rem;">';
        html += '<div style="font-size: 0.9rem; font-weight: 500; color: var(--text-muted); margin-bottom: 0.75rem;">' + icon('alert-triangle') + ' Deviations</div>';
        sprint.deviations.forEach(function(d) {
            var devText = typeof d === 'string' ? d : (d.deviation || JSON.stringify(d));
            var reason = typeof d === 'object' && d.reason ? '<div class="item-meta">' + escapeHtml(d.reason) + '</div>' : '';
            html += '<div class="item" style="border-left-color: var(--accent-orange);"><div class="item-title">' + escapeHtml(devText) + '</div>' + reason + '</div>';
        });
        html += '</div>';
    }

    // Block reason
    if (sprint.block_reason) {
        html += '<div class="error-message" style="margin-top: 1rem;">' + icon('x-circle') + ' <strong>Blocked:</strong> ' + escapeHtml(sprint.block_reason) + '</div>';
    }

    html += '</div>';
    content.innerHTML = html;
    refreshIcons();
}

// =============================================================================
// Needs Attention Section (Unified Alerts)
// =============================================================================

/**
 * Populate the Needs Attention section with aggregated alerts
 */
function populateNeedsAttention() {
    if (!dashboardData) return;
    
    var container = document.getElementById('needs-attention-items');
    var emptyState = document.getElementById('needs-attention-empty');
    var countBadge = document.getElementById('needs-attention-count');
    
    if (!container || !emptyState) return;
    
    var items = [];
    
    // Add overdue tasks
    if (dashboardData.sources.todoist && dashboardData.sources.todoist.tasks) {
        dashboardData.sources.todoist.tasks.filter(function(t) { return t.is_overdue; }).forEach(function(task) {
            items.push({
                type: 'overdue',
                icon: 'alert-triangle',
                title: task.content,
                meta: (task.project_name || 'Inbox') + ' • Due: ' + formatDate(task.due_date),
                priority: task.priority,
                actions: [
                    { label: 'Complete', onclick: 'completeTask("' + task.id + '")' },
                    { label: 'Reschedule', onclick: 'rescheduleTask("' + task.id + '")' }
                ]
            });
        });
    }
    
    // Add dirty repos
    if (dashboardData.sources.git && dashboardData.sources.git.repos) {
        dashboardData.sources.git.repos.filter(function(r) { return r.is_dirty; }).forEach(function(repo) {
            items.push({
                type: 'dirty',
                icon: 'git-branch',
                title: repo.name,
                meta: repo.branch + ' • ' + (repo.uncommitted_count || 'uncommitted') + ' changes',
                actions: [
                    { label: 'View Diff', onclick: 'openRepoModal("' + escapeHtml(repo.name) + '")' }
                ]
            });
        });
    }
    
    // Update count
    if (countBadge) countBadge.textContent = items.length;
    
    if (items.length === 0) {
        emptyState.style.display = 'block';
        container.style.display = 'none';
        return;
    }
    
    emptyState.style.display = 'none';
    container.style.display = 'block';
    
    var html = '';
    items.forEach(function(item) {
        var priorityClass = item.priority ? ' priority-' + item.priority : '';
        html += '<div class="attention-item' + priorityClass + '">';
        html += '<div class="attention-item-main">';
        html += '<span class="attention-icon">' + icon(item.icon) + '</span>';
        html += '<div class="attention-content">';
        html += '<div class="attention-title">' + escapeHtml(item.title) + '</div>';
        html += '<div class="attention-meta">' + escapeHtml(item.meta) + '</div>';
        html += '</div>';
        html += '</div>';
        if (item.actions && item.actions.length > 0) {
            html += '<div class="attention-actions">';
            item.actions.forEach(function(action) {
                html += '<button class="btn-ghost" onclick="' + action.onclick + '">' + action.label + '</button>';
            });
            html += '</div>';
        }
        html += '</div>';
    });
    
    container.innerHTML = html;
    refreshIcons();
}

/**
 * Toggle Needs Attention section collapse
 */
function toggleNeedsAttention() {
    var content = document.getElementById('needs-attention-content');
    var chevron = document.getElementById('needs-attention-chevron');
    if (content) content.classList.toggle('collapsed');
    if (chevron) chevron.classList.toggle('rotated');
}

/**
 * Toggle Git Repos section collapse
 */
function toggleGitRepos() {
    var content = document.getElementById('git-content');
    var chevron = document.getElementById('git-chevron');
    if (content) content.classList.toggle('collapsed');
    if (chevron) chevron.classList.toggle('rotated');
}

/**
 * Update Git summary bar
 */
function updateGitSummary() {
    if (!dashboardData || !dashboardData.sources.git) return;
    
    var git = dashboardData.sources.git;
    var repos = git.repos || [];
    var dirty = repos.filter(function(r) { return r.is_dirty; }).length;
    var totalCommits = repos.reduce(function(sum, r) { return sum + (r.commit_count || 0); }, 0);
    
    var summary = document.getElementById('git-summary');
    if (summary) {
        summary.textContent = repos.length + ' repos • ' + dirty + ' dirty • ' + totalCommits + ' commits';
    }
}

// =============================================================================
// In Progress & Ready Items
// =============================================================================

/**
 * Populate In Progress section
 */
function populateInProgress() {
    if (!dashboardData) return;
    
    var container = document.getElementById('inprogress-content');
    var countBadge = document.getElementById('inprogress-count');
    if (!container) return;
    
    var items = [];
    
    // Get in-progress from Kanban
    if (dashboardData.sources.kanban && dashboardData.sources.kanban.by_column) {
        var inProgress = dashboardData.sources.kanban.by_column['in-progress'] || [];
        inProgress.forEach(function(task) {
            items.push({
                source: 'kanban',
                title: task.title,
                meta: 'Kanban'
            });
        });
    }
    
    // Get in-progress from Linear
    if (dashboardData.sources.linear && dashboardData.sources.linear.by_status) {
        var linearInProgress = dashboardData.sources.linear.by_status['In Progress'] || [];
        linearInProgress.forEach(function(issue) {
            items.push({
                source: 'linear',
                title: issue.title,
                meta: issue.identifier + ' • Linear'
            });
        });
    }
    
    if (countBadge) countBadge.textContent = items.length;
    
    if (items.length === 0) {
        container.innerHTML = '<div class="empty-state">' +
            '<div class="empty-state-icon">' + icon('rocket') + '</div>' +
            '<div class="empty-state-text">Nothing actively in progress</div>' +
            '<div class="empty-state-hint">Ready to start something?</div>' +
            '<button class="btn-secondary" onclick="showReadyItems()">' + icon('list') + ' View Ready Items</button>' +
            '</div>';
        refreshIcons();
        return;
    }
    
    var html = '';
    items.forEach(function(item) {
        html += '<div class="progress-item">';
        html += '<span class="progress-icon">' + icon(item.source === 'linear' ? 'bar-chart-3' : 'trello') + '</span>';
        html += '<div class="progress-content">';
        html += '<div class="progress-title">' + escapeHtml(item.title) + '</div>';
        html += '<div class="progress-meta">' + escapeHtml(item.meta) + '</div>';
        html += '</div>';
        html += '</div>';
    });
    
    container.innerHTML = html;
    refreshIcons();
}

/**
 * Populate Ready / Next Up section
 */
function populateReadyItems() {
    if (!dashboardData) return;
    
    var container = document.getElementById('ready-content');
    var badge = document.getElementById('ready-badge');
    var readyCountEl = document.getElementById('ready-count');
    if (!container) return;
    
    var items = [];
    
    // Get ready items from Kanban
    if (dashboardData.sources.kanban && dashboardData.sources.kanban.by_column) {
        var ready = dashboardData.sources.kanban.by_column['ready'] || [];
        ready.forEach(function(task) {
            items.push({
                source: 'kanban',
                title: task.title,
                meta: 'Kanban • Ready'
            });
        });
    }
    
    // Get backlog items from Linear (top 3)
    if (dashboardData.sources.linear && dashboardData.sources.linear.by_status) {
        var backlog = dashboardData.sources.linear.by_status['Backlog'] || [];
        backlog.slice(0, 3).forEach(function(issue) {
            items.push({
                source: 'linear',
                title: issue.title,
                meta: issue.identifier + ' • Linear Backlog'
            });
        });
    }
    
    if (badge) badge.textContent = items.length;
    if (readyCountEl) readyCountEl.textContent = items.length;
    
    if (items.length === 0) {
        container.innerHTML = '<div class="empty-state-mini">No ready items</div>';
        return;
    }
    
    var html = '';
    items.slice(0, 5).forEach(function(item) {
        html += '<div class="ready-item">';
        html += '<span class="ready-icon">' + icon(item.source === 'linear' ? 'bar-chart-3' : 'list-checks') + '</span>';
        html += '<div class="ready-content">';
        html += '<div class="ready-title">' + escapeHtml(item.title) + '</div>';
        html += '<div class="ready-meta">' + escapeHtml(item.meta) + '</div>';
        html += '</div>';
        html += '</div>';
    });
    
    container.innerHTML = html;
    refreshIcons();
}

/**
 * Populate Activity Summary
 */
function populateActivitySummary() {
    if (!dashboardData) return;
    
    var container = document.getElementById('activity-content');
    if (!container) return;
    
    var git = dashboardData.sources.git || {};
    var repos = git.repos || [];
    var totalCommits = repos.reduce(function(sum, r) { return sum + (r.commit_count || 0); }, 0);
    var activeRepos = repos.filter(function(r) { return r.commit_count > 0; }).length;
    
    var html = '<div class="activity-summary">';
    html += '<div class="activity-row">';
    html += '<span class="activity-label">' + icon('git-commit') + ' Commits today</span>';
    html += '<span class="activity-value">' + totalCommits + '</span>';
    html += '</div>';
    html += '<div class="activity-row">';
    html += '<span class="activity-label">' + icon('folder') + ' Active repos</span>';
    html += '<span class="activity-value">' + activeRepos + '</span>';
    html += '</div>';
    
    // Overnight sprint status if available
    if (overnightSprints && overnightSprints.length > 0) {
        var latestSprint = overnightSprints[0];
        var sprintIcon = latestSprint.status === 'completed' ? 'check-circle' : 'clock';
        html += '<div class="activity-row">';
        html += '<span class="activity-label">' + icon('moon') + ' Last sprint</span>';
        html += '<span class="activity-value">' + icon(sprintIcon) + ' ' + latestSprint.status + '</span>';
        html += '</div>';
    }
    
    html += '</div>';
    
    container.innerHTML = html;
    refreshIcons();
}

/**
 * Show ready items modal
 */
function showReadyItems() {
    // For now, just scroll to or expand the ready section
    var readyCard = document.getElementById('ready-card');
    if (readyCard) {
        readyCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

/**
 * Navigate to Plan tab for AI suggestions
 */
function askJeevesForFocus() {
    switchTab('plan');
    // Could auto-send a message here in the future
}

// Placeholder functions for task actions
function completeTask(taskId) {
    console.log('Complete task:', taskId);
    // TODO: Implement Todoist API call
}

function rescheduleTask(taskId) {
    console.log('Reschedule task:', taskId);
    // TODO: Implement Todoist API call
}

// =============================================================================
// Initialization
// =============================================================================

function init() {
    initModal();

    var attentionBadge = document.getElementById('attention-badge');
    if (attentionBadge) {
        attentionBadge.addEventListener('click', toggleAttentionDropdown);
    }

    document.addEventListener('click', function(e) {
        var badge = document.getElementById('attention-badge');
        var dropdown = document.getElementById('attention-dropdown');
        if (badge && dropdown && !badge.contains(e.target)) {
            dropdown.classList.remove('open');
        }
    });

    document.querySelectorAll('.tab').forEach(function(tab) {
        tab.addEventListener('click', function() {
            var tabId = tab.getAttribute('data-tab');
            if (tabId) switchTab(tabId);
        });
    });

    var planInput = document.getElementById('plan-input');
    if (planInput) {
        planInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') sendPlanMessage();
        });
    }

    refreshIcons();
    refreshAll();
    loadOvernight();
}

document.addEventListener('DOMContentLoaded', init);
