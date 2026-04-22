/**
 * Glyph - Predictions Page JavaScript
 * Handles prediction viewing and deletion
 * Uses native fetch API and event listeners
 */

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
    const currentURL = window.location.href;
    const splitIndex = currentURL.lastIndexOf('/');
    const baseUrl = currentURL.substring(0, splitIndex);
    window.location = baseUrl + '/getPrediction?task_name=' +
        encodeURIComponent(taskName) + '&model_name=' + encodeURIComponent(modelName);
}

/**
 * Delete a prediction by task name
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
    
    const url = '/models/deletePrediction?task_name=' + encodeURIComponent(taskToDelete);
    
    try {
        const response = await fetch(url, getFetchOptionsWithCsrf({
            method: 'DELETE',
            headers: { 'Content-type': 'application/json' }
        }));
        
        if (response.ok) {
            const data = await response.json();
            Toast.success(data.message || 'Prediction deleted successfully');
            // Redirect to home after deletion
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
 * Initialize predictions table event handlers
 */
function initPredictionsTable() {
    const table = document.querySelector('.prediction-table');
    if (!table) return;
    
    const clickHandler = table.dataset.clickHandler;
    
    // Add click handlers to rows
    const rows = table.querySelectorAll('tbody tr.hover-row');
    rows.forEach(row => {
        row.addEventListener('click', function() {
            if (clickHandler && typeof window[clickHandler] === 'function') {
                window[clickHandler](this.id);
            }
        });
        
        // Add keyboard support (Enter key)
        row.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                if (clickHandler && typeof window[clickHandler] === 'function') {
                    window[clickHandler](this.id);
                }
            }
        });
    });
}

/**
 * Initialize predictions page event listeners
 */
function initPredictionsPage() {
    // Initialize table handlers
    initPredictionsTable();
    
    // Handle clickable prediction rows (entire row click)
    document.querySelectorAll('.clickable-row').forEach(function(row) {
        row.addEventListener('click', function() {
            const taskName = this.getAttribute('data-task-name');
            const modelName = this.getAttribute('data-model-name');
            viewPrediction(taskName, modelName);
        });
        
        // Add keyboard support
        row.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const taskName = this.getAttribute('data-task-name');
                const modelName = this.getAttribute('data-model-name');
                viewPrediction(taskName, modelName);
            }
        });
    });
    
    // Handle delete prediction button
    const deleteBtn = document.querySelector('.delete-prediction-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', deletePrediction);
    }
    
    // Initialize hover effects for table rows
    initTableHoverEffects();
}

/**
 * Initialize hover effects for table rows
 */
function initTableHoverEffects() {
    const hoverRows = document.querySelectorAll('.hover-row');
    
    hoverRows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.background = 'rgba(0, 255, 255, 0.07)';
        });
        
        row.addEventListener('mouseleave', function() {
            this.style.background = '#000000';
        });
        
        row.addEventListener('focus', function() {
            this.style.background = 'rgba(0, 255, 255, 0.07)';
        });
        
        row.addEventListener('blur', function() {
            this.style.background = '#000000';
        });
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        initPredictionsPage();
        initSyncScroll();
    });
} else {
    initPredictionsPage();
    initSyncScroll();
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
