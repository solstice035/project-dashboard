/**
 * Kanban Board Module
 * Integrated into Project Dashboard
 */

const KanbanBoard = {
    tasks: [],
    currentTask: null,
    apiBase: '/api/kanban',
    
    columns: [
        { id: 'backlog', title: 'Backlog', label: 'Ideas & Future Work' },
        { id: 'ready', title: 'Ready', label: 'Queued & Prioritized' },
        { id: 'in-progress', title: 'Active', label: 'Currently Working' },
        { id: 'review', title: 'Review', label: 'Pending Approval' },
        { id: 'done', title: 'Complete', label: 'Finished & Shipped' }
    ],

    init() {
        this.loadTasks();
        this.setupDragAndDrop();
        this.setupModal();
    },

    async loadTasks() {
        try {
            const resp = await fetch(`${this.apiBase}/tasks`);
            if (!resp.ok) throw new Error('Failed to load tasks');
            this.tasks = await resp.json();
            this.render();
            this.updateStatus('ok');
        } catch (err) {
            console.error('Kanban load error:', err);
            this.updateStatus('error');
        }
    },

    render() {
        this.columns.forEach(col => {
            const container = document.querySelector(`[data-kanban-column="${col.id}"] .kanban-cards`);
            const countEl = document.querySelector(`[data-kanban-column="${col.id}"] .kanban-column-count`);
            if (!container) return;

            const columnTasks = this.tasks.filter(t => t.column === col.id);
            countEl.textContent = columnTasks.length;

            if (columnTasks.length === 0) {
                container.innerHTML = '<div class="kanban-empty">No tasks</div>';
                return;
            }

            container.innerHTML = columnTasks.map(task => this.renderCard(task)).join('');
        });

        // Re-setup drag events on cards
        this.setupCardDrag();
    },

    renderCard(task) {
        const tags = (task.tags || []).slice(0, 3).map(t =>
            `<span class="kanban-tag">${this.escapeHtml(t)}</span>`
        ).join('');

        const priorityClass = `p${task.priority || 2}`;
        const priorityValue = task.priority || 2;
        const description = task.description ?
            `<div class="kanban-card-description">${this.escapeHtml(task.description)}</div>` : '';

        return `
            <div class="kanban-card" draggable="true" data-task-id="${task.id}" data-priority="${priorityValue}">
                <div class="kanban-card-actions">
                    <button class="kanban-card-btn edit" onclick="KanbanBoard.editTask(${task.id})" title="Edit">
                        <i data-lucide="edit-2"></i>
                    </button>
                    <button class="kanban-card-btn delete" onclick="KanbanBoard.deleteTask(${task.id})" title="Delete">
                        <i data-lucide="trash-2"></i>
                    </button>
                </div>
                <div class="kanban-card-title">${this.escapeHtml(task.title)}</div>
                ${description}
                <div class="kanban-card-meta">
                    <span class="kanban-priority ${priorityClass}" title="Priority ${priorityValue}"></span>
                    ${tags}
                </div>
            </div>
        `;
    },

    setupCardDrag() {
        document.querySelectorAll('.kanban-card').forEach(card => {
            card.addEventListener('dragstart', (e) => {
                card.classList.add('dragging');
                e.dataTransfer.setData('text/plain', card.dataset.taskId);
            });

            card.addEventListener('dragend', () => {
                card.classList.remove('dragging');
            });
        });

        // Refresh Lucide icons
        if (window.lucide) {
            lucide.createIcons();
        }
    },

    setupDragAndDrop() {
        document.querySelectorAll('.kanban-column').forEach(column => {
            const cardsContainer = column.querySelector('.kanban-cards');
            
            cardsContainer.addEventListener('dragover', (e) => {
                e.preventDefault();
                column.classList.add('drag-over');
            });

            cardsContainer.addEventListener('dragleave', () => {
                column.classList.remove('drag-over');
            });

            cardsContainer.addEventListener('drop', async (e) => {
                e.preventDefault();
                column.classList.remove('drag-over');

                const taskId = e.dataTransfer.getData('text/plain');
                const newColumn = column.dataset.kanbanColumn;

                await this.moveTask(taskId, newColumn);
            });
        });
    },

    async moveTask(taskId, newColumn) {
        try {
            const resp = await fetch(`${this.apiBase}/tasks/${taskId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ column: newColumn })
            });

            if (!resp.ok) throw new Error('Failed to move task');

            // Update local state
            const task = this.tasks.find(t => t.id == taskId);
            if (task) task.column = newColumn;

            this.render();
        } catch (err) {
            console.error('Move task error:', err);
            this.showToast('Failed to move task', 'error');
        }
    },

    setupModal() {
        const modal = document.getElementById('kanban-modal');
        if (!modal) return;

        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) this.closeModal();
        });

        // Close on Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                this.closeModal();
            }
        });
    },

    openModal(column = 'backlog') {
        const modal = document.getElementById('kanban-modal');
        const header = document.getElementById('kanban-modal-header');
        const form = document.getElementById('kanban-task-form');
        const deleteBtn = document.getElementById('kanban-delete-btn');

        this.currentTask = null;
        header.textContent = 'Add New Task';
        deleteBtn.style.display = 'none';
        form.reset();
        document.getElementById('kanban-task-column').value = column;

        modal.classList.add('active');
        document.getElementById('kanban-task-title').focus();
    },

    editTask(taskId) {
        const task = this.tasks.find(t => t.id == taskId);
        if (!task) return;

        const modal = document.getElementById('kanban-modal');
        const header = document.getElementById('kanban-modal-header');
        const deleteBtn = document.getElementById('kanban-delete-btn');

        this.currentTask = task;
        header.textContent = 'Edit Task';
        deleteBtn.style.display = 'inline-block';

        document.getElementById('kanban-task-title').value = task.title || '';
        document.getElementById('kanban-task-description').value = task.description || '';
        document.getElementById('kanban-task-tags').value = (task.tags || []).join(', ');
        document.getElementById('kanban-task-priority').value = task.priority || 2;
        document.getElementById('kanban-task-column').value = task.column || 'backlog';

        modal.classList.add('active');
    },

    closeModal() {
        const modal = document.getElementById('kanban-modal');
        modal.classList.remove('active');
        this.currentTask = null;
    },

    async saveTask() {
        const title = document.getElementById('kanban-task-title').value.trim();
        const description = document.getElementById('kanban-task-description').value.trim();
        const tagsStr = document.getElementById('kanban-task-tags').value.trim();
        const priority = parseInt(document.getElementById('kanban-task-priority').value) || 2;
        const column = document.getElementById('kanban-task-column').value;

        if (!title) {
            this.showToast('Title is required', 'error');
            return;
        }

        const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(t => t) : [];

        const taskData = { title, description, tags, priority, column };

        try {
            let resp;
            if (this.currentTask) {
                // Update existing
                resp = await fetch(`${this.apiBase}/tasks/${this.currentTask.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(taskData)
                });
            } else {
                // Create new
                resp = await fetch(`${this.apiBase}/tasks`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(taskData)
                });
            }

            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.error || 'Failed to save task');
            }

            this.closeModal();
            await this.loadTasks();
            this.showToast(this.currentTask ? 'Task updated' : 'Task created', 'success');
        } catch (err) {
            console.error('Save task error:', err);
            this.showToast(err.message, 'error');
        }
    },

    async deleteTask(taskId) {
        if (!confirm('Delete this task?')) return;

        try {
            const resp = await fetch(`${this.apiBase}/tasks/${taskId}`, {
                method: 'DELETE'
            });

            if (!resp.ok) throw new Error('Failed to delete task');

            this.closeModal();
            await this.loadTasks();
            this.showToast('Task deleted', 'success');
        } catch (err) {
            console.error('Delete task error:', err);
            this.showToast('Failed to delete task', 'error');
        }
    },

    updateStatus(status) {
        const dot = document.getElementById('status-kanban');
        if (dot) {
            dot.classList.remove('loading', 'ok', 'error');
            dot.classList.add(status);
        }
    },

    showToast(message, type = 'info') {
        // Use existing toast system if available, otherwise console
        if (window.showToast) {
            window.showToast(message, type);
        } else {
            console.log(`[${type}] ${message}`);
        }
    },

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
};

// Initialize when DOM ready and tab is shown
document.addEventListener('DOMContentLoaded', () => {
    // Initialize when kanban tab is first shown
    const kanbanTab = document.querySelector('[data-tab="kanban"]');
    if (kanbanTab) {
        kanbanTab.addEventListener('click', () => {
            if (!KanbanBoard.tasks.length) {
                KanbanBoard.init();
            }
        });
    }
});

// Export for global access
window.KanbanBoard = KanbanBoard;
