/**
 * Glyph - Models Page JavaScript
 * Handles model viewing and deletion
 */

/**
 * Navigate to model functions page
 * @param {string} id - Model ID element
 */
function goToModelURL(id) {
    const model_name = id.slice(0, -3);
    const status = document.getElementById(model_name + '-status');
    
    if (!status) {
        console.error('Status element not found for model:', model_name);
        return;
    }
    
    const statusText = status.innerText.trim();
    
    if (statusText === 'complete') {
        const currentURL = window.location.href;
        const splitIndex = currentURL.lastIndexOf('/');
        const url = currentURL.substring(0, splitIndex) + 
            '/api/v1/models/getFunctions?model_name=' + encodeURIComponent(model_name);
        
        if (url) {
            window.location = url;
        }
    } else if (statusText === 'N/A') {
        alert('No analysis has been performed yet!');
    } else {
        alert('Binary Analysis is not complete!');
    }
}

/**
 * Delete a model entry
 */
async function deleteModelEntry() {
    const fileNameElement = document.getElementById('file-name');
    if (!fileNameElement) {
        console.error('File name element not found');
        return;
    }
    
    const selection = fileNameElement.innerText;
    const binToDelete = selection.split(':')[1].replace(/\s+/, '');
    
    const currentURL = window.location.href;
    const url = '/models/getSymbols?binaryDel=' + encodeURIComponent(binToDelete);
    
    if (url) {
        window.location = url;
    }
}
