/**
 * Glyph - Predictions Page JavaScript
 * Handles prediction viewing and deletion
 * Uses native fetch API and event delegation
 */
'use strict';

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
    
    const taskName = extractLabelValue(taskNameElement);
    const modelName = extractLabelValue(modelNameElement);
    
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

    const taskToDelete = extractLabelValue(taskNameElement);

    try {
        const response = await authenticatedFetch(`/api/v1/predictions/deletePrediction?task_name=${encodeURIComponent(taskToDelete)}`, {
            method: 'DELETE',
            headers: {
                'Accept': 'application/json'
            }
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
 * Delete multiple selected predictions via API
 */
async function deleteSelectedPredictions() {
    const taskNames = selectionManager.getSelected();

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

// Create selection manager instance
const selectionManager = new SelectionManager({
    checkboxClass: '.prediction-select-checkbox',
    selectAllId: 'select-all-predictions',
    selectAllClass: '.prediction-select-all',
    deleteBtnId: 'delete-selected-predictions-btn',
    deleteBtnText: 'Delete Selected',
    storageKey: 'glyph_predictions_clear_selection',
    dataAttribute: 'taskName'
});

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
    selectionManager.clearSelectionsIfFlagged();

    // Initialize table with event delegation
    initTableDelegation(
        '.prediction-table',
        ['goToPredictionDetailsURL'],
        null,
        {
            useRowId: true,
            checkboxSelector: selectionManager.getCheckboxSelector(),
            checkboxHandler: selectionManager.getCheckboxHandler()
        }
    );

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
    const deleteBtn = document.getElementById('delete-prediction-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', deletePrediction);
    }

    // Initialize hover effects using CSS classes
    initTableHoverEffects();

    // Initialize synchronized scrolling
    initSyncScroll();

    // Attach delete selected button listener (avoids inline onclick which violates CSP)
    const deleteSelectedBtn = document.getElementById('delete-selected-predictions-btn');
    if (deleteSelectedBtn) {
        deleteSelectedBtn.addEventListener('click', deleteSelectedPredictions);
    }
});
