/**
 * Glyph - Symbols Page JavaScript
 * Handles function navigation and model deletion
 * Uses native fetch API and event listeners
 */
'use strict';

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
    return extractLabelValue(modelNameElement);
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

    const modelToDelete = extractLabelValue(modelNameElement);

    try {
        const response = await authenticatedFetch(`/api/v1/models/deleteModel?model_name=${encodeURIComponent(modelToDelete)}`, {
            method: 'DELETE',
            headers: {
                'Accept': 'application/json'
            }
        });

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
 * Initialize symbols page event listeners
 */
function initSymbolsPage() {
    // Bind delete model button
    const deleteModelBtn = document.getElementById('delete-model-btn');
    if (deleteModelBtn) {
        deleteModelBtn.addEventListener('click', deleteModel);
    }

    // Initialize table with event delegation
    initTableDelegation(
        '.symbols-table',
        ['goToFunctionURL'],
        null,
        {
            useRowId: true
        }
    );

    // Use shared hover effects from common.js instead of duplicate inline-style version
    initTableHoverEffects();

    // Initialize pagination
    const paginationEl = document.getElementById('symbols-pagination');
    const table = document.querySelector('.symbols-table');
    if (paginationEl && table) {
        const rows = table.querySelectorAll('tbody tr');
        if (rows.length > 0) {
            const pagination = new Pagination({
                tableSelector: '.symbols-table',
                paginationSelector: '#symbols-pagination',
                defaultPageSize: 10,
                pageSizes: [10, 25, 50, 100],
                storageKey: 'glyph_symbols_page_size'
            });
            pagination.init();
        } else {
            paginationEl.style.display = 'none';
        }
    }
}

// Initialize when DOM is ready using shared utility
onDomReady(initSymbolsPage);
