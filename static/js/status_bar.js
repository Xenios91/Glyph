/**
 * Glyph - Status Bar Module
 * Bottom-right floating panel showing upload and processing status
 * for tasks submitted by the current user.
 */

/**
 * Status bar manager
 */
const StatusBar = {
    // Storage key for localStorage
    STORAGE_KEY: 'glyph_active_tasks',

    // Polling interval in milliseconds
    POLL_INTERVAL: 2000,

    // Max consecutive "not found" responses before auto-cleanup
    MAX_NOT_FOUND: 3,

    // Internal state
    _tasks: new Map(),
    _pollTimer: null,
    _panel: null,
    _entriesContainer: null,
    _toggleBtn: null,
    _isPanelVisible: false,

    /**
     * Initialize the status bar on page load.
     * Restores active tasks from localStorage and starts polling.
     */
    init() {
        this._buildPanel();
        this._restoreTasks();
        this._updateBadge();
    },

    /**
     * Build the status bar panel DOM elements.
     */
    _buildPanel() {
        // Create panel container
        this._panel = document.createElement('div');
        this._panel.className = 'status-bar-panel';
        this._panel.id = 'status-bar-panel';
        this._panel.setAttribute('role', 'region');
        this._panel.setAttribute('aria-label', 'Upload and processing status');

        // Header
        const header = document.createElement('div');
        header.className = 'status-bar-header';
        header.innerHTML = `
            <h3>// STATUS</h3>
            <button class="status-bar-close" aria-label="Close status panel">&times;</button>
        `;

        // Entries container
        this._entriesContainer = document.createElement('div');
        this._entriesContainer.className = 'status-bar-entries';

        this._panel.appendChild(header);
        this._panel.appendChild(this._entriesContainer);

        // Close button handler
        header.querySelector('.status-bar-close').addEventListener('click', () => {
            this._hidePanel();
        });

        // Create toggle button
        this._toggleBtn = document.createElement('button');
        this._toggleBtn.className = 'status-bar-toggle';
        this._toggleBtn.id = 'status-bar-toggle';
        this._toggleBtn.setAttribute('aria-label', 'Toggle status panel');
        this._toggleBtn.setAttribute('aria-expanded', 'false');
        this._toggleBtn.innerHTML = `
            <span class="icon">&#9680;</span>
            <span class="badge" style="display: none;">0</span>
        `;
        this._toggleBtn.addEventListener('click', () => {
            this._togglePanel();
        });

        document.body.appendChild(this._panel);
        document.body.appendChild(this._toggleBtn);
    },

    /**
     * Toggle panel visibility.
     */
    _togglePanel() {
        if (this._isPanelVisible) {
            this._hidePanel();
        } else {
            this._showPanel();
        }
    },

    /**
     * Show the status bar panel.
     */
    _showPanel() {
        this._panel.classList.remove('is-closing');
        this._panel.classList.add('is-visible');
        this._isPanelVisible = true;
        this._toggleBtn.setAttribute('aria-expanded', 'true');
    },

    /**
     * Hide the status bar panel.
     */
    _hidePanel() {
        this._panel.classList.add('is-closing');
        this._toggleBtn.setAttribute('aria-expanded', 'false');
        setTimeout(() => {
            this._panel.classList.remove('is-visible', 'is-closing');
            this._isPanelVisible = false;
        }, 200);
    },

    /**
     * Update the badge count on the toggle button.
     */
    _updateBadge() {
        const badge = this._toggleBtn.querySelector('.badge');
        const count = this._tasks.size;
        if (count > 0) {
            badge.textContent = count > 9 ? '9+' : count;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    },

    /**
     * Restore active tasks from localStorage.
     */
    _restoreTasks() {
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            if (!stored) return;

            const tasks = JSON.parse(stored);
            const validTasks = [];

            for (const task of tasks) {
                // Skip client-side IDs (e.g. "upload_...") because the server
                // only knows about real UUIDs.  If uploadComplete() was never
                // called (user navigated away before the server responded),
                // we have no way to look up the task on the server.
                if (typeof task.uuid === 'string' && task.uuid.startsWith('upload_')) {
                    console.debug('[STATUS-BAR] Skipping stale client-side ID on restore:', task.uuid);
                    continue;
                }
                validTasks.push(task);

                this._tasks.set(task.uuid, {
                    uuid: task.uuid,
                    fileName: task.fileName,
                    state: 'processing',
                    notFoundCount: 0
                });
                this._createEntry(task.uuid, task.fileName, 'processing');
            }

            // Persist only the valid (server-side) tasks back to localStorage
            if (validTasks.length !== tasks.length) {
                this._persistTasks();
            }

            if (this._tasks.size > 0) {
                this._startPolling();
            }
        } catch (e) {
            console.warn('[STATUS-BAR] Failed to restore tasks from localStorage:', e);
            localStorage.removeItem(this.STORAGE_KEY);
        }
    },

    /**
     * Persist current tasks to localStorage.
     */
    _persistTasks() {
        const tasks = Array.from(this._tasks.values()).map(t => ({
            uuid: t.uuid,
            fileName: t.fileName,
            state: t.state
        }));

        if (tasks.length === 0) {
            localStorage.removeItem(this.STORAGE_KEY);
        } else {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(tasks));
        }
    },

    /**
     * Register a new upload entry.
     * @param {string} fileName - Name of the file being uploaded.
     */
    registerUpload(fileName) {
        const clientId = `upload_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
        this._tasks.set(clientId, {
            uuid: clientId,
            fileName: fileName,
            state: 'uploading',
            percent: 0,
            notFoundCount: 0
        });
        this._createEntry(clientId, fileName, 'uploading');
        this._updateBadge();
        this._showPanel();
        return clientId;
    },

    /**
     * Update upload progress percentage.
     * @param {string} clientId - Client-side ID returned by registerUpload.
     * @param {number} percent - Progress percentage (0-100).
     */
    updateUploadProgress(clientId, percent) {
        const task = this._tasks.get(clientId);
        if (!task) return;

        const rounded = Math.round(percent);
        task.percent = rounded;

        // When upload reaches 100%, immediately transition the UI to "processing" state
        // so the user sees progress rather than a stuck 100% bar
        if (rounded >= 100 && task.state === 'uploading') {
            task.state = 'uploading_complete';
            this._transitionToProcessingUI(clientId, task.fileName);
            return;
        }

        const fillEl = document.getElementById(`progress-fill-${clientId}`);
        if (fillEl) {
            fillEl.style.width = `${task.percent}%`;
        }
        const percentEl = document.getElementById(`percent-${clientId}`);
        if (percentEl) {
            percentEl.textContent = `${task.percent}%`;
        }
    },

    /**
     * Transition an entry's DOM from upload progress view to processing view.
     * Replaces the progress bar with pulsing dots animation.
     * @param {string} clientId - Client-side ID from registerUpload.
     * @param {string} fileName - File name for the processing label.
     */
    _transitionToProcessingUI(clientId, fileName) {
        const entry = document.getElementById(`entry-${clientId}`);
        if (!entry) return;

        // Remove the upload progress section
        const progressDiv = entry.querySelector('.status-entry-progress');
        if (progressDiv) {
            progressDiv.remove();
        }

        // Add processing section with pulsing dots
        const processingDiv = document.createElement('div');
        processingDiv.className = 'status-entry-processing';

        const labelSpan = document.createElement('span');
        labelSpan.className = 'label';
        labelSpan.textContent = 'Processing...';

        const dotsSpan = document.createElement('span');
        dotsSpan.className = 'pulsing-dots';
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('span');
            dot.className = 'dot';
            dotsSpan.appendChild(dot);
        }

        processingDiv.appendChild(labelSpan);
        processingDiv.appendChild(dotsSpan);
        entry.appendChild(processingDiv);
    },

    /**
     * Mark upload as complete and transition to processing state.
     * @param {string} clientId - Client-side ID from registerUpload.
     * @param {string} taskUuid - Server-side task UUID.
     */
    uploadComplete(clientId, taskUuid) {
        const task = this._tasks.get(clientId);
        if (!task) return;

        // Remove old client-keyed task tracking
        this._tasks.delete(clientId);

        // Register under server UUID
        this._tasks.set(taskUuid, {
            uuid: taskUuid,
            fileName: task.fileName,
            state: 'processing',
            notFoundCount: 0
        });

        this._persistTasks();
        this._updateBadge();
        this._ensurePolling();

        // If the UI already transitioned to processing (upload hit 100%),
        // just update the existing entry's ID instead of creating a duplicate
        const oldEntry = document.getElementById(`entry-${clientId}`);
        if (oldEntry) {
            // Check if this entry already has a processing div (UI transitioned)
            const hasProcessingDiv = oldEntry.querySelector('.status-entry-processing');
            if (hasProcessingDiv) {
                // Simply rename the entry ID to use the server UUID
                oldEntry.id = `entry-${taskUuid}`;
                // Update the dismiss button handler to use the new UUID
                const dismissBtn = oldEntry.querySelector('.status-entry-dismiss');
                if (dismissBtn) {
                    // Remove old listener and add new one by replacing the button
                    const newBtn = dismissBtn.cloneNode(true);
                    newBtn.addEventListener('click', () => {
                        this.removeEntry(taskUuid);
                    });
                    dismissBtn.replaceWith(newBtn);
                }
                return;
            }

            // Entry still shows upload progress - animate it out and create new processing entry
            oldEntry.classList.add('is-removing');
            setTimeout(() => {
                oldEntry.remove();
                this._checkEmpty();
            }, 250);
            this._createEntry(taskUuid, task.fileName, 'processing');
        } else {
            this._createEntry(taskUuid, task.fileName, 'processing');
        }
    },

    /**
     * Update a task's status from polling.
     * @param {string} uuid - Task UUID.
     * @param {string} status - Status string from backend.
     */
    updateStatus(uuid, status) {
        const task = this._tasks.get(uuid);
        if (!task) return;

        const entry = document.getElementById(`entry-${uuid}`);
        if (!entry) return;

        // Check for terminal states
        if (status === 'completed' || status === 'error') {
            this._handleTerminalState(uuid, status);
            return;
        }

        // Reset not-found counter on successful status response
        task.notFoundCount = 0;

        // Update status label with current step
        const labelEl = entry.querySelector('.status-entry-label .label');
        if (labelEl) {
            const displayStatus = status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            labelEl.textContent = `Processing... ${displayStatus}`;
        }
    },

    /**
     * Handle terminal task states (completed or error).
     * @param {string} uuid - Task UUID.
     * @param {string} status - 'completed' or 'error'.
     */
    _handleTerminalState(uuid, status) {
        const task = this._tasks.get(uuid);
        if (!task) return;

        const entry = document.getElementById(`entry-${uuid}`);
        if (entry) {
            entry.classList.add(status);

            // Update label
            const labelEl = entry.querySelector('.status-entry-label');
            if (labelEl) {
                const dotsContainer = entry.querySelector('.pulsing-dots');
                if (dotsContainer) dotsContainer.remove();

                const label = entry.querySelector('.status-entry-processing .label');
                if (label) {
                    label.textContent = status === 'completed'
                        ? 'Completed successfully'
                        : 'Processing failed';
                    label.style.color = status === 'completed' ? 'var(--green)' : 'var(--red)';
                }
            }
        }

        // Show toast notification
        if (typeof Toast !== 'undefined') {
            if (status === 'completed') {
                Toast.success(`${task.fileName} processed successfully`, 4000);
            } else {
                Toast.error(`${task.fileName} processing failed`, 5000);
            }
        }

        // Remove from tracking
        this._tasks.delete(uuid);
        this._persistTasks();
        this._updateBadge();

        // Auto-remove entry after delay
        setTimeout(() => {
            if (entry) {
                entry.classList.add('is-removing');
                setTimeout(() => {
                    entry.remove();
                    this._checkEmpty();
                }, 250);
            }
        }, 3000);

        // Stop polling if no tasks remain
        if (this._tasks.size === 0) {
            this._stopPolling();
        }
    },

    /**
     * Handle a task that returns "UUID Not Found" from the backend.
     * @param {string} uuid - Task UUID.
     */
    handleNotFound(uuid) {
        const task = this._tasks.get(uuid);
        if (!task) return;

        task.notFoundCount = (task.notFoundCount || 0) + 1;

        if (task.notFoundCount >= this.MAX_NOT_FOUND) {
            // Auto-cleanup stale task
            const entry = document.getElementById(`entry-${uuid}`);
            if (entry) {
                entry.classList.add('error');
                const label = entry.querySelector('.status-entry-processing .label');
                if (label) {
                    label.textContent = 'Task not found on server';
                    label.style.color = 'var(--red)';
                }
            }

            this._tasks.delete(uuid);
            this._persistTasks();
            this._updateBadge();

            setTimeout(() => {
                if (entry) {
                    entry.classList.add('is-removing');
                    setTimeout(() => {
                        entry.remove();
                        this._checkEmpty();
                    }, 250);
                }
            }, 2000);

            if (this._tasks.size === 0) {
                this._stopPolling();
            }
        }
    },

    /**
     * Create a DOM entry for a task.
     * @param {string} uuid - Task identifier.
     * @param {string} fileName - File name.
     * @param {string} state - 'uploading' or 'processing'.
     */
    _createEntry(uuid, fileName, state) {
        // Remove existing entry if any
        const existing = document.getElementById(`entry-${uuid}`);
        if (existing) existing.remove();

        const entry = document.createElement('div');
        entry.className = 'status-entry';
        entry.id = `entry-${uuid}`;

        // Build header with safe text node for file name (avoids XSS)
        const header = document.createElement('div');
        header.className = 'status-entry-header';

        const fileSpan = document.createElement('span');
        fileSpan.className = 'status-entry-file';

        const iconSpan = document.createElement('span');
        iconSpan.className = 'icon';
        iconSpan.textContent = '\u{1F4C4}';

        const nameSpan = document.createElement('span');
        nameSpan.appendChild(document.createTextNode(fileName));

        fileSpan.appendChild(iconSpan);
        fileSpan.appendChild(nameSpan);

        const dismissBtn = document.createElement('button');
        dismissBtn.className = 'status-entry-dismiss';
        dismissBtn.setAttribute('aria-label', 'Dismiss');
        dismissBtn.textContent = '\u00D7';

        header.appendChild(fileSpan);
        header.appendChild(dismissBtn);
        entry.appendChild(header);

        if (state === 'uploading') {
            const progressDiv = document.createElement('div');
            progressDiv.className = 'status-entry-progress';

            const track = document.createElement('div');
            track.className = 'progress-track';

            const fill = document.createElement('div');
            fill.className = 'progress-fill';
            fill.id = `progress-fill-${uuid}`;
            fill.style.width = '0%';
            track.appendChild(fill);

            const labelDiv = document.createElement('div');
            labelDiv.className = 'status-entry-label';

            const labelSpan = document.createElement('span');
            labelSpan.className = 'label';
            labelSpan.textContent = 'Uploading...';

            const percentSpan = document.createElement('span');
            percentSpan.className = 'status-entry-percent';
            percentSpan.id = `percent-${uuid}`;
            percentSpan.textContent = '0%';

            labelDiv.appendChild(labelSpan);
            labelDiv.appendChild(percentSpan);
            progressDiv.appendChild(track);
            progressDiv.appendChild(labelDiv);
            entry.appendChild(progressDiv);
        } else {
            const processingDiv = document.createElement('div');
            processingDiv.className = 'status-entry-processing';

            const labelSpan = document.createElement('span');
            labelSpan.className = 'label';
            labelSpan.textContent = 'Processing...';

            const dotsSpan = document.createElement('span');
            dotsSpan.className = 'pulsing-dots';
            for (let i = 0; i < 3; i++) {
                const dot = document.createElement('span');
                dot.className = 'dot';
                dotsSpan.appendChild(dot);
            }

            processingDiv.appendChild(labelSpan);
            processingDiv.appendChild(dotsSpan);
            entry.appendChild(processingDiv);
        }

        // Dismiss handler
        dismissBtn.addEventListener('click', () => {
            this.removeEntry(uuid);
        });

        this._entriesContainer.appendChild(entry);
    },

    /**
     * Remove an entry manually.
     * @param {string} uuid - Task UUID.
     */
    removeEntry(uuid) {
        this._tasks.delete(uuid);
        this._persistTasks();
        this._updateBadge();

        const entry = document.getElementById(`entry-${uuid}`);
        if (entry) {
            entry.classList.add('is-removing');
            setTimeout(() => {
                entry.remove();
                this._checkEmpty();
            }, 250);
        }

        if (this._tasks.size === 0) {
            this._stopPolling();
        }
    },

    /**
     * Check if entries container is empty and show empty state.
     */
    _checkEmpty() {
        const entries = this._entriesContainer.querySelectorAll('.status-entry');
        if (entries.length === 0 && this._tasks.size === 0) {
            const empty = document.createElement('div');
            empty.className = 'status-bar-empty';
            empty.textContent = 'No active tasks';
            this._entriesContainer.appendChild(empty);
        }
    },

    /**
     * Start polling for task statuses.
     */
    _startPolling() {
        if (this._pollTimer) return;
        this._pollStatuses();
        this._pollTimer = setInterval(() => {
            this._pollStatuses();
        }, this.POLL_INTERVAL);
    },

    /**
     * Ensure polling is active if there are tasks.
     */
    _ensurePolling() {
        if (this._tasks.size > 0 && !this._pollTimer) {
            this._startPolling();
        }
    },

    /**
     * Stop polling.
     */
    _stopPolling() {
        if (this._pollTimer) {
            clearInterval(this._pollTimer);
            this._pollTimer = null;
        }
    },

    /**
     * Poll backend for status updates on all tracked tasks.
     */
    async _pollStatuses() {
        const uuids = Array.from(this._tasks.keys());
        // Filter to only processing tasks (uploading tasks don't need polling)
        const processingUuids = uuids.filter(uuid => {
            const task = this._tasks.get(uuid);
            return task && task.state === 'processing';
        });

        for (const uuid of processingUuids) {
            try {
                const token = this._getAccessToken();
                const headers = { 'Accept': 'application/json' };
                if (token) headers['Authorization'] = `Bearer ${token}`;

                const response = await fetch(
                    `/api/v1/status/getStatus?uuid=${encodeURIComponent(uuid)}`,
                    { headers }
                );

                if (response.ok) {
                    const data = await response.json();
                    const status = data.data && data.data.status;
                    if (status) {
                        this.updateStatus(uuid, status);
                    }
                } else if (response.status === 404) {
                    this.handleNotFound(uuid);
                }
            } catch (e) {
                // Silently fail on network errors - retry next poll
                console.debug('[STATUS-BAR] Poll failed for', uuid, e);
            }
        }
    },

    /**
     * Get access token from cookie.
     * @returns {string|null}
     */
    _getAccessToken() {
        const match = document.cookie.match(/access_token_cookie=([^;]+)/);
        return match ? match[1] : null;
    }
};

// Expose globally
window.StatusBar = StatusBar;

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => StatusBar.init());
} else {
    StatusBar.init();
}
