/**
 * Glyph - Common JavaScript Utilities
 * Contains shared JavaScript functions used across multiple templates
 */

// Change background color for table rows on hover
function changeBackground(id, color) {
    const element = document.getElementById(id);
    if (element) {
        element.style.background = color;
    }
}

// Navigate to a URL based on element ID
function goToURL(id) {
    // Override this function in page-specific scripts if needed
    console.log('goToURL called with id:', id);
}

// Delete an item by ID
function deleteItem(id) {
    // Override this function in page-specific scripts if needed
    console.log('deleteItem called with id:', id);
}

// Utility function to encode URL parameters
function encodeParams(params) {
    return Object.keys(params)
        .map(key => encodeURIComponent(key) + '=' + encodeURIComponent(params[key]))
        .join('&');
}

// Utility function to get current base URL
function getBaseUrl() {
    const currentURL = window.location.href;
    const splitIndex = currentURL.lastIndexOf("/");
    return currentURL.substring(0, splitIndex);
}
