/**
 * Glyph - Models Page JavaScript
 * Handles model viewing and deletion
 * Uses native fetch API and event listeners
 */

/**
 * Navigate to model functions page
 * @param {string} id - Model ID element
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
        const currentURL = window.location.href;
        const splitIndex = currentURL.lastIndexOf('/');
        const url = currentURL.substring(0, splitIndex) +
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
    
    const currentURL = window.location.href;
    const url = '/models/getSymbols?binaryDel=' + encodeURIComponent(binToDelete);
    
    if (url) {
        window.location = url;
    }
}

/**
 * Initialize model table event handlers
 */
function initModelTable() {
    const table = document.querySelector('.model-table');
    if (!table) return;
    
    const clickHandler = table.dataset.clickHandler;
    
    // Add click handlers to rows
    const rows = table.querySelectorAll('tbody tr.hover-row');
    rows.forEach(row => {
        row.addEventListener('click', function() {
            if (clickHandler && typeof window[clickHandler] === 'function') {
                window[clickHandler](this);
            }
        });
        
        // Add keyboard support (Enter key)
        row.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                if (clickHandler && typeof window[clickHandler] === 'function') {
                    window[clickHandler](this);
                }
            }
        });
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initModelTable);
} else {
    initModelTable();
}
