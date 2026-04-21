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

/**
 * Get CSRF token from meta tag
 * @returns {string|null} CSRF token or null if not found
 */
function getCsrfToken() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    return metaTag ? metaTag.getAttribute('content') : null;
}

/**
 * Create fetch options with CSRF token
 * @param {Object} options - Original fetch options
 * @returns {Object} Fetch options with CSRF header added
 */
function getFetchOptionsWithCsrf(options) {
    const csrfToken = getCsrfToken();
    const headers = { ...options.headers };
    
    if (csrfToken) {
        headers["X-CSRF-Token"] = csrfToken;
    }
    
    return {
        ...options,
        headers: headers
    };
}

/**
 * Get access token from cookie
 * @returns {string|null} Access token or null if not found
 */
function getAccessToken() {
    const match = document.cookie.match(/access_token_cookie=([^;]+)/);
    return match ? match[1] : null;
}

/**
 * Fetch with authentication handling
 * Automatically adds auth token and handles 401 responses
 * @param {string} url - URL to fetch
 * @param {Object} options - Fetch options
 * @returns {Promise<Response>} Fetch response
 */
async function authenticatedFetch(url, options = {}) {
    const token = getAccessToken();
    const headers = { ...options.headers };
    
    if (token && !headers['Authorization']) {
        headers['Authorization'] = 'Bearer ' + token;
    }
    
    const response = await fetch(url, { ...options, headers });
    
    if (response.status === 401) {
        // Redirect to login, preserving current path
        const redirectUrl = '/login?redirect=' + encodeURIComponent(window.location.pathname);
        window.location.href = redirectUrl;
    }
    
    return response;
}

/**
 * Check if user is authenticated
 * @returns {Promise<boolean>} True if authenticated
 */
async function checkAuthStatus() {
    try {
        const response = await fetch('/auth/me', {
            headers: { 'Accept': 'application/json' }
        });
        return response.status === 200;
    } catch (error) {
        console.error('Auth check failed:', error);
        return false;
    }
}
