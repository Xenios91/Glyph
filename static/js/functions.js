/**
 * Glyph - Function Details Page JavaScript
 * Handles function viewing and deletion
 * Uses native fetch API and event listeners
 */
'use strict';

/**
 * Delete a function by name
 */
async function deleteFunction() {
    const functionNameElement = document.getElementById('function-name');
    if (!functionNameElement) {
        console.error('Function name element not found');
        Toast.error('Function name not found');
        return;
    }
    
    const functionToDelete = extractLabelValue(functionNameElement);
    
    try {
        await deleteResource('/model/deleteFunction', { function_name: functionToDelete }, '/');
    } catch (error) {
        console.error('Error deleting function:', error);
    }
}

/**
 * Initialize function page event listeners
 */
function initFunctionPage() {
    // Bind delete function button if present
    const deleteBtn = document.querySelector('.delete-function-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', deleteFunction);
    }
}

// Initialize when DOM is ready using shared utility
onDomReady(initFunctionPage);
