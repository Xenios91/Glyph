/**
 * Glyph - Run Task JavaScript
 * Handles task execution and polling for results
 */
'use strict';

(function () {
    'use strict';

    // ============================================================
    // State
    // ============================================================

    /** @type {string|null} */
    var currentTaskUuid = null;

    /** @type {number|undefined} */
    var pollingInterval = undefined;

    /** @type {number|undefined} */
    var elapsedTimerId = undefined;

    /** @type {number} */
    var taskStartedAt = 0;

    /** @type {string} */
    var currentTaskName = '';

    /** @type {number} */
    var binaryId = parseInt(window.location.search.match(/binary_id=(\d+)/)?.[1] || '0', 10);

    /** @type {string|null} */
    var urlTaskType = new URLSearchParams(window.location.search).get('task_type');

    // ============================================================
    // DOM Ready
    // ============================================================

    document.addEventListener('DOMContentLoaded', function () {
        loadFunctionCount();
        autoFillTaskName();
        preSelectTaskType();

        // Wire the execute button and task-type select via addEventListener
        // (inline onclick/onchange handlers are blocked by the strict CSP
        // script-src 'self' policy).
        var executeBtn = document.getElementById('execute-btn');
        if (executeBtn) {
            executeBtn.addEventListener('click', function () {
                window.executeTask();
            });
        }

        var taskTypeSelect = document.getElementById('task-type');
        if (taskTypeSelect) {
            taskTypeSelect.addEventListener('change', function () {
                window.handleTaskTypeChange();
            });
        }

        var bgBtn = document.getElementById('run-task-background-btn');
        if (bgBtn) {
            bgBtn.addEventListener('click', runInBackground);
        }

        var cancelBtn = document.getElementById('run-task-cancel-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', cancelTask);
        }
    });

    // ============================================================
    // Initialization
    // ============================================================

    /**
     * Load function count for the binary
     */
    async function loadFunctionCount() {
        if (!binaryId) return;

        try {
            var response = await authenticatedFetch('/api/v1/binaries/binaries/' + binaryId, {
                headers: { 'Accept': 'application/json' }
            });

            var data = await response.json();
            if (response.ok && data.data) {
                var countEl = document.getElementById('function-count');
                if (countEl) {
                    countEl.textContent = data.data.function_count || 0;
                }
            }
        } catch (error) {
            console.error('Failed to load function count:', error);
        }
    }

    /**
     * Auto-fill task name with timestamp
     */
    function autoFillTaskName() {
        var nameInput = document.getElementById('task-name');
        if (nameInput) {
            var timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
            nameInput.value = 'task_' + timestamp;
        }
    }

    /**
     * Pre-select task type from URL parameter
     */
    function preSelectTaskType() {
        if (!urlTaskType) return;

        var taskTypeSelect = document.getElementById('task-type');
        if (taskTypeSelect && taskTypeSelect.querySelector('option[value="' + urlTaskType + '"]')) {
            taskTypeSelect.value = urlTaskType;
            handleTaskTypeChange();
        }
    }

    // ============================================================
    // Task Type Switching
    // ============================================================

    /**
     * Handle task type change
     */
    window.handleTaskTypeChange = function () {
        var taskType = document.getElementById('task-type').value;

        var dangerousFunctionsOptions = document.getElementById('dangerous-functions-options');
        var mlTrainingOptions = document.getElementById('ml-training-options');
        var mlPredictionOptions = document.getElementById('ml-prediction-options');

        // Hide all
        if (dangerousFunctionsOptions) dangerousFunctionsOptions.classList.add('is-hidden');
        if (mlTrainingOptions) mlTrainingOptions.classList.add('is-hidden');
        if (mlPredictionOptions) mlPredictionOptions.classList.add('is-hidden');

        // Show selected
        if (taskType === 'dangerous_functions' && dangerousFunctionsOptions) {
            dangerousFunctionsOptions.classList.remove('is-hidden');
        } else if (taskType === 'ml_training' && mlTrainingOptions) {
            mlTrainingOptions.classList.remove('is-hidden');
        } else if (taskType === 'ml_prediction' && mlPredictionOptions) {
            mlPredictionOptions.classList.remove('is-hidden');
        }
    };

    // ============================================================
    // Task Execution
    // ============================================================

    /**
     * Execute the selected task
     */
    window.executeTask = async function () {
        var taskName = document.getElementById('task-name').value.trim();
        var taskType = document.getElementById('task-type').value;

        // Validation
        hideTaskError();

        if (!taskName) {
            showTaskError('Task name is required');
            return;
        }

        var modelName = '';
        var mlClassType = null;

        if (taskType === 'ml_training') {
            modelName = document.getElementById('model-name').value.trim();
            mlClassType = document.getElementById('ml-class-type').value;
            if (!modelName) {
                showTaskError('Model name is required for ML training');
                return;
            }
        } else if (taskType === 'ml_prediction') {
            // ML prediction requires an existing model name (no class type).
            modelName = document.getElementById('prediction-model-name').value.trim();
            if (!modelName) {
                showTaskError('Model name is required for ML prediction');
                return;
            }
        }
        // dangerous_functions task type requires no additional parameters

        // Disable button
        var btn = document.getElementById('execute-btn');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'EXECUTING...';
        }

        var payload = {
            binary_id: binaryId,
            task_type: taskType,
            task_name: taskName
        };

        if (modelName) payload.model_name = modelName;
        if (mlClassType) payload.ml_class_type = mlClassType;

        try {
            var response = await authenticatedFetch('/api/v1/tasks/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            var data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Task execution failed');
            }

            currentTaskUuid = data.data.task_uuid;
            currentTaskName = taskName;

            // Register with the global StatusBar so the task is tracked even
            // if the user navigates away (run in background).
            if (typeof StatusBar !== 'undefined') {
                StatusBar.registerTask(currentTaskUuid, taskName, {
                    resultLink: '/task-results?task_uuid=' + encodeURIComponent(currentTaskUuid),
                    resultLabel: 'View results'
                });
            }

            // Show status (with task name + ticking elapsed time)
            var configEl = document.getElementById('task-config');
            var statusEl = document.getElementById('task-status');
            if (configEl) configEl.style.display = 'none';
            if (statusEl) statusEl.classList.remove('is-hidden');

            var taskNameEl = document.getElementById('run-task-task-name');
            if (taskNameEl) {
                taskNameEl.textContent = taskName;
            }
            var metaEl = document.getElementById('run-task-task-meta');
            if (metaEl) {
                metaEl.classList.remove('is-hidden');
            }
            startElapsedTimer();

            // Start polling
            startPolling(currentTaskUuid);

        } catch (error) {
            console.error('Task execution error:', error);
            showTaskError(error.message || 'Failed to execute task');
            if (btn) {
                btn.disabled = false;
                btn.textContent = 'EXECUTE TASK';
            }
        }
    };

    // ============================================================
    // Polling
    // ============================================================

    /**
     * Start polling for task status
     * @param {string} taskUuid
     */
    function startPolling(taskUuid) {
        pollTaskStatus(taskUuid);

        pollingInterval = setInterval(function () {
            pollTaskStatus(taskUuid);
        }, 3000);
    }

    /**
     * Poll task status
     * @param {string} taskUuid
     */
    async function pollTaskStatus(taskUuid) {
        try {
            var response = await authenticatedFetch('/api/v1/tasks/' + taskUuid + '/status', {
                headers: { 'Accept': 'application/json' }
            });

            var data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to get task status');
            }

            var status = data.data.status;
            var statusText = document.getElementById('status-text');

            if (statusText) {
                statusText.textContent = 'Status: ' + status.toUpperCase();
            }

            if (status === 'completed') {
                stopPolling();
                stopElapsedTimer();
                // Fetch and redirect to results
                window.location.href = '/task-results?task_uuid=' + taskUuid;
            } else if (status === 'error') {
                stopPolling();
                stopElapsedTimer();
                var statusSubtext = document.getElementById('status-subtext');
                if (statusSubtext) {
                    statusSubtext.textContent = 'Task failed. Check server logs for details.';
                    statusSubtext.style.color = 'var(--red)';
                }
                // Show back button
                showBackButton();
            }

        } catch (error) {
            console.error('Poll error:', error);
        }
    }

    /**
     * Stop polling
     */
    function stopPolling() {
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = undefined;
        }
    }

    /**
     * Start the ticking "Xs elapsed" counter.
     */
    function startElapsedTimer() {
        taskStartedAt = Date.now();
        var elapsedEl = document.getElementById('run-task-elapsed');
        var tick = function () {
            if (elapsedEl) {
                var seconds = Math.floor((Date.now() - taskStartedAt) / 1000);
                elapsedEl.textContent = seconds + 's elapsed';
            }
        };
        tick();
        elapsedTimerId = setInterval(tick, 1000);
    }

    /**
     * Stop the elapsed counter and hide the task meta row.
     */
    function stopElapsedTimer() {
        if (elapsedTimerId) {
            clearInterval(elapsedTimerId);
            elapsedTimerId = undefined;
        }
        var metaEl = document.getElementById('run-task-task-meta');
        if (metaEl) {
            metaEl.classList.add('is-hidden');
        }
    }

    /**
     * Dismiss the blocking status panel and let the StatusBar track the task.
     * The task keeps running on the server; the completion toast (with a link
     * to the results page) is surfaced by the StatusBar.
     */
    window.runInBackground = function () {
        stopPolling();
        stopElapsedTimer();
        var statusEl = document.getElementById('task-status');
        if (statusEl) {
            statusEl.classList.add('is-hidden');
        }
        if (typeof Toast !== 'undefined') {
            Toast.info('Task is now running in the background. Track it in the status panel.', 4000);
        }
    };

    /**
     * Cancel the task (client-side only: no server cancel endpoint exists).
     * Stops local polling and removes the StatusBar entry.
     */
    window.cancelTask = function () {
        stopPolling();
        stopElapsedTimer();
        if (currentTaskUuid && typeof StatusBar !== 'undefined') {
            StatusBar.removeEntry(currentTaskUuid);
        }
        currentTaskUuid = null;
        var statusEl = document.getElementById('task-status');
        if (statusEl) {
            statusEl.classList.add('is-hidden');
        }
        if (typeof Toast !== 'undefined') {
            Toast.warning('Task tracking cancelled. The server may still finish the job.', 4000);
        }
    };

    /**
     * Show back button after task completes or fails
     */
    function showBackButton() {
        var statusEl = document.getElementById('task-status');
        if (!statusEl) return;

        var existingBtn = statusEl.querySelector('.back-button');
        if (existingBtn) return;

        var btnDiv = document.createElement('div');
        btnDiv.className = 'execute-section back-button';
        btnDiv.innerHTML =
            '<a href="/binary-library" class="cyber-btn is-primary">BACK TO LIBRARY</a>';
        statusEl.appendChild(btnDiv);
    }

    // ============================================================
    // UI Helpers
    // ============================================================

    /**
     * Show task error
     * @param {string} message
     */
    function showTaskError(message) {
        var el = document.getElementById('task-error');
        if (el) {
            el.textContent = message;
            el.classList.remove('is-hidden');
        }
    }

    /**
     * Hide task error
     */
    function hideTaskError() {
        var el = document.getElementById('task-error');
        if (el) {
            el.textContent = '';
            el.classList.add('is-hidden');
        }
    }

})();
