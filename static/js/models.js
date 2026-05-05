/**
 * Glyph - Models Page JavaScript
 * Handles model viewing, multi-selection, and bulk deletion
 * Uses native fetch API and event delegation
 */
'use strict';

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
 * Delete multiple selected models via API
 */
async function deleteSelectedModels() {
    const modelNames = selectionManager.getSelected();

    if (modelNames.length === 0) {
        Toast.warning('No models selected');
        return;
    }

    const confirmed = confirm(
        `Are you sure you want to delete ${modelNames.length} model(s)?`
    );

    if (!confirmed) return;

    try {
        const response = await authenticatedFetch('/api/v1/models/deleteModels', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ model_names: modelNames })
        });

        const data = await response.json();

        if (response.ok) {
            Toast.success(data.message || 'Models deleted successfully');
            // Signal to clear selections on reload (browser may restore checkbox state)
            sessionStorage.setItem('glyph_models_clear_selection', '1');
            // Reload the page to reflect changes
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            Toast.error(data.detail?.error_message || 'Failed to delete models');
        }
    } catch (error) {
        console.error('Error deleting models:', error);
        Toast.error('Network error while deleting models');
    }
}

// Create selection manager instance
const selectionManager = new SelectionManager({
    checkboxClass: '.model-select-checkbox',
    selectAllId: 'select-all-models',
    selectAllClass: '.model-select-all',
    deleteBtnId: 'delete-selected-btn',
    deleteBtnText: 'Delete Selected',
    storageKey: 'glyph_models_clear_selection',
    dataAttribute: 'modelName'
});

// Initialize when DOM is ready using utility
onDomReady(function() {
    selectionManager.clearSelectionsIfFlagged();

    // Initialize table with event delegation
    initTableDelegation(
        '.model-table',
        ['goToModelURL'],
        null,
        {
            checkboxSelector: selectionManager.getCheckboxSelector(),
            checkboxHandler: selectionManager.getCheckboxHandler()
        }
    );

    // Attach delete button listener (avoids inline onclick which violates CSP)
    const deleteBtn = document.getElementById('delete-selected-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', deleteSelectedModels);
    }
});
