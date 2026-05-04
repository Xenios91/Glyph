/**
 * Glyph - Predictions Page JavaScript
 * Handles prediction viewing and deletion
 * Uses native fetch API and event listeners with event delegation
 */
'use strict';

// Whitelist of allowed click handler function names to prevent arbitrary code execution
const ALLOWED_CLICK_HANDLERS = ['goToPredictionDetailsURL'];

/**
 * Navigate to prediction details page
 * @param {string} id - Row ID element
 */
function goToPredictionDetailsURL(id) {
    const functionName = id.slice(0, -3);
    const taskNameElement = document.getElementById('task-name');
    const modelNameElement = document.getElementById('model-name');
    
    if (!taskNameElement || !modelNameElement) {
        console.error('Task name or model name element not found');
        return;
    }
    
    const taskName = taskNameElement.innerText.split(':')[1].replace(/\s+/, '');
    const modelName = modelNameElement.innerText.split(':')[1].replace(/\s+/, '');
    
    const url = '/api/v1/models/getPredictionDetails?function_name=' +
        encodeURIComponent(functionName) +
        '&task_name=' + encodeURIComponent(taskName) +
        '&model_name=' + encodeURIComponent(modelName);
    
    if (url) {
        window.location = url;
    }
}

/**
 * Navigate to prediction details page (alternative signature)
 * @param {string} functionName - Name of the function
 * @param {string} modelName - Name of the model
 * @param {string} taskName - Name of the task
 */
window.goToPredictionDetails = function goToPredictionDetails(functionName, modelName, taskName) {
    const url = '/api/v1/models/getPredictionDetails?function_name=' + encodeURIComponent(functionName) +
        '&task_name=' + encodeURIComponent(taskName) +
        '&model_name=' + encodeURIComponent(modelName);
    
    if (url) {
        window.location = url;
    }
}

/**
 * Navigate to view prediction page
 * @param {string} taskName - Name of the task
 * @param {string} modelName - Name of the model
 */
function viewPrediction(taskName, modelName) {
    const baseUrl = getBaseUrl();
    window.location = baseUrl + '/getPrediction?task_name=' +
        encodeURIComponent(taskName) + '&model_name=' + encodeURIComponent(modelName);
}

/**
 * Delete a prediction by task name (legacy single-delete)
 */
async function deletePrediction() {
    const taskNameElement = document.getElementById('task-name');
    if (!taskNameElement) {
        console.error('Task name element not found');
        Toast.error('Task name not found');
        return;
    }

    const selection = taskNameElement.innerText;
    const taskToDelete = selection.split(':')[1].replace(/\s+/, '');

    try {
        const response = await authenticatedFetch('/api/v1/predictions/deletePrediction', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ task_name: taskToDelete })
        });

        if (response.ok) {
            const data = await response.json();
            Toast.success(data.message || 'Prediction deleted successfully');
            setTimeout(() => {
                window.location = '/';
            }, 1000);
        } else {
            const errorData = await response.json().catch(() => ({}));
            const errorMessage = errorData.detail || errorData.message || 'Failed to delete prediction';
            Toast.error(errorMessage);
        }
    } catch (error) {
        console.error('Error deleting prediction:', error);
        Toast.error('Network error. Please try again.');
    }
}

/**
 * Get all selected task names from checkboxes
 * @returns {string[]} Array of selected task names
 */
function getSelectedTaskNames() {
    const checkboxes = document.querySelectorAll('.prediction-select-checkbox:checked');
    return Array.from(checkboxes).map(cb => cb.dataset.taskName);
}

/**
 * Update the delete button state based on selection count
 */
function updatePredictionDeleteButtonState() {
    const deleteBtn = document.getElementById('delete-selected-predictions-btn');
    if (!deleteBtn) return;

    const selectedCount = document.querySelectorAll('.prediction-select-checkbox:checked').length;
    deleteBtn.disabled = selectedCount === 0;
    deleteBtn.textContent = selectedCount > 0
        ? `Delete Selected (${selectedCount})`
        : 'Delete Selected';
}

/**
 * Sync row selection class with checkbox state
 * @param {HTMLElement} row - Table row element
 */
function syncPredictionRowSelection(row) {
    const checkbox = row.querySelector('.prediction-select-checkbox');
    if (checkbox) {
        row.classList.toggle('is-selected', checkbox.checked);
    }
}

/**
 * Handle select-all checkbox toggle for predictions
 * @param {boolean} checked - Whether all should be selected
 */
function toggleSelectAllPredictions(checked) {
    const checkboxes = document.querySelectorAll('.prediction-select-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = checked;
        const row = cb.closest('tr');
        if (row) syncPredictionRowSelection(row);
    });
    updatePredictionDeleteButtonState();
}

/**
 * Check if all prediction checkboxes are selected and update select-all accordingly
 */
function updatePredictionSelectAllState() {
    const selectAll = document.getElementById('select-all-predictions');
    if (!selectAll) return;

    const allCheckboxes = document.querySelectorAll('.prediction-select-checkbox');
    const checkedCount = document.querySelectorAll('.prediction-select-checkbox:checked').length;
    selectAll.checked = allCheckboxes.length > 0 && checkedCount === allCheckboxes.length;
    selectAll.indeterminate = checkedCount > 0 && checkedCount < allCheckboxes.length;
}

/**
 * Delete multiple selected predictions via API
 */
