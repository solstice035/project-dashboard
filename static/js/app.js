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
let gatewayToken = localStorage.getItem('gateway_token') || '';
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
// Toast Notification System
// =============================================================================

/**
 * Show a toast notification
 * @param {string} message - The message to display
 * @param {string} type - Type: 'info', 'success', 'error', 'warning'
 * @param {number} duration - Duration in ms (0 for persistent)
 */
function showToast(message, type, duration) {
    type = type || 'info';
    duration = duration !== undefined ? duration : 4000;

    var container = document.getElementById('toast-container');
    if (!container) return;

    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;

    var iconName = {
        success: 'check-circle',
        error: 'x-circle',
        warning: 'alert-triangle',
        info: 'info'
    }[type] || 'info';

    var iconEl = document.createElement('i');
    iconEl.setAttribute('data-lucide', iconName);
    iconEl.className = 'toast-icon';

    var content = document.createElement('span');
    content.className = 'toast-content';
    content.textContent = message;

    var closeIcon = document.createElement('i');
    closeIcon.setAttribute('data-lucide', 'x');

    var closeBtn = document.createElement('button');
    closeBtn.className = 'toast-close';
    closeBtn.appendChild(closeIcon);
    closeBtn.onclick = function() { dismissToast(toast); };

    toast.appendChild(iconEl);
    toast.appendChild(content);
    toast.appendChild(closeBtn);
    container.appendChild(toast);

    // Initialize Lucide icons within toast
    if (typeof lucide !== 'undefined') {
        lucide.createIcons({ nodes: [toast] });
    }

    // Trigger animation
    requestAnimationFrame(function() {
        toast.classList.add('show');
    });

    if (duration > 0) {
        setTimeout(function() { dismissToast(toast); }, duration);
    }

    return toast;
}

/**
 * Dismiss a toast notification
 */
