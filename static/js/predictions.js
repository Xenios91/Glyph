/**
 * Glyph - Predictions Page JavaScript
 * Handles prediction viewing and deletion
 * Uses native fetch API and event listeners with event delegation
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
    const baseUrl = getBaseUrl();
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
 * Initialize predictions table with event delegation
 * Uses single event listener on table instead of individual row listeners
 */
function initPredictionsTable() {
    const table = document.querySelector('.prediction-table');
    if (!table) return;
    
    const clickHandler = table.dataset.clickHandler;
    
    // Event delegation: single listener on table for all row clicks
    table.addEventListener('click', function(e) {
        const row = e.target.closest('tbody tr.hover-row');
        if (!row) return;
        
        if (clickHandler && typeof window[clickHandler] === 'function') {
            window[clickHandler](row.id);
        }
    });
    
    // Event delegation: single listener for keyboard events
    table.addEventListener('keydown', function(e) {
        const row = e.target.closest('tbody tr.hover-row');
        if (!row) return;
        
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (clickHandler && typeof window[clickHandler] === 'function') {
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
            e.preventDefault();
            e.stopPropagation();
            
            const taskName = this.getAttribute('data-task-name');
            const modelName = this.getAttribute('data-model-name');
            
            console.log('Row clicked:', { taskName, modelName });
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
    
    // Handle delete prediction button
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
    initPredictionsPage();
    initSyncScroll();
});