async function deleteSelectedPredictions() {
    const taskNames = getSelectedTaskNames();

    if (taskNames.length === 0) {
        Toast.warning('No predictions selected');
        return;
    }

    const confirmed = confirm(
        `Are you sure you want to delete ${taskNames.length} prediction(s)?`
    );

    if (!confirmed) return;

    try {
        const response = await authenticatedFetch('/api/v1/predictions/deletePredictions', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ task_names: taskNames })
        });

        const data = await response.json();

        if (response.ok) {
            Toast.success(data.message || 'Predictions deleted successfully');
            sessionStorage.setItem('glyph_predictions_clear_selection', '1');
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            Toast.error(data.detail?.error_message || 'Failed to delete predictions');
        }
    } catch (error) {
        console.error('Error deleting predictions:', error);
        Toast.error('Network error while deleting predictions');
    }
}

/**
 * Clear selections if flagged after a bulk delete
 */
function clearPredictionSelectionsIfFlagged() {
    if (sessionStorage.getItem('glyph_predictions_clear_selection') === '1') {
        sessionStorage.removeItem('glyph_predictions_clear_selection');
        const checkboxes = document.querySelectorAll('.prediction-select-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = false;
            const row = cb.closest('tr');
            if (row) row.classList.remove('is-selected');
        });
        const selectAll = document.getElementById('select-all-predictions');
        if (selectAll) {
            selectAll.checked = false;
            selectAll.indeterminate = false;
        }
        updatePredictionDeleteButtonState();
    }
}

/**
 * Initialize predictions table with event delegation
 * Uses single event listener on table instead of individual row listeners
 */
function initPredictionsTable() {
    const table = document.querySelector('.prediction-table');
    if (!table) return;

    const clickHandler = table.dataset.clickHandler;

    // Event delegation: single listener on table for all clicks
    table.addEventListener('click', function(e) {
        // Handle checkbox clicks - prevent row navigation
        const checkbox = e.target.closest('.prediction-select-checkbox, .prediction-select-all');
        if (checkbox) {
            e.stopPropagation();

            setTimeout(() => {
                if (checkbox.classList.contains('prediction-select-all')) {
                    toggleSelectAllPredictions(checkbox.checked);
                } else {
                    const row = checkbox.closest('tr');
                    if (row) syncPredictionRowSelection(row);
                    updatePredictionSelectAllState();
                    updatePredictionDeleteButtonState();
                }
            }, 0);
            return;
        }

        // Handle row clicks (navigation)
        const row = e.target.closest('tbody tr.hover-row');
        if (!row) return;

        if (clickHandler && ALLOWED_CLICK_HANDLERS.includes(clickHandler) && typeof window[clickHandler] === 'function') {
            window[clickHandler](row.id);
        }
    });

    // Event delegation: single listener for keyboard events
    table.addEventListener('keydown', function(e) {
        const row = e.target.closest('tbody tr.hover-row');
        if (!row) return;

        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (clickHandler && ALLOWED_CLICK_HANDLERS.includes(clickHandler) && typeof window[clickHandler] === 'function') {
                window[clickHandler](row.id);
            }
        }
    });
}

/**
 * Initialize predictions page event listeners with event delegation
 */
function initPredictionsPage() {
    // Initialize table handlers with event delegation
    initPredictionsTable();

    // Add click handler directly to table rows for predictions list page
    const clickableRows = document.querySelectorAll('.clickable-row');
    clickableRows.forEach(row => {
        row.addEventListener('click', function(e) {
            // Don't navigate if clicking a checkbox
            const checkbox = e.target.closest('.prediction-select-checkbox, .prediction-select-all');
            if (checkbox) return;

            e.preventDefault();
            e.stopPropagation();

            const taskName = this.getAttribute('data-task-name');
            const modelName = this.getAttribute('data-model-name');

            viewPrediction(taskName, modelName);
        });

        // Keyboard handler for accessibility
        row.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const taskName = this.getAttribute('data-task-name');
                const modelName = this.getAttribute('data-model-name');
                viewPrediction(taskName, modelName);
            }
        });
    });

    // Handle delete prediction button (legacy single-delete)
    const deleteBtn = document.querySelector('.delete-prediction-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', deletePrediction);
    }

    // Initialize hover effects using CSS classes
    initTableHoverEffects();
}

/**
 * Initialize synchronized scrolling for token display containers
 */
function initSyncScroll() {
    const modelTokensDiv = document.getElementById('model_tokens_div');
    const predictionTokensDiv = document.getElementById('prediction_tokens_div');
    
    if (!modelTokensDiv || !predictionTokensDiv) {
        return;
    }
    
    // Scroll model_tokens_div when prediction_tokens_div scrolls
    predictionTokensDiv.addEventListener('scroll', function() {
        modelTokensDiv.scrollTop = this.scrollTop;
    });
    
    // Scroll prediction_tokens_div when model_tokens_div scrolls
    modelTokensDiv.addEventListener('scroll', function() {
        predictionTokensDiv.scrollTop = this.scrollTop;
    });
}

// Initialize when DOM is ready using utility
onDomReady(function() {
    clearPredictionSelectionsIfFlagged();
    initPredictionsPage();
    initSyncScroll();

    // Attach delete selected button listener (avoids inline onclick which violates CSP)
    const deleteSelectedBtn = document.getElementById('delete-selected-predictions-btn');
    if (deleteSelectedBtn) {
        deleteSelectedBtn.addEventListener('click', deleteSelectedPredictions);
    }
});