function dismissToast(toast) {
    toast.classList.remove('show');
    setTimeout(function() {
        if (toast.parentNode) {
            toast.remove();
        }
    }, 300);
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
        case 'life':
            loadLifeDashboard();
            break;
        case 'plan':
            loadPlanContext();
            loadStandup();
            break;
        case 'analytics':
            loadAnalytics();
            break;
        case 'school':
            loadSchoolTab();
            break;
        case 'financial':
            loadFinancialTab();
            break;
        case 'rss':
            loadRssEntries();
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

    ['git', 'todoist', 'kanban', 'linear', 'rss'].forEach(function(s) {
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
        
        // Sync XP from dashboard activity
        syncXpFromDashboard();
        
        // Fetch inbox digest (separate async call)
        fetchAndRenderInbox();
        
        // Fetch school email summary
        fetchAndRenderSchool();
        
        // Fetch RSS/News summary
        loadRssSummary();

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

        html += '<div class="' + cls + '" onclick="openTaskModal(\'' + escapeHtml(String(task.id)) + '\')">';
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
            html += '<div class="item item-active" onclick="openKanbanModal(\'' + escapeHtml(String(t.id)) + '\')">';
            html += '<div class="item-title">' + escapeHtml(t.title) + '</div></div>';
        });
    }
    if (ready.length) {
        html += '<div class="context-section-title" style="margin-top: var(--spacing-md);">' + icon('circle') + ' Ready</div>';
        ready.slice(0, 2).forEach(function(t) {
            html += '<div class="item" onclick="openKanbanModal(\'' + escapeHtml(String(t.id)) + '\')">';
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

        html += '<div class="' + cls + '" onclick="openLinearModal(\'' + escapeHtml(String(issue.id)) + '\')">';
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

/**
 * Fetch and render inbox digest
 */
async function fetchAndRenderInbox() {
    var content = document.getElementById('inbox-content');
    var count = document.getElementById('inbox-count');
    if (!content) return;

    content.innerHTML = '<div class="skeleton"></div>';

    try {
        var response = await fetch('/api/inbox/digest');
        var data = await response.json();
        renderInbox(data);
    } catch (error) {
        console.error('Inbox fetch error:', error);
        content.innerHTML = '<div class="error-message">' + icon('alert-circle') + ' Failed to load inbox</div>';
        if (count) count.textContent = '!';
        refreshIcons();
    }
}

/**
 * Render inbox digest - all user content is escaped
 */
function renderInbox(data) {
    var content = document.getElementById('inbox-content');
    var count = document.getElementById('inbox-count');
    if (!content) return;

    if (!data.accounts || !data.accounts.length) {
        content.innerHTML = '<div class="empty-state"><div class="empty-state-icon">' + icon('mail') + '</div><div class="empty-state-text">No email accounts configured</div></div>';
        if (count) count.textContent = '-';
        refreshIcons();
        return;
    }

    var totalUnread = data.summary ? data.summary.total_unread : 0;
    var totalUrgent = data.summary ? data.summary.total_urgent : 0;

    if (count) {
        if (totalUrgent > 0) {
            count.textContent = totalUrgent + ' urgent';
            count.classList.add('urgent');
        } else {
            count.textContent = totalUnread + ' unread';
            count.classList.remove('urgent');
        }
    }

    var html = '';

    data.accounts.forEach(function(account) {
        var statusIcon = account.status === 'ok' ? 'check-circle' : (account.status === 'timeout' ? 'clock' : 'alert-circle');
        var statusClass = account.status === 'ok' ? 'ok' : 'warning';

        html += '<div class="inbox-account">';
        html += '<div class="inbox-account-header">';
        html += '<span class="inbox-account-name">' + icon('mail') + ' ' + escapeHtml(account.name || account.account) + '</span>';
        html += '<span class="inbox-account-count ' + statusClass + '">' + (account.total_unread || 0) + '</span>';
        html += '</div>';

        if (account.status !== 'ok') {
            html += '<div class="inbox-error">' + icon(statusIcon) + ' ' + escapeHtml(account.error || account.status) + '</div>';
        } else {
            // Urgent items
            if (account.urgent && account.urgent.length > 0) {
                html += '<div class="inbox-section urgent">';
                html += '<span class="inbox-label">' + icon('alert-circle') + ' Urgent</span>';
                account.urgent.slice(0, 3).forEach(function(msg) {
                    html += '<div class="inbox-item">';
                    html += '<span class="inbox-from">' + escapeHtml(msg.from) + '</span>';
                    html += '<span class="inbox-subject">' + escapeHtml(msg.subject) + '</span>';
                    html += '</div>';
                });
                html += '</div>';
            }

            // From people (if no urgent, show these)
            if ((!account.urgent || account.urgent.length === 0) && account.from_people && account.from_people.length > 0) {
                html += '<div class="inbox-section">';
                html += '<span class="inbox-label">' + icon('user') + ' From People</span>';
                account.from_people.slice(0, 3).forEach(function(msg) {
                    html += '<div class="inbox-item">';
                    html += '<span class="inbox-from">' + escapeHtml(msg.from) + '</span>';
                    html += '<span class="inbox-subject">' + escapeHtml(msg.subject) + '</span>';
                    html += '</div>';
                });
                html += '</div>';
            }

            // Newsletter count
            if (account.newsletters > 0) {
                html += '<div class="inbox-newsletters">' + icon('newspaper') + ' ' + account.newsletters + ' newsletters</div>';
            }
        }

        html += '</div>';
    });

    content.innerHTML = html;
    refreshIcons();
}

/**
 * Fetch and render school email summary
 */
async function fetchAndRenderSchool() {
    var content = document.getElementById('school-content');
    var count = document.getElementById('school-count');
    if (!content) return;

    content.innerHTML = '<div class="skeleton"></div>';

    try {
        var response = await fetch('/api/school/summary');
        var data = await response.json();
        renderSchool(data);
    } catch (error) {
        console.error('School fetch error:', error);
        content.innerHTML = '<div class="error-message">' + icon('alert-circle') + ' Failed to load school data</div>';
        if (count) count.textContent = '!';
        refreshIcons();
    }
}

/**
 * Render school email summary - all user content is escaped
 */
function renderSchool(data) {
    var content = document.getElementById('school-content');
    var count = document.getElementById('school-count');
    if (!content) return;

    if (data.status === 'not_configured') {
        content.innerHTML = '<div class="setup-prompt">' + icon('info') + ' School automation not set up yet</div>';
        if (count) count.textContent = '-';
        refreshIcons();
        return;
    }

    if (data.status === 'error') {
        content.innerHTML = '<div class="error-message">' + icon('alert-circle') + ' ' + escapeHtml(data.error) + '</div>';
        if (count) count.textContent = '!';
        refreshIcons();
        return;
    }

    var summary = data.summary || {};
    var byChild = data.by_child || {};
    var byUrgency = data.by_urgency || {};
    var recentEmails = data.recent_emails || [];

    // Set badge
    var pendingActions = summary.pending_actions || 0;
    var highUrgency = byUrgency['HIGH'] || 0;
    
    if (count) {
        if (highUrgency > 0) {
            count.textContent = highUrgency + ' urgent';
            count.classList.add('urgent');
        } else if (pendingActions > 0) {
            count.textContent = pendingActions + ' pending';
            count.classList.remove('urgent');
        } else {
            count.textContent = summary.recent_email_count || 0;
            count.classList.remove('urgent');
        }
    }

    var html = '';

    // Children summary
    html += '<div class="school-children">';
    var children = summary.children || ['Elodie', 'Nathaniel', 'Florence'];
    children.forEach(function(child) {
        var childData = byChild[child] || {emails: 0, actions: 0};
        html += '<div class="school-child">';
        html += '<span class="school-child-name">' + icon('user') + ' ' + escapeHtml(child) + '</span>';
        html += '<span class="school-child-stats">' + childData.emails + ' emails, ' + childData.actions + ' actions</span>';
        html += '</div>';
    });
    html += '</div>';

    // Urgency breakdown
    if (Object.keys(byUrgency).length > 0) {
        html += '<div class="school-urgency">';
        var urgencyColors = {'HIGH': 'urgent', 'MEDIUM': 'warning', 'LOW': 'info', 'INFO': 'muted'};
        for (var urg in byUrgency) {
            html += '<span class="school-urgency-badge ' + (urgencyColors[urg] || '') + '">' + urg + ': ' + byUrgency[urg] + '</span>';
        }
        html += '</div>';
    }

    // Recent emails (last 3)
    if (recentEmails.length > 0) {
        html += '<div class="school-recent">';
        html += '<span class="inbox-label">' + icon('mail') + ' Recent</span>';
        recentEmails.slice(0, 3).forEach(function(email) {
            html += '<div class="school-email">';
            html += '<span class="school-email-child">' + escapeHtml(email.child || '?') + '</span>';
            html += '<span class="school-email-subject">' + escapeHtml((email.subject || '').substring(0, 40)) + '</span>';
            html += '</div>';
        });
        html += '</div>';
    }

    // Process button
    html += '<div class="school-actions">';
    html += '<button class="btn-secondary btn-sm" onclick="triggerSchoolProcess()">' + icon('refresh-cw') + ' Process New</button>';
    html += '</div>';

    content.innerHTML = html;
    refreshIcons();
}

/**
 * Trigger school email processing
 */
async function triggerSchoolProcess() {
    try {
        var response = await fetch('/api/school/process', {method: 'POST'});
        var data = await response.json();
        if (data.status === 'started') {
            showToast('School email processing started', 'success');
        } else {
            showToast('Failed to start: ' + (data.error || 'unknown'), 'error');
        }
    } catch (error) {
        showToast('Failed to trigger processing', 'error');
    }
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
// =============================================================================
// Health Data Integration (Apple Health)
// =============================================================================

let healthData = null;

/**
 * Load health data from Apple Health analytics
 */
async function loadHealthData() {
    try {
        const resp = await fetch('/api/life/health');
        healthData = await resp.json();
        
        if (healthData.status !== 'ok') {
            console.warn('Health data not available:', healthData.message);
            renderHealthUnavailable(healthData.message);
            return;
        }
        
        renderHealthStats();
        renderHealthInsights();
        updateHealthScore();
        
    } catch (e) {
        console.error('Health data fetch error:', e);
        renderHealthUnavailable('Failed to load health data');
    }
}

/**
 * Render health stats in the stat cards
 */
function renderHealthStats() {
    if (!healthData || !healthData.today) return;
    
    const today = healthData.today;
    
    // Steps
    const stepsEl = document.getElementById('health-steps');
    if (stepsEl) {
        const steps = today.steps || 0;
        stepsEl.textContent = steps.toLocaleString();
        stepsEl.parentElement.classList.toggle('stat-success', steps >= 10000);
    }
    
    // Exercise minutes
    const exerciseEl = document.getElementById('health-exercise');
    if (exerciseEl) {
        const mins = today.exercise_minutes || 0;
        exerciseEl.textContent = mins + 'm';
        exerciseEl.parentElement.classList.toggle('stat-success', mins >= 30);
    }
    
    // Resting HR
    const rhrEl = document.getElementById('health-rhr');
    if (rhrEl) {
        const rhr = today.resting_hr;
        rhrEl.textContent = rhr ? rhr + ' bpm' : '-';
        // Lower is better for resting HR
        if (rhr) {
            rhrEl.parentElement.classList.toggle('stat-success', rhr < 60);
        }
    }
}

/**
 * Update health score display
 */
function updateHealthScore() {
    if (!healthData || !healthData.health_score) return;
    
    const score = healthData.health_score;
    const scoreEl = document.getElementById('health-score-value');
    const cardEl = document.getElementById('health-score-card');
    
    if (scoreEl) {
        scoreEl.textContent = score.score;
    }
    
    if (cardEl) {
        // Color based on score level
        cardEl.classList.remove('stat-success', 'stat-warning', 'stat-danger');
        if (score.score >= 80) {
            cardEl.classList.add('stat-success');
        } else if (score.score >= 50) {
            cardEl.classList.add('stat-warning');
        } else {
            cardEl.classList.add('stat-danger');
        }
        cardEl.title = score.description || '';
    }
    
    // Update the Life Pulse XP widget with health-based XP
    const lifePulseXp = document.getElementById('life-pulse-xp');
    if (lifePulseXp && healthData.summary) {
        // Calculate XP from health activities
        const summary = healthData.summary;
        let xp = 0;
        
        // 1 XP per 1000 steps
        xp += Math.floor((healthData.today?.steps || 0) / 1000) * 10;
        // 2 XP per exercise minute
        xp += (healthData.today?.exercise_minutes || 0) * 2;
        // 5 XP for hitting stand goal
        if ((healthData.today?.stand_hours || 0) >= 12) xp += 50;
        
        lifePulseXp.textContent = '+' + xp;
    }
}

/**
 * Render health insights
 */
function renderHealthInsights() {
    const container = document.getElementById('health-insights-content');
    if (!container) return;
    
    if (!healthData || !healthData.insights || healthData.insights.length === 0) {
        container.innerHTML = '<div class="empty-state-mini">No insights available</div>';
        return;
    }
    
    let html = '<div class="health-insights-list">';
    healthData.insights.forEach(function(insight) {
        const typeClass = insight.type === 'positive' ? 'insight-positive' : 
                          insight.type === 'warning' ? 'insight-warning' : 'insight-neutral';
        html += '<div class="insight-item ' + typeClass + '">';
        html += '<span class="insight-icon">' + (insight.icon || '💡') + '</span>';
        html += '<div class="insight-content">';
        html += '<strong>' + escapeHtml(insight.title) + '</strong>';
        html += '<span>' + escapeHtml(insight.text) + '</span>';
        html += '</div>';
        html += '</div>';
    });
    html += '</div>';
    
    container.innerHTML = html;
}

/**
 * Render health unavailable state
 */
function renderHealthUnavailable(message) {
    const container = document.getElementById('health-insights-content');
    if (container) {
        container.innerHTML = '<div class="empty-state-mini">' + 
            '<i data-lucide="heart-off" class="icon"></i> ' +
            escapeHtml(message || 'Health data not available') +
            '</div>';
        refreshIcons();
    }
    
    // Clear stats
    ['health-steps', 'health-exercise', 'health-rhr', 'health-score-value'].forEach(function(id) {
        const el = document.getElementById(id);
        if (el) el.textContent = '-';
    });
}

/**
 * Refresh health data (triggered by button)
 */
async function refreshHealthData() {
    showToast('Refreshing health data...', 'info', 2000);
    
    try {
        // First try to regenerate
        const refreshResp = await fetch('/api/life/health/refresh', { method: 'POST' });
        const refreshResult = await refreshResp.json();
        
        if (refreshResult.status === 'ok') {
            showToast('Health data regenerated!', 'success');
        }
        
        // Then reload
        await loadHealthData();
        
    } catch (e) {
        console.error('Health refresh error:', e);
        showToast('Failed to refresh health data', 'error');
    }
}

// =============================================================================
// Life Balance Tab
// =============================================================================

let lifeData = null;
let lifeRadarChart = null;

/**
 * Load life dashboard data
 */
async function loadLifeDashboard() {
    // Load health data first (real data)
    loadHealthData();
    
    // Then try gamification data (may not exist yet)
    try {
        const resp = await fetch('/api/life/dashboard');
        lifeData = await resp.json();
        
        if (lifeData.error) {
            console.error('Life dashboard error:', lifeData.error);
            return;
        }
        
        renderLifeHeader();
        renderLifeAreas();
        renderStreaks();
        renderAchievements();
        renderLifeRadar();
        renderProgressRings();
        renderHeatmap();
        
        // Also load days since
        loadDaysSince();
        
    } catch (e) {
        console.error('Life dashboard fetch error:', e);
    }
}

/**
 * Render the XP header bar
 */
function renderLifeHeader() {
    if (!lifeData) return;

    var levelEl = document.getElementById('life-level');
    var titleEl = document.getElementById('life-title');
    var xpEl = document.getElementById('life-xp');
    var progressFill = document.getElementById('xp-progress-fill');
    var progressText = document.getElementById('xp-progress-text');
    var todayXp = document.getElementById('today-xp');
    var lifePulseXp = document.getElementById('life-pulse-xp');

    if (levelEl) levelEl.textContent = 'Lv ' + lifeData.level;
    if (titleEl) titleEl.textContent = lifeData.level_title;
    if (xpEl) xpEl.textContent = lifeData.total_xp.toLocaleString() + ' XP';
    if (progressFill) progressFill.style.width = lifeData.level_progress + '%';
    if (progressText) progressText.textContent = lifeData.xp_to_next.toLocaleString() + ' XP to next level';
    if (todayXp) todayXp.textContent = '+' + lifeData.today_xp;

    // Update Life Pulse widget in header
    if (lifePulseXp) lifePulseXp.textContent = '+' + lifeData.today_xp;
}

/**
 * Render life area cards
 */
function renderLifeAreas() {
    if (!lifeData || !lifeData.areas) return;
    
    var container = document.getElementById('life-areas-grid');
    if (!container) return;
    
    var html = '';
    lifeData.areas.forEach(function(area) {
        var weeklyXp = lifeData.weekly_xp[area.code] || 0;
        var progress = Math.min(100, (area.today_xp / area.daily_xp_cap) * 100);
        
        html += '<div class="life-area-card" onclick="showAreaDetails(\'' + area.code + '\')">';
        html += '<div class="life-area-header">';
        html += '<div class="life-area-icon" style="background: ' + area.color + '20; color: ' + area.color + ';">';
        html += icon(area.icon);
        html += '</div>';
        html += '<span class="life-area-name">' + escapeHtml(area.name) + '</span>';
        html += '<span class="life-area-xp">Lv ' + area.level + '</span>';
        html += '</div>';
        html += '<div class="life-area-progress">';
        html += '<div class="life-area-progress-fill" style="width: ' + progress + '%; background: ' + area.color + ';"></div>';
        html += '</div>';
        html += '<div class="life-area-stats">';
        html += '<span>Today: ' + area.today_xp + '/' + area.daily_xp_cap + '</span>';
        html += '<span>Week: ' + weeklyXp + '</span>';
        html += '</div>';
        html += '</div>';
    });
    
    container.innerHTML = html;
    refreshIcons();
}

/**
 * Render streaks
 */
function renderStreaks() {
    if (!lifeData || !lifeData.streaks) return;
    
    var container = document.getElementById('streaks-content');
    if (!container) return;
    
    if (lifeData.streaks.length === 0) {
        container.innerHTML = '<div class="empty-state-mini">No streaks yet</div>';
        return;
    }
    
    var html = '';
    lifeData.streaks.forEach(function(streak) {
        var isActive = streak.current_streak > 0;
        html += '<div class="streak-item">';
        html += '<div class="streak-info">';
        html += '<span class="streak-icon' + (isActive ? ' active' : '') + '">' + icon('flame') + '</span>';
        html += '<span class="streak-name">' + escapeHtml(streak.activity.replace(/_/g, ' ')) + '</span>';
        html += '</div>';
        html += '<span class="streak-count' + (streak.current_streak === 0 ? ' zero' : '') + '">' + streak.current_streak + '</span>';
        html += '</div>';
    });
    
    container.innerHTML = html;
    refreshIcons();
}

/**
 * Render recent achievements
 */
function renderAchievements() {
    if (!lifeData || !lifeData.achievements) return;
    
    var container = document.getElementById('achievements-content');
    if (!container) return;
    
    if (lifeData.achievements.length === 0) {
        container.innerHTML = '<div class="empty-state-mini">No achievements earned yet. Keep going!</div>';
        return;
    }
    
    var html = '';
    lifeData.achievements.forEach(function(ach) {
        html += '<div class="achievement-item">';
        html += '<div class="achievement-icon ' + ach.rarity + '">' + icon(ach.icon || 'star') + '</div>';
        html += '<div class="achievement-info">';
        html += '<div class="achievement-name">' + escapeHtml(ach.name) + '</div>';
        html += '<div class="achievement-desc">' + escapeHtml(ach.description) + '</div>';
        html += '</div>';
        html += '<span class="achievement-xp">+' + ach.xp_reward + '</span>';
        html += '</div>';
    });
    
    container.innerHTML = html;
    refreshIcons();
}

/**
 * Render life balance radar chart
 */
function renderLifeRadar() {
    if (!lifeData || !lifeData.areas) return;
    
    var canvas = document.getElementById('life-radar-chart');
    if (!canvas) return;
    
    var labels = lifeData.areas.map(function(a) { return a.name; });
    var values = lifeData.areas.map(function(a) {
        var weekly = lifeData.weekly_xp[a.code] || 0;
        var maxWeekly = a.daily_xp_cap * 7;
        return Math.min(100, (weekly / maxWeekly) * 100);
    });
    var colors = lifeData.areas.map(function(a) { return a.color; });
    
    if (lifeRadarChart) {
        lifeRadarChart.destroy();
    }
    
    lifeRadarChart = new Chart(canvas, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: 'This Week',
                data: values,
                backgroundColor: 'rgba(56, 178, 172, 0.2)',
                borderColor: 'rgba(56, 178, 172, 1)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(56, 178, 172, 1)',
                pointBorderColor: '#fff',
                pointRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        display: false
                    },
                    grid: {
                        color: 'rgba(255,255,255,0.1)'
                    },
                    angleLines: {
                        color: 'rgba(255,255,255,0.1)'
                    },
                    pointLabels: {
                        color: '#a0aec0',
                        font: { size: 11 }
                    }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

/**
 * Render progress rings (Canvas-based)
 */
function renderProgressRings() {
    if (!lifeData || !lifeData.areas) return;
    
    var canvas = document.getElementById('rings-canvas');
    var legend = document.getElementById('rings-legend');
    if (!canvas || !legend) return;
    
    var ctx = canvas.getContext('2d');
    var centerX = canvas.width / 2;
    var centerY = canvas.height / 2;
    var maxRadius = 90;
    var ringWidth = 12;
    var ringGap = 4;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw rings for top 4 areas (by today's activity)
    var topAreas = lifeData.areas.slice(0, 4);
    var legendHtml = '';
    
    topAreas.forEach(function(area, i) {
        var radius = maxRadius - (i * (ringWidth + ringGap));
        var progress = Math.min(1, area.today_xp / area.daily_xp_cap);
        
        // Background ring
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
        ctx.strokeStyle = 'rgba(255,255,255,0.1)';
        ctx.lineWidth = ringWidth;
        ctx.stroke();
        
        // Progress ring
        if (progress > 0) {
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, -Math.PI / 2, -Math.PI / 2 + (2 * Math.PI * progress));
            ctx.strokeStyle = area.color;
            ctx.lineWidth = ringWidth;
            ctx.lineCap = 'round';
            ctx.stroke();
        }
        
        legendHtml += '<div class="ring-legend-item">';
        legendHtml += '<span class="ring-legend-dot" style="background: ' + area.color + ';"></span>';
        legendHtml += '<span>' + escapeHtml(area.name) + '</span>';
        legendHtml += '<span class="ring-legend-value">' + Math.round(progress * 100) + '%</span>';
        legendHtml += '</div>';
    });
    
    legend.innerHTML = legendHtml;
}

/**
 * Render activity heatmap
 */
function renderHeatmap() {
    if (!lifeData || !lifeData.heatmap) return;
    
    var container = document.getElementById('activity-heatmap');
    if (!container) return;
    
    // Create 12 weeks of data
    var today = new Date();
    var startDate = new Date(today);
    startDate.setDate(startDate.getDate() - 83); // 12 weeks back
    
    // Build XP lookup
    var xpByDate = {};
    lifeData.heatmap.forEach(function(d) {
        xpByDate[d.date] = d.xp;
    });
    
    // Find max XP for scaling
    var maxXp = Math.max.apply(null, lifeData.heatmap.map(function(d) { return d.xp; })) || 100;
    
    var html = '<div class="heatmap-grid">';
    var currentDate = new Date(startDate);
    
    for (var week = 0; week < 12; week++) {
        html += '<div class="heatmap-week">';
        for (var day = 0; day < 7; day++) {
            var dateStr = currentDate.toISOString().split('T')[0];
            var xp = xpByDate[dateStr] || 0;
            var level = 0;
            if (xp > 0) level = Math.min(5, Math.ceil((xp / maxXp) * 5));
            
            html += '<div class="heatmap-day level-' + level + '" title="' + dateStr + ': ' + xp + ' XP"></div>';
            currentDate.setDate(currentDate.getDate() + 1);
        }
        html += '</div>';
    }
    html += '</div>';
    
    html += '<div class="heatmap-labels">';
    html += '<span>Less</span>';
    html += '<div style="display: flex; gap: 2px;">';
    for (var l = 0; l <= 5; l++) {
        html += '<div class="heatmap-day level-' + l + '" style="width: 10px; height: 10px;"></div>';
    }
    html += '</div>';
    html += '<span>More</span>';
    html += '</div>';
    
    container.innerHTML = html;
}

/**
 * Calculate and award XP from dashboard data
 * Called after dashboard refresh to sync XP with actual activity
 */
async function syncXpFromDashboard() {
    if (!dashboardData) return;
    
    var xpUpdates = [];
    
    // Work XP from commits
    if (dashboardData.sources.git && dashboardData.sources.git.repos) {
        var totalCommits = dashboardData.sources.git.repos.reduce(function(sum, r) {
            return sum + (r.commit_count || 0);
        }, 0);
        if (totalCommits > 0) {
            xpUpdates.push({ area: 'work', xp: Math.min(totalCommits * 5, 100), activity: 'commits' });
        }
    }
    
    // Work XP from completed tasks
    if (dashboardData.sources.todoist && dashboardData.sources.todoist.tasks) {
        var completedToday = dashboardData.sources.todoist.completed_today || 0;
        if (completedToday > 0) {
            xpUpdates.push({ area: 'work', xp: Math.min(completedToday * 10, 100), activity: 'tasks_completed' });
        }
    }
    
    // Work XP from sprints
    if (overnightSprints && overnightSprints.length > 0) {
        var todaySprint = overnightSprints.find(function(s) {
            return s.date === new Date().toISOString().split('T')[0];
        });
        if (todaySprint && todaySprint.status === 'completed') {
            xpUpdates.push({ area: 'work', xp: 100, activity: 'sprint_complete' });
        }
    }
    
    // Apply XP updates
    for (var i = 0; i < xpUpdates.length; i++) {
        var update = xpUpdates[i];
        try {
            await fetch('/api/life/xp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(update)
            });
        } catch (e) {
            console.error('XP sync error:', e);
        }
    }
    
    // Refresh life dashboard if on that tab
    var lifeTab = document.getElementById('tab-life');
    if (lifeTab && lifeTab.classList.contains('active')) {
        loadLifeDashboard();
    }
}

// =============================================================================
// Days Since
// =============================================================================

let daysSinceData = null;

/**
 * Load days since data
 */
async function loadDaysSince() {
    try {
        const resp = await fetch('/api/days-since');
        daysSinceData = await resp.json();
        renderDaysSince();
    } catch (e) {
        console.error('Days since error:', e);
    }
}

/**
 * Render days since items
 */
function renderDaysSince() {
    if (!daysSinceData || !daysSinceData.events) return;
    
    var container = document.getElementById('days-since-content');
    if (!container) return;
    
    var html = '';
    daysSinceData.events.forEach(function(event) {
        var statusClass = event.status;
        var daysText = event.days !== null ? event.days + 'd' : 'Never';
        
        html += '<div class="days-since-item ' + statusClass + '" onclick="logDaysSince(\'' + event.code + '\')">';
        html += '<div class="days-since-icon"><i data-lucide="' + event.icon + '" class="icon"></i></div>';
        html += '<div class="days-since-info">';
        html += '<span class="days-since-name">' + escapeHtml(event.name) + '</span>';
        html += '</div>';
        html += '<span class="days-since-value ' + statusClass + '">' + daysText + '</span>';
        html += '</div>';
    });
    
    container.innerHTML = html;
    refreshIcons();
}

/**
 * Log a days-since event (mark as done today)
 */
async function logDaysSince(code) {
    try {
        var resp = await fetch('/api/days-since/' + code + '/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        var data = await resp.json();
        
        if (data.status === 'ok') {
            // Show confirmation
            showXpNotification(0, data.message);
            loadDaysSince();
        }
    } catch (e) {
        console.error('Log days since error:', e);
    }
}

/**
 * Quick log an activity
 */
async function quickLog(activityType) {
    try {
        var resp = await fetch('/api/life/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: activityType })
        });
        
        var data = await resp.json();
        
        if (data.status === 'ok') {
            // Show XP notification
            showXpNotification(data.xp_added, activityType);
            
            // Show achievement notifications
            if (data.achievements && data.achievements.length > 0) {
                data.achievements.forEach(function(ach) {
                    setTimeout(function() {
                        showAchievementNotification(ach);
                    }, 500);
                });
            }
            
            // Refresh life dashboard
            loadLifeDashboard();
        } else {
            console.error('Quick log error:', data);
        }
        
    } catch (e) {
        console.error('Quick log fetch error:', e);
    }
}

/**
 * Show achievement unlocked notification
 */
function showAchievementNotification(achievement) {
    var notification = document.createElement('div');
    notification.className = 'achievement-notification';
    notification.innerHTML = '<div class="achievement-unlock-icon">🏆</div>' +
        '<div class="achievement-unlock-title">Achievement Unlocked!</div>' +
        '<div class="achievement-unlock-name">' + escapeHtml(achievement.name) + '</div>' +
        '<div class="achievement-unlock-xp">+' + achievement.xp + ' XP</div>';
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(function() {
        notification.classList.add('show');
    }, 100);
    
    // Remove after delay
    setTimeout(function() {
        notification.classList.remove('show');
        setTimeout(function() {
            notification.remove();
        }, 500);
    }, 3000);
}

/**
 * Show XP earned notification
 */
function showXpNotification(xp, activity) {
    // Update today's XP with animation
    var todayXpEl = document.getElementById('today-xp');
    if (todayXpEl) {
        todayXpEl.classList.add('xp-earned');
        setTimeout(function() {
            todayXpEl.classList.remove('xp-earned');
        }, 300);
    }
    
    // Create floating notification
    var notification = document.createElement('div');
    notification.className = 'xp-notification';
    notification.innerHTML = '+' + xp + ' XP<br><small>' + activity + '</small>';
    notification.style.cssText = 'position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); ' +
        'background: linear-gradient(135deg, var(--accent), #8b5cf6); color: white; ' +
        'padding: 1rem 2rem; border-radius: 12px; font-size: 1.5rem; font-weight: 700; ' +
        'text-align: center; z-index: 9999; animation: xp-float 1.5s ease forwards;';
    
    document.body.appendChild(notification);
    
    setTimeout(function() {
        notification.remove();
    }, 1500);
}

/**
 * Show area details modal
 */
function showAreaDetails(areaCode) {
    var area = lifeData.areas.find(function(a) { return a.code === areaCode; });
    if (!area) return;
    
    var content = '<div style="text-align: center; padding: 1rem;">';
    content += '<div style="font-size: 3rem; margin-bottom: 1rem;">' + icon(area.icon) + '</div>';
    content += '<h2 style="margin-bottom: 0.5rem;">' + escapeHtml(area.name) + '</h2>';
    content += '<p style="color: var(--text-muted);">Level ' + area.level + ' • ' + area.total_xp + ' Total XP</p>';
    content += '<div style="margin: 1.5rem 0;">';
    content += '<div style="font-size: 2rem; font-weight: 700; color: var(--accent);">' + area.today_xp + '/' + area.daily_xp_cap + '</div>';
    content += '<div style="color: var(--text-muted);">Today\'s XP</div>';
    content += '</div>';
    content += '</div>';
    
    openModal(area.name + ' Details', content, area.icon);
}

/**
 * Show all achievements
 */
async function showAllAchievements() {
    try {
        const resp = await fetch('/api/life/achievements');
        const data = await resp.json();
        
        if (!data.achievements) return;
        
        var content = '<div style="max-height: 400px; overflow-y: auto;">';
        data.achievements.forEach(function(ach) {
            var earned = ach.earned;
            content += '<div class="achievement-item" style="opacity: ' + (earned ? '1' : '0.5') + ';">';
            content += '<div class="achievement-icon ' + ach.rarity + '">' + icon(ach.icon || 'star') + '</div>';
            content += '<div class="achievement-info">';
            content += '<div class="achievement-name">' + escapeHtml(ach.name) + (earned ? ' ✓' : '') + '</div>';
            content += '<div class="achievement-desc">' + escapeHtml(ach.description) + '</div>';
            content += '</div>';
            content += '<span class="achievement-xp">+' + ach.xp_reward + '</span>';
            content += '</div>';
        });
        content += '</div>';
        
        openModal('All Achievements', content, 'trophy');
        refreshIcons();
        
    } catch (e) {
        console.error('Achievements error:', e);
    }
}

// =============================================================================
// School Tab
// =============================================================================

/**
 * Global state for school tab
 */
var schoolTabData = null;
var expandedChildren = {};
var expandedActions = {};

/**
 * Load school tab data from API
 */
async function loadSchoolTab() {
    var container = document.getElementById('school-children-container');
    if (!container) return;

    container.innerHTML = '<div class="skeleton" style="height: 200px;"></div>';

    try {
        var response = await fetch('/api/school/tab');
        schoolTabData = await response.json();
        renderSchoolTab(schoolTabData);
    } catch (error) {
        console.error('School tab error:', error);
        container.innerHTML = '<div class="error-message">' + icon('alert-circle') + ' Failed to load school data</div>';
        refreshIcons();
    }
}

/**
 * Refresh school tab data
 */
function refreshSchoolTab() {
    loadSchoolTab();
    showToast('Refreshing school data...', 'info', 2000);
}

/**
 * Render the full school tab - all user content is escaped via escapeHtml()
 */
function renderSchoolTab(data) {
    var container = document.getElementById('school-children-container');
    if (!container) return;

    // Handle not configured
    if (data.status === 'not_configured') {
        container.innerHTML = '<div class="school-empty-state">' +
            '<div class="empty-state-icon">' + icon('graduation-cap') + '</div>' +
            '<div class="empty-state-text">School automation not set up</div>' +
            '<div class="empty-state-hint">Run school-email-processor to get started</div>' +
            '</div>';
        refreshIcons();
        return;
    }

    // Handle error
    if (data.status === 'error') {
        container.innerHTML = '<div class="error-message">' + icon('alert-circle') + ' ' + escapeHtml(data.error) + '</div>';
        refreshIcons();
        return;
    }

    // Update status bar
    updateSchoolStatus(data.processing_status);

    // Update summary stats
    var totalEl = document.getElementById('school-total-actions');
    var highEl = document.getElementById('school-high-count');
    if (totalEl) totalEl.textContent = data.totals.total;
    if (highEl) highEl.textContent = data.totals.high;

    // Render children sections
    var html = '';
    var children = data.children || [];

    if (children.length === 0 || data.totals.total === 0) {
        html = '<div class="school-empty-state">' +
            '<div class="empty-state-icon">' + icon('check-circle') + '</div>' +
            '<div class="empty-state-text">All clear!</div>' +
            '<div class="empty-state-hint">No pending school actions</div>' +
            '</div>';
    } else {
        children.forEach(function(child) {
            html += renderChildSection(child);
        });
    }

    container.innerHTML = html;
    refreshIcons();
}

/**
 * Update the processing status bar
 */
function updateSchoolStatus(status) {
    var lastRunEl = document.getElementById('school-last-run');
    var actionsCountEl = document.getElementById('school-actions-count');

    if (!status) {
        if (lastRunEl) lastRunEl.textContent = 'Never';
        if (actionsCountEl) actionsCountEl.textContent = '0 actions';
        return;
    }

    if (lastRunEl) {
        lastRunEl.textContent = status.last_run_relative || 'Unknown';
    }
    if (actionsCountEl) {
        actionsCountEl.textContent = status.actions_extracted + ' actions extracted';
    }
}

/**
 * Render a collapsible child section - all user content is escaped
 */
function renderChildSection(child) {
    var isExpanded = expandedChildren[child.name] !== false; // Default to expanded
    var summary = child.summary || {};
    var actions = child.actions || [];

    var headerClass = 'school-child-header' + (isExpanded ? ' expanded' : '');
    var contentClass = 'school-child-content' + (isExpanded ? '' : ' collapsed');

    // Build badges
    var badges = '';
    if (summary.high > 0) {
        badges += '<span class="school-badge urgency-high">' + summary.high + ' high</span>';
    }
    if (summary.medium > 0) {
        badges += '<span class="school-badge urgency-medium">' + summary.medium + ' medium</span>';
    }
    if (summary.low > 0) {
        badges += '<span class="school-badge urgency-low">' + summary.low + ' low</span>';
    }

    var html = '<div class="school-child-section" data-child="' + escapeHtml(child.name) + '">';

    // Header
    html += '<div class="' + headerClass + '" onclick="toggleChildSection(\'' + escapeHtml(child.name) + '\')">';
    html += '<div class="school-child-title">';
    html += icon('user') + ' <span>' + escapeHtml(child.name) + '</span>';
    html += '<span class="school-child-count">(' + summary.total + ')</span>';
    html += '</div>';
    html += '<div class="school-child-badges">' + badges + '</div>';
    html += icon(isExpanded ? 'chevron-up' : 'chevron-down', 'collapse-icon');
    html += '</div>';

    // Content
    html += '<div class="' + contentClass + '">';

    if (actions.length === 0) {
        html += '<div class="school-child-empty">' + icon('check-circle') + ' No pending actions</div>';
    } else {
        actions.forEach(function(action) {
            html += renderActionCard(action, child.name);
        });
    }

    html += '</div></div>';

    return html;
}

/**
 * Render an action card - all user content is escaped
 */
function renderActionCard(action, childName) {
    var isExpanded = expandedActions[action.id] || false;
    var cardClass = 'school-action-card urgency-' + (action.urgency || 'low').toLowerCase();
    if (isExpanded) cardClass += ' expanded';

    var typeIcon = getActionTypeIcon(action.type);

    var html = '<div class="' + cardClass + '" data-action-id="' + escapeHtml(action.id) + '" onclick="toggleActionExpand(\'' + escapeHtml(action.id) + '\')">';

    // Card header
    html += '<div class="school-action-header">';
    html += '<div class="school-action-type">' + icon(typeIcon) + '</div>';
    html += '<div class="school-action-info">';
    html += '<div class="school-action-description">' + escapeHtml(action.description || 'Action') + '</div>';
    if (action.deadline_relative) {
        html += '<div class="school-action-deadline">' + icon('calendar') + ' ' + escapeHtml(action.deadline_relative) + '</div>';
    }
    html += '</div>';
    html += '<div class="school-action-urgency-badge ' + getUrgencyClass(action.urgency) + '">' + escapeHtml(action.urgency || 'LOW') + '</div>';
    html += '</div>';

    // Expandable details
    html += '<div class="school-action-details">';
    if (action.source_email && action.source_email.subject) {
        html += '<div class="school-action-source">';
        html += '<span class="school-action-source-label">' + icon('mail') + ' Source:</span>';
        html += '<span class="school-action-source-text">' + escapeHtml(action.source_email.subject) + '</span>';
        html += '</div>';
    }
    if (action.source_text) {
        html += '<div class="school-action-excerpt">' + escapeHtml(action.source_text.substring(0, 150)) + (action.source_text.length > 150 ? '...' : '') + '</div>';
    }

    // Status indicators
    html += '<div class="school-action-status">';
    if (action.todoist_task_id) {
        html += '<span class="school-action-status-badge synced">' + icon('check') + ' Todoist</span>';
    }
    if (action.calendar_event_id) {
        html += '<span class="school-action-status-badge synced">' + icon('check') + ' Calendar</span>';
    }
    if (!action.todoist_task_id && !action.calendar_event_id) {
        html += '<span class="school-action-status-badge pending">' + icon('clock') + ' Pending sync</span>';
    }
    html += '</div>';
    html += '</div>';

    html += '</div>';

    return html;
}

/**
 * Get urgency CSS class
 */
function getUrgencyClass(urgency) {
    switch ((urgency || '').toUpperCase()) {
        case 'HIGH': return 'urgency-high';
        case 'MEDIUM': return 'urgency-medium';
        case 'LOW': return 'urgency-low';
        default: return 'urgency-info';
    }
}

/**
 * Get icon for action type
 */
function getActionTypeIcon(type) {
    switch ((type || '').toUpperCase()) {
        case 'FORM': return 'file-text';
        case 'EVENT': return 'calendar';
        case 'PAYMENT': return 'credit-card';
        case 'REMINDER': return 'bell';
        case 'NOTIFICATION': return 'info';
        default: return 'clipboard-list';
    }
}

/**
 * Toggle child section expand/collapse
 */
function toggleChildSection(childName) {
    expandedChildren[childName] = expandedChildren[childName] === false;

    var section = document.querySelector('.school-child-section[data-child="' + childName + '"]');
    if (!section) return;

    var header = section.querySelector('.school-child-header');
    var content = section.querySelector('.school-child-content');
    var chevron = header.querySelector('.collapse-icon');

    if (expandedChildren[childName]) {
        header.classList.add('expanded');
        content.classList.remove('collapsed');
        if (chevron) {
            chevron.setAttribute('data-lucide', 'chevron-up');
        }
    } else {
        header.classList.remove('expanded');
        content.classList.add('collapsed');
        if (chevron) {
            chevron.setAttribute('data-lucide', 'chevron-down');
        }
    }

    refreshIcons();
}

/**
 * Toggle action card expand/collapse
 */
function toggleActionExpand(actionId) {
    event.stopPropagation();

    expandedActions[actionId] = !expandedActions[actionId];

    var card = document.querySelector('.school-action-card[data-action-id="' + actionId + '"]');
    if (!card) return;

    if (expandedActions[actionId]) {
        card.classList.add('expanded');
    } else {
        card.classList.remove('expanded');
    }
}

// =============================================================================
// Financial Tab
// =============================================================================

var spendingTrendChart = null;

/**
 * Load Financial tab data
 */
async function loadFinancialTab() {
    try {
        // Fetch summary data
        var response = await fetch('/api/integrations/monzo');
        var result = await response.json();

        if (result.status === 'ok' && result.data) {
            renderFinancialSummary(result.data);
            showElement('financial-stats');
            hideElement('financial-offline');
            updateFinancialStatus('Connected to Monzo', 'ok');
            
            // Fetch trends
            loadFinancialTrends();
            loadFinancialRecurring();
        } else {
            showFinancialOffline(result.message || 'Service unavailable');
        }
    } catch (error) {
        console.error('Financial tab error:', error);
        showFinancialOffline('Failed to connect to Monzo service');
    }
}

/**
 * Render the summary stats
 */
function renderFinancialSummary(data) {
    // Format amounts (values are in pence)
    var balance = document.getElementById('financial-balance');
    var spendToday = document.getElementById('financial-spend-today');
    var spendMonth = document.getElementById('financial-spend-month');
    var transactions = document.getElementById('financial-transactions');

    if (balance) balance.textContent = formatMoney(data.balance);
    if (spendToday) spendToday.textContent = formatMoney(data.spend_today);
    if (spendMonth) spendMonth.textContent = formatMoney(data.spend_this_month);
    if (transactions) transactions.textContent = data.transaction_count.toLocaleString();

    // Render top categories
    renderCategories(data.top_categories || []);
}

/**
 * Format pence to pounds
 */
function formatMoney(pence) {
    if (pence === undefined || pence === null) return '-';
    var pounds = pence / 100;
    return '£' + pounds.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * Render top spending categories
 */
function renderCategories(categories) {
    var container = document.getElementById('financial-categories');
    if (!container) return;

    if (!categories || categories.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No spending data</div></div>';
        return;
    }

    var html = '<div class="category-list">';
    categories.forEach(function(cat) {
        var name = (cat.category || 'general').replace(/_/g, ' ');
        name = name.charAt(0).toUpperCase() + name.slice(1);
        html += '<div class="category-item">';
        html += '<span class="category-name">' + escapeHtml(name) + '</span>';
        html += '<span class="category-amount">' + formatMoney(cat.amount) + '</span>';
        html += '</div>';
    });
    html += '</div>';

    container.innerHTML = html;
}

/**
 * Load spending trends
 */
async function loadFinancialTrends() {
    try {
        // For now, use the same endpoint - the backend needs account_id
        // This will be updated when Monzo is properly configured
        var response = await fetch('/api/integrations/monzo/trends?days=30');
        if (!response.ok) {
            // Trends endpoint may not exist yet - that's ok
            return;
        }
        var data = await response.json();
        if (data.daily_spend) {
            renderSpendingTrend(data.daily_spend);
        }
    } catch (error) {
        console.log('Trends not available:', error.message);
    }
}

/**
 * Render spending trend chart
 */
function renderSpendingTrend(dailySpend) {
    var canvas = document.getElementById('spending-trend-chart');
    if (!canvas) return;

    var ctx = canvas.getContext('2d');

    // Destroy previous chart if exists
    if (spendingTrendChart) {
        spendingTrendChart.destroy();
    }

    var labels = dailySpend.map(function(d) {
        return new Date(d.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    });
    var values = dailySpend.map(function(d) { return d.amount / 100; });

    spendingTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Daily Spend',
                data: values,
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) { return '£' + value; }
                    }
                }
            }
        }
    });
}

