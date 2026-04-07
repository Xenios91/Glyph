/**
 * Glyph - Function Details Page JavaScript
 * Handles function viewing and deletion
 */

/**
 * Delete a function by name
 */
async function deleteFunction() {
    const functionNameElement = document.getElementById('function-name');
    if (!functionNameElement) {
        console.error('Function name element not found');
        return;
    }
    
    const selection = functionNameElement.innerText;
    const functionToDelete = selection.split(':')[1].replace(/\s+/, '');
    
    const url = '/model/deleteFunction?function_name=' + encodeURIComponent(functionToDelete);
    
    try {
        await fetch(url, getFetchOptionsWithCsrf({
            method: 'DELETE',
            headers: { 'Content-type': 'application/json' }
        }));
        
        // Redirect to home after deletion
        window.location = '/';
    } catch (error) {
        console.error('Error deleting function:', error);
    }
}
