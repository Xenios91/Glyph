/**
 * Glyph - Common JavaScript Utilities
 * Contains shared JavaScript functions used across multiple templates
 */
'use strict';

// ============================================================
// Core Utilities
// ============================================================

/**
 * Utility function to encode URL parameters
 * @param {Object} params - Key-value pairs to encode
 * @returns {string} Encoded query string
 */
function encodeParams(params) {
    return Object.keys(params)
        .map(key => encodeURIComponent(key) + '=' + encodeURIComponent(params[key]))
        .join('&');
}

/**
 * Get the base URL (origin) of the current page
 * @returns {string} The origin (protocol + host)
 */
function getBaseUrl() {
    return window.location.origin;
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

// ============================================================
// DOM Utilities
// ============================================================

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

/**
 * Show error message in an element and auto-hide after 5 seconds
 * @param {string} elementId - ID of the error display element
 * @param {string} message - Error message to display
 */
function showError(elementId, message) {
    const errorDiv = document.getElementById(elementId);
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    }
}

/**
 * Hide error message element
 * @param {string} elementId - ID of the error display element
 */
function hideError(elementId) {
    const errorDiv = document.getElementById(elementId);
    if (errorDiv) {
        errorDiv.style.display = 'none';
    }
}

// ============================================================
// Form Validation Utilities
// ============================================================

/**
 * Set up real-time field validation with blur and input handlers
 * @param {HTMLElement} input - Input element to validate
 * @param {Function} validator - Validation function returning true if valid
 */
function setupFieldValidation(input, validator) {
    if (!input) return;
    
    input.addEventListener('blur', function() {
        if (!validator(this.value)) {
            this.classList.add('is-error');
            this.setAttribute('aria-invalid', 'true');
        } else {
            this.classList.remove('is-error');
            this.setAttribute('aria-invalid', 'false');
        }
    });
    
    input.addEventListener('input', function() {
        if (this.classList.contains('is-error')) {
            this.classList.remove('is-error');
            this.setAttribute('aria-invalid', 'false');
        }
    });
}

// ============================================================
// Table Delegation Utilities
// ============================================================

/**
 * Initialize table with event delegation for row clicks and keyboard navigation
 * @param {string} tableSelector - CSS selector for the table
 * @param {string[]} allowedHandlers - Whitelist of allowed handler function names
 * @param {Function} handler - Function to call on row click (receives row element or row.id)
 * @param {Object} options - Optional configuration
 * @param {boolean} options.useRowId - Pass row.id instead of row element to handler
 * @param {Function} options.checkboxHandler - Optional handler for checkbox clicks
 */
function initTableDelegation(tableSelector, allowedHandlers, handler, options = {}) {
    const table = document.querySelector(tableSelector);
    if (!table) return;

    const clickHandlerName = table.dataset.clickHandler;
    const useRowId = options.useRowId || false;

    // Event delegation: single listener on table for all clicks
    table.addEventListener('click', function(e) {
        // Handle checkbox clicks if handler provided
        if (options.checkboxHandler) {
            const checkbox = e.target.closest(options.checkboxSelector || 'input[type="checkbox"]');
            if (checkbox) {
                e.stopPropagation();
                setTimeout(() => options.checkboxHandler(checkbox), 0);
                return;
            }
        }

        // Handle row clicks (navigation)
        const row = e.target.closest('tbody tr.hover-row');
        if (!row) return;

        if (clickHandlerName && allowedHandlers.includes(clickHandlerName) && typeof window[clickHandlerName] === 'function') {
            window[clickHandlerName](useRowId ? row.id : row);
        }
    });

    // Event delegation: single listener for keyboard events
    table.addEventListener('keydown', function(e) {
        const row = e.target.closest('tbody tr.hover-row');
        if (!row) return;

        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (clickHandlerName && allowedHandlers.includes(clickHandlerName) && typeof window[clickHandlerName] === 'function') {
                window[clickHandlerName](useRowId ? row.id : row);
            }
        }
    });
}

// ============================================================
// Selection Management Utilities
// ============================================================

/**
 * SelectionManager - Handles checkbox selection, select-all, and delete button state
 * for table-based lists with bulk operations.
 * 
 * @example
 * const manager = new SelectionManager({
 *     checkboxClass: '.model-select-checkbox',
 *     selectAllId: 'select-all-models',
 *     deleteBtnId: 'delete-selected-btn',
 *     deleteBtnText: 'Delete Selected',
 *     storageKey: 'glyph_models_clear_selection',
 *     dataAttribute: 'model-name'
 * });
 * manager.init();
 */
class SelectionManager {
    /**
     * @param {Object} config - Configuration options
     * @param {string} config.checkboxClass - CSS class for individual checkboxes
     * @param {string} config.selectAllId - ID of the select-all checkbox
     * @param {string} config.deleteBtnId - ID of the delete button
     * @param {string} config.deleteBtnText - Base text for delete button
     * @param {string} config.storageKey - SessionStorage key for clear flag
     * @param {string} config.dataAttribute - Data attribute name on checkboxes (e.g., 'model-name')
     * @param {string} [config.selectAllClass] - CSS class for select-all checkbox
     * @param {Function} [config.onSelectAll] - Callback when select-all is toggled
     * @param {Function} [config.onSelectionChange] - Callback when individual selection changes
     */
    constructor(config) {
        this.checkboxClass = config.checkboxClass;
        this.selectAllId = config.selectAllId;
        this.deleteBtnId = config.deleteBtnId;
        this.deleteBtnText = config.deleteBtnText;
        this.storageKey = config.storageKey;
        this.dataAttribute = config.dataAttribute;
        this.selectAllClass = config.selectAllClass || '.select-all';
        this.onSelectAll = config.onSelectAll || (() => {});
        this.onSelectionChange = config.onSelectionChange || (() => {});
    }