/**
 * Load recurring/subscription data
 */
async function loadFinancialRecurring() {
    try {
        var response = await fetch('/api/integrations/monzo/recurring');
        if (!response.ok) return;
        var data = await response.json();
        renderSubscriptions(data);
    } catch (error) {
        console.log('Recurring data not available:', error.message);
    }
}

/**
 * Render subscriptions list
 */
function renderSubscriptions(data) {
    var container = document.getElementById('financial-subscriptions');
    var totalBadge = document.getElementById('subscriptions-total');
    
    if (!container) return;

    var items = data.items || [];
    
    if (totalBadge) {
        totalBadge.textContent = formatMoney(data.total_monthly_cost) + '/mo';
    }

    if (items.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No recurring payments detected</div></div>';
        return;
    }

    var html = '<div class="subscription-list">';
    items.slice(0, 8).forEach(function(sub) {
        html += '<div class="subscription-item">';
        html += '<div class="subscription-info">';
        html += '<span class="subscription-name">' + escapeHtml(sub.merchant_name) + '</span>';
        html += '<span class="subscription-freq">' + escapeHtml(sub.frequency_label) + '</span>';
        html += '</div>';
        html += '<span class="subscription-amount">' + formatMoney(sub.monthly_cost) + '/mo</span>';
        html += '</div>';
    });
    html += '</div>';

    container.innerHTML = html;
}

