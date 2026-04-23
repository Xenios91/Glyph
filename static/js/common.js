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

/**
 * DOM Ready utility - executes callback when DOM is ready
 * @param {Function} callback - Function to execute when DOM is ready
 */
function onDomReady(callback) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', callback);
    } else {
        callback();
    }
}

/**
 * Add click and keyboard event listeners to an element
 * @param {HTMLElement} element - Element to add listeners to
 * @param {Function} clickHandler - Click event handler
 * @param {Function} keyHandler - Keyboard event handler (optional)
 */
function addInteractiveListeners(element, clickHandler, keyHandler) {
    element.addEventListener('click', clickHandler);
    
    if (keyHandler) {
        element.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                keyHandler(e);
            }
        });
    }
}

/**
 * Initialize table row hover effects using CSS classes instead of inline styles
 * @param {string} selector - CSS selector for hover rows
 */
function initTableHoverEffects(selector = '.hover-row') {
    const hoverRows = document.querySelectorAll(selector);
    
    hoverRows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.classList.add('is-hovered');
        });
        
        row.addEventListener('mouseleave', function() {
            this.classList.remove('is-hovered');
        });
        
        row.addEventListener('focus', function() {
            this.classList.add('is-hovered');
        });
        
        row.addEventListener('blur', function() {
            this.classList.remove('is-hovered');
        });
    });
}
