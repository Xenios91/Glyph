/**
 * Glyph - Symbols Page JavaScript
 * Handles function navigation and model deletion
 */

/**
 * Navigate to function details page
 * @param {string} id - Row ID element
 */
function goToFunctionURL(id) {
    const functionName = id.slice(0, -3);
    const url = '/api/v1/models/getFunction?function_name=' + 
        encodeURIComponent(functionName) + '&model_name=' + getModelName();
    
    if (url) {
        window.location = url;
    }
}

/**
 * Get the model name from the page
 * @returns {string} Model name
 */
function getModelName() {
    const modelNameElement = document.getElementById('model-name');
    if (!modelNameElement) {
        console.error('Model name element not found');
        return '';
    }
    
    const selection = modelNameElement.innerText;
    return selection.split(':')[1].replace(/\s+/, '');
}

/**
 * Delete a model by name
 */
async function deleteModel() {
    const modelNameElement = document.getElementById('model-name');
    if (!modelNameElement) {
        console.error('Model name element not found');
        return;
    }
    
    const selection = modelNameElement.innerText;
    const modelToDelete = selection.split(':')[1].replace(/\s+/, '');
    
    const url = '/api/v1/models/deleteModel?model_name=' + encodeURIComponent(modelToDelete);
    
    try {
        await fetch(url, {
            method: 'DELETE',
            headers: { 'Content-type': 'application/json' }
        });
        
        // Redirect to home after deletion
        window.location = '/';
    } catch (error) {
        console.error('Error deleting model:', error);
    }
}