/**
 * Show offline message
 */
function showFinancialOffline(message) {
    hideElement('financial-stats');
    showElement('financial-offline');
    updateFinancialStatus(message || 'Monzo service offline', 'error');
    
    // Show placeholder categories and subscriptions
    var categories = document.getElementById('financial-categories');
    if (categories) {
        categories.innerHTML = '<div class="empty-state"><div class="empty-state-text">Connect Monzo to see spending</div></div>';
    }
    var subscriptions = document.getElementById('financial-subscriptions');
    if (subscriptions) {
        subscriptions.innerHTML = '<div class="empty-state"><div class="empty-state-text">Connect Monzo to see subscriptions</div></div>';
    }
    var budgets = document.getElementById('financial-budgets');
    if (budgets) {
        budgets.innerHTML = '<div class="empty-state"><div class="empty-state-text">Connect Monzo to see budgets</div></div>';
    }
}

/**
 * Update financial status indicator
 */
function updateFinancialStatus(message, status) {
    var statusEl = document.getElementById('financial-status');
    if (!statusEl) return;
    
    var iconName = status === 'ok' ? 'check-circle' : 'wifi-off';
    statusEl.innerHTML = icon(iconName) + ' <span>' + escapeHtml(message) + '</span>';
    statusEl.className = 'financial-status ' + (status === 'ok' ? 'status-ok' : 'status-error');
}