    /**
     * Get all selected values from checkboxes
     * @returns {string[]} Array of selected values
     */
    getSelected() {
        const checkboxes = document.querySelectorAll(`${this.checkboxClass}:checked`);
        return Array.from(checkboxes).map(cb => cb.dataset[this.dataAttribute]);
    }

    /**
     * Update the delete button state based on selection count
     */
    updateDeleteButtonState() {
        const deleteBtn = document.getElementById(this.deleteBtnId);
        if (!deleteBtn) return;

        const selectedCount = document.querySelectorAll(`${this.checkboxClass}:checked`).length;
        deleteBtn.disabled = selectedCount === 0;
        deleteBtn.textContent = selectedCount > 0
            ? `${this.deleteBtnText} (${selectedCount})`
            : this.deleteBtnText;
    }

    /**
     * Sync row selection class with checkbox state
     * @param {HTMLElement} row - Table row element
     */
    syncRowSelection(row) {
        const checkbox = row.querySelector(this.checkboxClass);
        if (checkbox) {
            row.classList.toggle('is-selected', checkbox.checked);
        }
    }

    /**
     * Handle select-all checkbox toggle
     * @param {boolean} checked - Whether all should be selected
     */
    toggleSelectAll(checked) {
        const checkboxes = document.querySelectorAll(this.checkboxClass);
        checkboxes.forEach(cb => {
            cb.checked = checked;
            const row = cb.closest('tr');
            if (row) this.syncRowSelection(row);
        });
        this.updateDeleteButtonState();
        this.onSelectAll(checked);
    }

    /**
     * Check if all checkboxes are selected and update select-all accordingly
     */
    updateSelectAllState() {
        const selectAll = document.getElementById(this.selectAllId);
        if (!selectAll) return;

        const allCheckboxes = document.querySelectorAll(this.checkboxClass);
        const checkedCount = document.querySelectorAll(`${this.checkboxClass}:checked`).length;
        selectAll.checked = allCheckboxes.length > 0 && checkedCount === allCheckboxes.length;
        selectAll.indeterminate = checkedCount > 0 && checkedCount < allCheckboxes.length;
    }

    /**
     * Clear selections if flagged after a bulk delete
     */
    clearSelectionsIfFlagged() {
        if (sessionStorage.getItem(this.storageKey) === '1') {
            sessionStorage.removeItem(this.storageKey);
            const checkboxes = document.querySelectorAll(this.checkboxClass);
            checkboxes.forEach(cb => {
                cb.checked = false;
                const row = cb.closest('tr');
                if (row) row.classList.remove('is-selected');
            });
            const selectAll = document.getElementById(this.selectAllId);
            if (selectAll) {
                selectAll.checked = false;
                selectAll.indeterminate = false;
            }
            this.updateDeleteButtonState();
        }
    }

    /**
     * Get the checkbox click handler for use with initTableDelegation
     * @returns {Function} Checkbox click handler
     */
    getCheckboxHandler() {
        return (checkbox) => {
            if (checkbox.classList.contains(this.selectAllClass.slice(1))) {
                this.toggleSelectAll(checkbox.checked);
            } else {
                const row = checkbox.closest('tr');
                if (row) this.syncRowSelection(row);
                this.updateSelectAllState();
                this.updateDeleteButtonState();
                this.onSelectionChange(checkbox);
            }
        };
    }

    /**
     * Get the checkbox selector for use with initTableDelegation
     * @returns {string} Combined selector for individual and select-all checkboxes
     */
    getCheckboxSelector() {
        return `${this.checkboxClass}, ${this.selectAllClass}`;
    }
}

// ============================================================
// API Operation Utilities
// ============================================================

/**
 * Delete a resource via authenticated fetch
 * @param {string} url - API endpoint URL
 * @param {Object} body - Request body object
 * @param {string} [redirectUrl] - URL to redirect to on success (optional)
 * @returns {Promise<Object>} Response data
 */
async function deleteResource(url, body, redirectUrl) {
    try {
        const response = await authenticatedFetch(url, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(body)
        });

        const data = await response.json();

        if (response.ok) {
            if (typeof Toast !== 'undefined') {
                Toast.success(data.message || 'Deleted successfully');
            }
            if (redirectUrl) {
                setTimeout(() => {
                    window.location = redirectUrl;
                }, 1000);
            }
            return data;
        } else {
            const errorMessage = data.detail || data.message || 'Failed to delete resource';
            if (typeof Toast !== 'undefined') {
                Toast.error(errorMessage);
            }
            throw new Error(errorMessage);
        }
    } catch (error) {
        if (typeof Toast !== 'undefined' && !error.message.includes('Failed to delete')) {
            Toast.error('Network error. Please try again.');
        }
        throw error;
    }
}

/**
 * Extract value from labeled text (e.g., "Model Name: my_model" -> "my_model")
 * @param {HTMLElement} element - Element containing labeled text
 * @returns {string} Extracted value
 */
function extractLabelValue(element) {
    if (!element) return '';
    const text = element.innerText;
    const parts = text.split(':');
    return parts.length > 1 ? parts.slice(1).join(':').replace(/^\s+|\s+$/g, '') : text.trim();
}

// ============================================================
// Initialization
// ============================================================

// Initialize back button handlers (replaces inline onclick="history.back()")
document.addEventListener('DOMContentLoaded', function() {
    var backButtons = document.querySelectorAll('.back-btn');
    backButtons.forEach(function(btn) {
        btn.addEventListener('click', function() {
            history.back();
        });
    });
});
