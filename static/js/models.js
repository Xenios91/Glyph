/**
 * Glyph - Models Page JavaScript
 * Handles model viewing and deletion
 * Uses native fetch API and event delegation
 */

/**
 * Navigate to model functions page
 * @param {HTMLElement} rowElement - Model row element
 */
function goToModelURL(rowElement) {
    const modelName = rowElement.dataset.modelName;
    const statusCell = rowElement.querySelector('.model-status-cell');
    
    if (!statusCell) {
        console.error('Status cell not found for model:', modelName);
        Toast.error('Model status not found');
        return;
    }
    
    const statusText = statusCell.dataset.status;
    
    if (statusText === 'complete') {
        const url = getBaseUrl() +
            '/api/v1/models/getFunctions?model_name=' + encodeURIComponent(modelName);
        
        if (url) {
            window.location = url;
        }
    } else if (statusText === 'na') {
        Toast.warning('No analysis has been performed yet!');
    } else {
        Toast.warning('Binary Analysis is not complete!');
    }
}

/**
 * Delete a model entry
 */
async function deleteModelEntry() {
    const fileNameElement = document.getElementById('file-name');
    if (!fileNameElement) {
        console.error('File name element not found');
        Toast.error('File name not found');
        return;
    }
    
    const selection = fileNameElement.innerText;
    const binToDelete = selection.split(':')[1].replace(/\s+/, '');
    
    const url = getBaseUrl() + '/models/getSymbols?binaryDel=' + encodeURIComponent(binToDelete);
    
    if (url) {
        window.location = url;
    }
}

/**
 * Initialize model table with event delegation
 * Uses single event listener on table instead of individual row listeners
 */
function initModelTable() {
    const table = document.querySelector('.model-table');
    if (!table) return;
    
    const clickHandler = table.dataset.clickHandler;
    
    // Event delegation: single listener on table for all row clicks
    table.addEventListener('click', function(e) {
        const row = e.target.closest('tbody tr.hover-row');
        if (!row) return;
        
        if (clickHandler && typeof window[clickHandler] === 'function') {
            window[clickHandler](row);
        }
    });
    
    // Event delegation: single listener for keyboard events
    table.addEventListener('keydown', function(e) {
        const row = e.target.closest('tbody tr.hover-row');
        if (!row) return;
        
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (clickHandler && typeof window[clickHandler] === 'function') {
                window[clickHandler](row);
            }
        }
    });
}

// Initialize when DOM is ready using utility
onDomReady(initModelTable);
