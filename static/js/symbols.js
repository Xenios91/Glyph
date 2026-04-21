/**
 * Glyph - Symbols Page JavaScript
 * Handles function navigation and model deletion
 * Uses native fetch API and event listeners
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
        Toast.error('Model name not found');
        return;
    }
    
    const selection = modelNameElement.innerText;
    const modelToDelete = selection.split(':')[1].replace(/\s+/, '');
    
    const url = '/api/v1/models/deleteModel?model_name=' + encodeURIComponent(modelToDelete);
    
    try {
        const response = await fetch(url, getFetchOptionsWithCsrf({
            method: 'DELETE',
            headers: { 'Content-type': 'application/json' }
        }));
        
        if (response.ok) {
            const data = await response.json();
            Toast.success(data.message || 'Model deleted successfully');
            // Redirect to home after deletion
            setTimeout(() => {
                window.location = '/';
            }, 1000);
        } else {
            const errorData = await response.json().catch(() => ({}));
            const errorMessage = errorData.detail || errorData.message || 'Failed to delete model';
            Toast.error(errorMessage);
        }
    } catch (error) {
        console.error('Error deleting model:', error);
        Toast.error('Network error. Please try again.');
    }
}

/**
 * Initialize symbols table event handlers
 */
function initSymbolsTable() {
    const table = document.querySelector('.symbols-table');
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

/**
 * Initialize symbols page event listeners
 */
function initSymbolsPage() {
    // Bind delete model button
    const deleteBtn = document.getElementById('delete-model-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', deleteModel);
    }
    
    // Initialize table handlers
    initSymbolsTable();
    initTableHoverEffects();
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSymbolsPage);
} else {
    initSymbolsPage();
}
