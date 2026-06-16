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

        var codeReuseOptions = document.getElementById('code-reuse-options');
        var dangerousFunctionsOptions = document.getElementById('dangerous-functions-options');
        var mlTrainingOptions = document.getElementById('ml-training-options');
        var mlPredictionOptions = document.getElementById('ml-prediction-options');

        // Hide all
        if (codeReuseOptions) codeReuseOptions.style.display = 'none';
        if (dangerousFunctionsOptions) dangerousFunctionsOptions.style.display = 'none';
        if (mlTrainingOptions) mlTrainingOptions.style.display = 'none';
        if (mlPredictionOptions) mlPredictionOptions.style.display = 'none';

        // Show selected
        if (taskType === 'code_reuse' && codeReuseOptions) {
            codeReuseOptions.style.display = 'block';
        } else if (taskType === 'dangerous_functions' && dangerousFunctionsOptions) {
            dangerousFunctionsOptions.style.display = 'block';
        } else if (taskType === 'ml_training' && mlTrainingOptions) {
            mlTrainingOptions.style.display = 'block';
        } else if (taskType === 'ml_prediction' && mlPredictionOptions) {
            mlPredictionOptions.style.display = 'block';
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
            modelName = document.getElementById('prediction-model').value;
            mlClassType = document.getElementById('ml-class-type-pred').value;
            if (!modelName) {
                showTaskError('Please select a model for prediction');
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

            // Show status
            var configEl = document.getElementById('task-config');
            var statusEl = document.getElementById('task-status');
            if (configEl) configEl.style.display = 'none';
            if (statusEl) statusEl.style.display = 'block';

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
            var response = await authenticatedFetch('/api/v1/tasks/tasks/' + taskUuid + '/status', {
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
                // Fetch and redirect to results
                window.location.href = '/task-results?task_uuid=' + taskUuid;
            } else if (status === 'error') {
                stopPolling();
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
            el.style.display = 'block';
        }
    }

    /**
     * Hide task error
     */
    function hideTaskError() {
        var el = document.getElementById('task-error');
        if (el) {
            el.textContent = '';
            el.style.display = 'none';
        }
    }

})();