/**
 * Helper to show element
 */
function showElement(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = '';
}

/**
 * Helper to hide element
 */
function hideElement(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = 'none';
}

// =============================================================================
// Initialization
// =============================================================================

// =============================================================================
// RSS/News Feed Functions
// =============================================================================

let rssCurrentFilter = 'unread';
let rssCurrentCategory = '';

/**
 * Load RSS summary stats
 */
async function loadRssSummary() {
    try {
        const response = await fetch('/api/rss/summary');
        const data = await response.json();
        
        if (data.status === 'ok') {
            document.getElementById('status-rss').classList.remove('loading', 'error');
            document.getElementById('status-rss').classList.add('ok');
            
            document.getElementById('rss-unread').textContent = data.total_unread || 0;
            document.getElementById('rss-feeds').textContent = data.total_feeds || 0;
            document.getElementById('rss-categories').textContent = data.categories || 0;
            
            document.getElementById('rss-status').innerHTML = icon('rss') + ' <span>Connected · ' + (data.total_unread || 0) + ' unread</span>';
            document.getElementById('rss-offline').style.display = 'none';
            
            // Populate category filter
            const select = document.getElementById('rss-category-filter');
            select.innerHTML = '<option value="">All Categories</option>';
            if (data.by_category) {
                Object.entries(data.by_category).forEach(([cat, info]) => {
                    select.innerHTML += '<option value="' + escapeHtml(cat) + '">' + escapeHtml(cat) + ' (' + info.unread + ')</option>';
                });
            }
            
            return data;
        } else {
            throw new Error(data.error || 'Unknown error');
        }
    } catch (e) {
        console.error('RSS summary error:', e);
        document.getElementById('status-rss').classList.remove('loading', 'ok');
        document.getElementById('status-rss').classList.add('error');
        document.getElementById('rss-status').innerHTML = icon('wifi-off') + ' <span>Offline</span>';
        document.getElementById('rss-offline').style.display = 'block';
        return null;
    }
}

