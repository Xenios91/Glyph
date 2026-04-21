/**
 * Glyph - Function Details Page JavaScript
 * Handles function viewing and deletion
 * Uses native fetch API and event listeners
 */

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
    
    const selection = functionNameElement.innerText;
    const functionToDelete = selection.split(':')[1].replace(/\s+/, '');
    
    const url = '/model/deleteFunction?function_name=' + encodeURIComponent(functionToDelete);
    
    try {
        const response = await fetch(url, getFetchOptionsWithCsrf({
            method: 'DELETE',
            headers: { 'Content-type': 'application/json' }
        }));
        
        if (response.ok) {
            const data = await response.json();
            Toast.success(data.message || 'Function deleted successfully');
            // Redirect to home after deletion
            setTimeout(() => {
                window.location = '/';
            }, 1000);
        } else {
            const errorData = await response.json().catch(() => ({}));
            const errorMessage = errorData.detail || errorData.message || 'Failed to delete function';
            Toast.error(errorMessage);
        }
    } catch (error) {
        console.error('Error deleting function:', error);
        Toast.error('Network error. Please try again.');
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

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFunctionPage);
} else {
    initFunctionPage();
}
