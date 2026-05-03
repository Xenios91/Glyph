/**
 * Glyph - Models Page JavaScript
 * Handles model viewing, multi-selection, and bulk deletion
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
 * Delete a model entry (legacy single-delete via redirect)
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
 * Get all selected model names from checkboxes
 * @returns {string[]} Array of selected model names
 */
function getSelectedModelNames() {
    const checkboxes = document.querySelectorAll('.model-select-checkbox:checked');
    return Array.from(checkboxes).map(cb => cb.dataset.modelName);
}

/**
 * Update the delete button state based on selection count
 */
function updateDeleteButtonState() {
    const deleteBtn = document.getElementById('delete-selected-btn');
    if (!deleteBtn) return;

    const selectedCount = document.querySelectorAll('.model-select-checkbox:checked').length;
    deleteBtn.disabled = selectedCount === 0;
    deleteBtn.textContent = selectedCount > 0
        ? `Delete Selected (${selectedCount})`
        : 'Delete Selected';
}

/**
 * Sync row selection class with checkbox state
 * @param {HTMLElement} row - Table row element
 */
function syncRowSelection(row) {
    const checkbox = row.querySelector('.model-select-checkbox');
    if (checkbox) {
        row.classList.toggle('is-selected', checkbox.checked);
    }
}

/**
 * Handle select-all checkbox toggle
 * @param {boolean} checked - Whether all should be selected
 */
function toggleSelectAll(checked) {
    const checkboxes = document.querySelectorAll('.model-select-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = checked;
        const row = cb.closest('tr');
        if (row) syncRowSelection(row);
    });
    updateDeleteButtonState();
}

/**
 * Check if all checkboxes are selected and update select-all accordingly
 */
function updateSelectAllState() {
    const selectAll = document.getElementById('select-all-models');
    if (!selectAll) return;

    const allCheckboxes = document.querySelectorAll('.model-select-checkbox');
    const checkedCount = document.querySelectorAll('.model-select-checkbox:checked').length;
    selectAll.checked = allCheckboxes.length > 0 && checkedCount === allCheckboxes.length;
    selectAll.indeterminate = checkedCount > 0 && checkedCount < allCheckboxes.length;
}

/**
 * Delete multiple selected models via API
 */
async function deleteSelectedModels() {
    const modelNames = getSelectedModelNames();

    if (modelNames.length === 0) {
        Toast.warning('No models selected');
        return;
    }

    const confirmed = confirm(
        `Are you sure you want to delete ${modelNames.length} model(s)?`
    );

    if (!confirmed) return;

    const url = getBaseUrl() + '/api/v1/models/deleteModels?model_names=' + encodeURIComponent(modelNames.join(','));

    try {
        const response = await authenticatedFetch(url, {
            method: 'DELETE',
            headers: { 'Accept': 'application/json' }
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

/**
 * Initialize model table with event delegation
 * Uses single event listener on table instead of individual row listeners
 */
function initModelTable() {
    const table = document.querySelector('.model-table');
    if (!table) return;

    const clickHandler = table.dataset.clickHandler;

    // Event delegation: single listener on table for all clicks
    table.addEventListener('click', function(e) {
        // Handle checkbox clicks - prevent row navigation
        const checkbox = e.target.closest('.model-select-checkbox, .model-select-all');
        if (checkbox) {
            e.stopPropagation();

            // Small delay to allow the checkbox state to update before handlers run
            setTimeout(() => {
                if (checkbox.classList.contains('model-select-all')) {
                    toggleSelectAll(checkbox.checked);
                } else {
                    const row = checkbox.closest('tr');
                    if (row) syncRowSelection(row);
                    updateSelectAllState();
                    updateDeleteButtonState();
                }
            }, 0);
            return;
        }

        // Handle row clicks (navigation)
        const row = e.target.closest('tbody tr.hover-row');
        if (!row) return;

        // Only navigate if the click was not on a checkbox
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
// Clear selections if flagged after a bulk delete (browser may restore checkbox state on reload)
function clearSelectionsIfFlagged() {
    if (sessionStorage.getItem('glyph_models_clear_selection') === '1') {
        sessionStorage.removeItem('glyph_models_clear_selection');
        const checkboxes = document.querySelectorAll('.model-select-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = false;
            const row = cb.closest('tr');
            if (row) row.classList.remove('is-selected');
        });
        const selectAll = document.getElementById('select-all-models');
        if (selectAll) {
            selectAll.checked = false;
            selectAll.indeterminate = false;
        }
        updateDeleteButtonState();
    }
}

onDomReady(function() {
    clearSelectionsIfFlagged();
    initModelTable();

    // Attach delete button listener (avoids inline onclick which violates CSP)
    const deleteBtn = document.getElementById('delete-selected-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', deleteSelectedModels);
    }
});