/**
 * Load RSS entries
 */
async function loadRssEntries() {
    const container = document.getElementById('rss-entries');
    container.innerHTML = '<div class="skeleton"></div>';
    
    try {
        let url = '/api/rss/entries?limit=100';
        if (rssCurrentFilter === 'starred') {
            url = '/api/rss/entries?status=read&limit=100'; // We'll filter starred client-side
        } else if (rssCurrentFilter !== 'all') {
            url += '&status=' + rssCurrentFilter;
        }
        if (rssCurrentCategory) {
            // Note: category_id would need lookup, for now we filter client-side
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.status !== 'ok') {
            throw new Error(data.error || 'Failed to load entries');
        }
        
        let entries = data.entries || [];
        
        // Client-side filtering for starred
        if (rssCurrentFilter === 'starred') {
            entries = entries.filter(e => e.starred);
        }
        
        // Update starred count
        const starredCount = data.entries ? data.entries.filter(e => e.starred).length : 0;
        document.getElementById('rss-starred').textContent = starredCount;
        
        if (entries.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">' + icon('inbox') + '</div><div class="empty-state-text">No entries found</div></div>';
            refreshIcons();
            return;
        }
        
        // Group by category
        const byCategory = {};
        entries.forEach(entry => {
            const cat = entry.feed?.category?.title || 'Uncategorized';
            if (rssCurrentCategory && cat !== rssCurrentCategory) return;
            if (!byCategory[cat]) byCategory[cat] = [];
            byCategory[cat].push(entry);
        });
        
        let html = '';
        Object.entries(byCategory).forEach(([category, catEntries]) => {
            html += '<div class="rss-category">';
            html += '<div class="rss-category-header">' + icon('folder') + ' ' + escapeHtml(category) + ' <span class="rss-category-count">' + catEntries.length + '</span></div>';
            html += '<div class="rss-entry-list">';
            
            catEntries.forEach(entry => {
                const readingTime = entry.reading_time ? entry.reading_time + ' min' : '';
                const timeAgo = formatTimeAgo(entry.published_at);
                const starClass = entry.starred ? 'starred' : '';
                
                html += '<div class="rss-entry ' + (entry.status === 'read' ? 'read' : '') + '" data-id="' + entry.id + '">';
                html += '<div class="rss-entry-main" onclick="openRssEntry(' + entry.id + ', \'' + escapeHtml(entry.url).replace(/'/g, "\\'") + '\')">';
                html += '<div class="rss-entry-title">' + escapeHtml(entry.title) + '</div>';
                html += '<div class="rss-entry-meta">';
                html += '<span class="rss-entry-feed">' + escapeHtml(entry.feed?.title || 'Unknown') + '</span>';
                html += '<span class="rss-entry-time">' + timeAgo + '</span>';
                if (readingTime) html += '<span class="rss-entry-reading">' + readingTime + '</span>';
                html += '</div>';
                html += '</div>';
                html += '<div class="rss-entry-actions">';
                html += '<button class="rss-action-btn ' + starClass + '" onclick="toggleRssStar(' + entry.id + ')" title="Star">' + icon('star') + '</button>';
                html += '<button class="rss-action-btn" onclick="markRssRead(' + entry.id + ')" title="Mark read">' + icon('check') + '</button>';
                html += '</div>';
                html += '</div>';
            });
            
            html += '</div></div>';
        });
        
        container.innerHTML = html;
        refreshIcons();
        
    } catch (e) {
        console.error('RSS entries error:', e);
        container.innerHTML = '<div class="empty-state error"><div class="empty-state-icon">' + icon('alert-circle') + '</div><div class="empty-state-text">Failed to load entries</div></div>';
        refreshIcons();
    }
}

/**
 * Format time ago
 */
function formatTimeAgo(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 60) return diffMins + 'm ago';
    if (diffHours < 24) return diffHours + 'h ago';
    if (diffDays < 7) return diffDays + 'd ago';
    return formatDate(dateStr);
}

