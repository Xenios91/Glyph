/**
 * Glyph - Predictions Page JavaScript
 * Handles prediction viewing and deletion
 */

/**
 * Navigate to prediction details page
 * @param {string} functionName - Name of the function
 * @param {string} modelName - Name of the model
 * @param {string} taskName - Name of the task
 */
function goToURL(functionName, modelName, taskName) {
    const currentURL = window.location.href;
    const splitIndex = currentURL.lastIndexOf('/');
    const url = currentURL.substring(0, splitIndex) + 
        '/models/getPredictionDetails?function_name=' + encodeURIComponent(functionName) + 
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
        return;
    }
    
    const selection = taskNameElement.innerText;
    const taskToDelete = selection.split(':')[1].replace(/\s+/, '');
    
    const url = '/models/deletePrediction?task_name=' + encodeURIComponent(taskToDelete);
    
    try {
        await fetch(url, getFetchOptionsWithCsrf({
            method: 'DELETE',
            headers: { 'Content-type': 'application/json' }
        }));
        
        // Redirect to home after deletion
        window.location = '/';
    } catch (error) {
        console.error('Error deleting prediction:', error);
    }
}

/**
 * Initialize predictions page event listeners
 */
function initPredictionsPage() {
    // Handle row clicks for function details
    document.querySelectorAll('tr[id^="prediction-func-"]').forEach(function(row) {
        row.addEventListener('click', function() {
            const functionName = this.getAttribute('data-function-name');
            const modelName = this.getAttribute('data-model-name');
            const taskName = this.getAttribute('data-task-name');
            goToURL(functionName, modelName, taskName);
        });
    });
    
    // Handle view prediction buttons
    document.querySelectorAll('.view-prediction-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const taskName = this.getAttribute('data-task-name');
            const modelName = this.getAttribute('data-model-name');
            viewPrediction(taskName, modelName);
        });
    });
    
    // Handle delete prediction button
    const deleteBtn = document.querySelector('.delete-prediction-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', deletePrediction);
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPredictionsPage);
} else {
    initPredictionsPage();
}
