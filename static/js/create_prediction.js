/**
 * Glyph - Create Prediction Page JavaScript
 * Handles prediction task creation from uploaded binaries using existing ML models
 * Uses native fetch API with authenticatedFetch from common.js
 */
'use strict';

(function () {
    /** @type {string|null} */
    const urlBinaryId = new URLSearchParams(window.location.search).get('binary_id');

    /**
     * Load available binaries into the selection dropdown
     */
    async function loadBinaries() {
        const select = document.getElementById('binary-select');
        if (!select) return;

        try {
            const response = await authenticatedFetch('/api/v1/binaries/list', {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            });

            if (!response.ok) {
                console.error('[CREATE_PREDICTION] Failed to load binaries:', response.status);
                return;
            }

            const data = await response.json();
            const binaries = data.data && data.data.items ? data.data.items : [];

            if (binaries.length === 0) {
                select.innerHTML = '<option value="" disabled selected hidden>NO BINARIES AVAILABLE</option>';
                return;
            }

            select.innerHTML = '<option value="" disabled selected hidden>SELECT BINARY</option>';
            binaries.forEach(function (binary) {
                const option = document.createElement('option');
                option.value = binary.id;
                option.textContent = binary.name + ' (' + binary.function_count + ' functions)';
                select.appendChild(option);
                // Auto-select if this binary matches the URL parameter
                if (urlBinaryId && String(binary.id) === urlBinaryId) {
                    option.selected = true;
                }
            });
        } catch (error) {
            console.error('[CREATE_PREDICTION] Error loading binaries:', error);
        }
    }

    /**
     * Load available ML models into the model selection dropdown
     */
    async function loadModels() {
        const select = document.getElementById('model-select');
        if (!select) return;

        try {
            const response = await authenticatedFetch('/getModels', {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            });

            if (!response.ok) {
                console.error('[CREATE_PREDICTION] Failed to load models:', response.status);
                return;
            }

            const data = await response.json();
            const models = data.models ? data.models : [];

            if (models.length === 0) {
                select.innerHTML = '<option value="" disabled selected hidden>NO MODELS AVAILABLE</option>';
                return;
            }

            select.innerHTML = '<option value="" disabled selected hidden>SELECT MODEL</option>';
            models.forEach(function (model) {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('[CREATE_PREDICTION] Error loading models:', error);
        }
    }

    /**
     * Auto-fill task name with timestamp
     */
    function autoFillTaskName() {
        var nameInput = document.getElementById('task-name');
        if (nameInput) {
            var timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
            nameInput.value = 'prediction_' + timestamp;
        }
    }

    /**
     * Validate the create prediction form
     * @returns {boolean} True if valid, false otherwise
     */
    function validateForm() {
        const binarySelect = document.getElementById('binary-select');
        const modelSelect = document.getElementById('model-select');
        const taskName = document.getElementById('task-name');
        const errorEl = document.getElementById('create-prediction-error');

        if (!binarySelect || !binarySelect.value) {
            if (errorEl) {
                errorEl.textContent = 'Please select a binary.';
                errorEl.style.display = 'block';
            }
            return false;
        }

        if (!modelSelect || !modelSelect.value) {
            if (errorEl) {
                errorEl.textContent = 'Please select a model.';
                errorEl.style.display = 'block';
            }
            return false;
        }

        if (!taskName || !taskName.value.trim()) {
            if (errorEl) {
                errorEl.textContent = 'Please enter a task name.';
                errorEl.style.display = 'block';
            }
            return false;
        }

        if (errorEl) {
            errorEl.style.display = 'none';
        }
        return true;
    }

    /**
     * Show status message
     * @param {string} message - Status message to display
     * @param {boolean} isSuccess - Whether this is a success message
     */
    function showStatus(message, isSuccess) {
        const statusEl = document.getElementById('create-prediction-status');
        const statusText = document.getElementById('create-prediction-status-text');
        const spinner = document.getElementById('status-spinner');

        if (!statusEl || !statusText) return;

        statusEl.style.display = 'block';
        statusEl.classList.remove('is-error', 'is-success');

        if (isSuccess === true) {
            statusEl.classList.add('is-success');
            if (spinner) spinner.style.display = 'none';
        } else if (isSuccess === false) {
            statusEl.classList.add('is-error');
            if (spinner) spinner.style.display = 'none';
        } else {
            if (spinner) spinner.style.display = 'block';
        }

        statusText.textContent = message;
    }

    /**
     * Disable/enable the create prediction button
     * @param {boolean} disabled - Whether to disable the button
     */
    function setButtonState(disabled) {
        const btn = document.getElementById('create-prediction-btn');
        if (btn) {
            btn.disabled = disabled;
        }
    }

    /**
     * Poll task status until completion or failure
     * @param {string} taskUuid - Task UUID to poll
     */
    async function pollTaskStatus(taskUuid) {
        const POLL_INTERVAL = 3000; // 3 seconds

        const checkStatus = async () => {
            try {
                const response = await authenticatedFetch(
                    '/api/v1/tasks/tasks/' + encodeURIComponent(taskUuid) + '/status',
                    { method: 'GET', headers: { 'Accept': 'application/json' } }
                );

                if (!response.ok) {
                    console.error('[CREATE_PREDICTION] Status poll failed:', response.status);
                    return 'unknown';
                }

                const data = await response.json();
                const status = data.data && data.data.status;

                if (status === 'completed') {
                    showStatus('Prediction completed successfully!', true);
                    // Redirect to predictions page after a brief delay
                    setTimeout(function () {
                        window.location.href = '/getPredictions';
                    }, 1500);
                    return 'done';
                } else if (status === 'failed' || status === 'error') {
                    showStatus('Prediction failed.', false);
                    setButtonState(false);
                    return 'done';
                }

                // Still running - update status and continue polling
                showStatus('Prediction in progress... (' + status + ')', null);
                setTimeout(checkStatus, POLL_INTERVAL);
            } catch (error) {
                console.error('[CREATE_PREDICTION] Error polling status:', error);
                setTimeout(checkStatus, POLL_INTERVAL);
            }
        };

        // Start polling
        setTimeout(checkStatus, POLL_INTERVAL);
    }

    /**
     * Handle create prediction button click
     */
    async function handleCreatePrediction() {
        if (!validateForm()) return;

        const binaryId = parseInt(document.getElementById('binary-select').value, 10);
        const modelName = document.getElementById('model-select').value.trim();
        const taskName = document.getElementById('task-name').value.trim();

        setButtonState(true);
        showStatus('Submitting prediction task...', null);

        try {
            const response = await authenticatedFetch('/api/v1/tasks/execute', {
                method: 'POST',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    binary_id: binaryId,
                    task_type: 'ml_prediction',
                    task_name: taskName,
                    model_name: modelName
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(function () { return null; });
                const errorMsg = errorData && errorData.detail
                    ? errorData.detail
                    : 'Failed to create prediction task (HTTP ' + response.status + ')';
                showStatus(errorMsg, false);
                setButtonState(false);
                return;
            }

            const data = await response.json();
            const taskUuid = data.data && data.data.task_uuid;

            if (taskUuid) {
                showStatus('Prediction task submitted. Processing...', null);
                pollTaskStatus(taskUuid);
            } else {
                showStatus('Task submitted but no UUID received.', false);
                setButtonState(false);
            }
        } catch (error) {
            console.error('[CREATE_PREDICTION] Error submitting task:', error);
            showStatus('Network error. Please try again.', false);
            setButtonState(false);
        }
    }

    /**
     * Initialize page when DOM is ready
     */
    function init() {
        loadBinaries();
        loadModels();
        autoFillTaskName();

        const btn = document.getElementById('create-prediction-btn');
        if (btn) {
            btn.addEventListener('click', handleCreatePrediction);
        }
    }

    // Use onDomReady from common.js if available, otherwise fallback
    if (typeof onDomReady === 'function') {
        onDomReady(init);
    } else {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
    }
})();