/**
 * Filter RSS by status
 */
function filterRssStatus(status) {
    rssCurrentFilter = status;
    document.querySelectorAll('.rss-filter').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filter === status);
    });
    loadRssEntries();
}

/**
 * Filter RSS by category
 */
function filterRssCategory(category) {
    rssCurrentCategory = category;
    loadRssEntries();
}

/**
 * Open RSS entry in new tab and mark as read
 */
function openRssEntry(id, url) {
    window.open(url, '_blank');
    markRssRead(id);
}

/**
 * Mark entry as read
 */
async function markRssRead(id) {
    try {
        await fetch('/api/rss/entries/' + id + '/read', { method: 'PUT' });
        const entry = document.querySelector('.rss-entry[data-id="' + id + '"]');
        if (entry) entry.classList.add('read');
        
        // Update unread count
        const unreadEl = document.getElementById('rss-unread');
        const current = parseInt(unreadEl.textContent) || 0;
        if (current > 0) unreadEl.textContent = current - 1;
    } catch (e) {
        console.error('Mark read error:', e);
    }
}

/**
 * Toggle star on entry
 */
async function toggleRssStar(id) {
    try {
        await fetch('/api/rss/entries/' + id + '/star', { method: 'PUT' });
        const btn = document.querySelector('.rss-entry[data-id="' + id + '"] .rss-action-btn');
        if (btn) btn.classList.toggle('starred');
    } catch (e) {
        console.error('Star toggle error:', e);
    }
}

/**
 * Refresh RSS data
 */
async function refreshRss() {
    await loadRssSummary();
    await loadRssEntries();
}

function init() {
    initModal();
    initKeyboardShortcuts();

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

/**
 * Initialize keyboard shortcuts
 */
function initKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ignore if typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        
        // R - Refresh
        if (e.key === 'r' || e.key === 'R') {
            e.preventDefault();
            refreshAll();
            return;
        }
        
        // 1-4 - Switch tabs
        if (e.key === '1') {
            e.preventDefault();
            switchTab('command-center');
        } else if (e.key === '2') {
            e.preventDefault();
            switchTab('life');
        } else if (e.key === '3') {
            e.preventDefault();
            switchTab('plan');
        } else if (e.key === '4') {
            e.preventDefault();
            switchTab('analytics');
        } else if (e.key === '5') {
            e.preventDefault();
            switchTab('school');
        } else if (e.key === '6') {
            e.preventDefault();
            switchTab('financial');
        } else if (e.key === '7') {
            e.preventDefault();
            switchTab('rss');
        }

        // ? - Show help
        if (e.key === '?') {
            e.preventDefault();
            showKeyboardHelp();
        }
    });
}

/**
 * Show keyboard shortcuts help
 */
function showKeyboardHelp() {
    var content = '<div class="keyboard-help">';
    content += '<div class="shortcut-row"><kbd>R</kbd> Refresh dashboard</div>';
    content += '<div class="shortcut-row"><kbd>1</kbd> Command tab</div>';
    content += '<div class="shortcut-row"><kbd>2</kbd> Life tab</div>';
    content += '<div class="shortcut-row"><kbd>3</kbd> Plan tab</div>';
    content += '<div class="shortcut-row"><kbd>4</kbd> Analytics tab</div>';
    content += '<div class="shortcut-row"><kbd>5</kbd> School tab</div>';
    content += '<div class="shortcut-row"><kbd>6</kbd> Financial tab</div>';
    content += '<div class="shortcut-row"><kbd>?</kbd> Show this help</div>';
    content += '<div class="shortcut-row"><kbd>Esc</kbd> Close modal</div>';
    content += '</div>';
    
    openModal('Keyboard Shortcuts', content, 'keyboard');
}

document.addEventListener('DOMContentLoaded', init);

/* =============================================================================
   MOBILE RESPONSIVE FUNCTIONALITY
   Added: 2026-02-03 Overnight Sprint
   ============================================================================= */

/**
 * Check if device is mobile (touch device or small screen)
 */
function isMobileDevice() {
    return window.innerWidth <= 768 || 'ontouchstart' in window;
}

/**
 * Initialize mobile-specific features
 */
function initMobileFeatures() {
    if (!isMobileDevice()) return;
    
    // Add collapse icons to cards that don't have them
    var cards = document.querySelectorAll('.card');
    cards.forEach(function(card) {
        var header = card.querySelector('.card-header');
        if (!header) return;
        
        // Skip if already has collapse icon
        if (header.querySelector('.collapse-icon')) return;
        
        // Skip certain cards that shouldn't collapse
        var cardId = card.id || '';
        if (cardId.includes('modal') || cardId.includes('attention')) return;
        
        // Add chevron icon for collapse indicator
        var chevron = document.createElement('i');
        chevron.setAttribute('data-lucide', 'chevron-down');
        chevron.className = 'icon collapse-icon';
        header.appendChild(chevron);
        
        // Make header clickable for toggle
        header.addEventListener('click', function(e) {
            // Don't toggle if clicking a button or link inside header
            if (e.target.closest('button') || e.target.closest('a')) return;
            
            toggleCardCollapse(card);
        });
    });
    
    // Re-initialize Lucide icons for new chevrons
    if (window.lucide) {
        lucide.createIcons();
    }
}

/**
 * Toggle card collapse state
 */
function toggleCardCollapse(card) {
    if (!card) return;
    
    var isCollapsed = card.classList.contains('collapsed');
    
    if (isCollapsed) {
        card.classList.remove('collapsed');
        // Store state
        if (card.id) {
            localStorage.setItem('card-' + card.id + '-collapsed', 'false');
        }
    } else {
        card.classList.add('collapsed');
        // Store state
        if (card.id) {
            localStorage.setItem('card-' + card.id + '-collapsed', 'true');
        }
    }
}

/**
 * Restore collapsed states from localStorage
 */
function restoreCardStates() {
    if (!isMobileDevice()) return;
    
    var cards = document.querySelectorAll('.card[id]');
    cards.forEach(function(card) {
        var state = localStorage.getItem('card-' + card.id + '-collapsed');
        if (state === 'true') {
            card.classList.add('collapsed');
        }
    });
}

/**
 * Handle orientation change
 */
function handleOrientationChange() {
    // Recalculate layouts after orientation change
    setTimeout(function() {
        if (window.lucide) {
            lucide.createIcons();
        }
    }, 100);
}

/**
 * Initialize touch-specific behaviors
 */
function initTouchBehaviors() {
    if (!('ontouchstart' in window)) return;
    
    // Add touch feedback class on touch
    document.addEventListener('touchstart', function(e) {
        var target = e.target.closest('.card-header, .tab, .btn-primary, .btn-secondary, .task-item');
        if (target) {
            target.classList.add('touch-active');
        }
    }, { passive: true });
    
    document.addEventListener('touchend', function(e) {
        var active = document.querySelectorAll('.touch-active');
        active.forEach(function(el) {
            el.classList.remove('touch-active');
        });
    }, { passive: true });
}

/**
 * Handle window resize - adjust for mobile/desktop transitions
 */
var resizeTimeout;
function handleResize() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(function() {
        if (isMobileDevice()) {
            initMobileFeatures();
        } else {
            // Remove collapsed states on desktop
            document.querySelectorAll('.card.collapsed').forEach(function(card) {
                card.classList.remove('collapsed');
            });
        }
    }, 250);
}

// Add to existing init or DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    initMobileFeatures();
    restoreCardStates();
    initTouchBehaviors();
    
    // Listen for resize and orientation changes
    window.addEventListener('resize', handleResize);
    window.addEventListener('orientationchange', handleOrientationChange);
});

/* =============================================================================
   Enhanced XP Gamification
   Added: 2026-02-03 Overnight Sprint
   ============================================================================= */

/**
 * Sync XP from all automatic sources on dashboard load
 */
async function syncAutoXp() {
    try {
        const resp = await fetch('/api/life/xp/sync', { method: 'POST' });
        const data = await resp.json();
        
        if (data.status === 'ok' && data.xp_awarded && data.xp_awarded.total > 0) {
            console.log('XP synced:', data.xp_awarded);
            
            // Show notifications for new XP
            if (data.details && data.details.length > 0) {
                data.details.forEach(function(detail) {
                    showXpNotification(0, detail);
                });
            }
            
            // Show achievement notifications
            if (data.new_achievements && data.new_achievements.length > 0) {
                data.new_achievements.forEach(function(achievement) {
                    showAchievementUnlock(achievement);
                });
            }
            
            // Update Life Pulse widget
            updateLifePulseFromSync(data);
        }
    } catch (e) {
        console.error('Auto XP sync error:', e);
    }
}

/**
 * Update Life Pulse widget with today's XP
 */
async function refreshLifePulse() {
    try {
        const resp = await fetch('/api/life/stats/today');
        const data = await resp.json();
        
        var lifePulseXp = document.getElementById('life-pulse-xp');
        if (lifePulseXp) {
            lifePulseXp.textContent = '+' + (data.today_xp || 0);
            
            // Add animation class if XP > 0
            if (data.today_xp > 0) {
                lifePulseXp.classList.add('has-xp');
            }
        }
    } catch (e) {
        console.error('Life pulse refresh error:', e);
    }
}

/**
 * Update Life Pulse from XP sync response
 */
function updateLifePulseFromSync(data) {
    var lifePulseXp = document.getElementById('life-pulse-xp');
    if (lifePulseXp && data.xp_awarded) {
        // Trigger a refresh to get accurate total
        refreshLifePulse();
    }
}

/**
 * Show achievement unlock notification
 */
function showAchievementUnlock(achievement) {
    var notification = document.createElement('div');
    notification.className = 'achievement-notification';
    notification.innerHTML = '<div class="achievement-icon">🏆</div>' +
        '<div class="achievement-text">' +
        '<div class="achievement-title">Achievement Unlocked!</div>' +
        '<div class="achievement-name">' + escapeHtml(achievement.name) + '</div>' +
        '</div>';
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(function() {
        notification.classList.add('show');
    }, 10);
    
    // Remove after delay
    setTimeout(function() {
        notification.classList.remove('show');
        setTimeout(function() {
            notification.remove();
        }, 300);
    }, 4000);
}

// Call auto XP sync on page load (after main init)
document.addEventListener('DOMContentLoaded', function() {
    // Delay XP sync to not block initial load
    setTimeout(function() {
        syncAutoXp();
        refreshLifePulse();
    }, 2000);
});
