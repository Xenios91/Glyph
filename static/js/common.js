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
 * Custom error class for authentication failures
 */
class AuthError extends Error {
    /**
     * @param {string} message - Error message
     * @param {number} status - HTTP status code
     */
    constructor(message, status) {
        super(message);
        this.name = 'AuthError';
        this.status = status;
    }
}

/**
 * Custom error class for API errors
 */
class ApiError extends Error {
    /**
     * @param {string} message - Error message
     * @param {number} status - HTTP status code
     * @param {Object} [details] - Additional error details
     */
    constructor(message, status, details) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.details = details || null;
    }
}

/**
 * Fetch with authentication handling
 * Automatically adds auth token and handles 401 responses
 * @param {string} url - URL to fetch
 * @param {Object} options - Fetch options
 * @param {Object} [options] - Fetch options
 * @param {boolean} [options.redirectOn401=true] - Whether to redirect on 401
 * @param {number} [options.timeout=30000] - Request timeout in milliseconds
 * @returns {Promise<Response>} Fetch response
 * @throws {AuthError} - When authentication fails (401)
 * @throws {ApiError} - When server returns error status (4xx, 5xx)
 * @throws {Error} - When network error or timeout occurs
 */
async function authenticatedFetch(url, options = {}, fetchOptions = {}) {
    const token = getAccessToken();
    const shouldRedirect = fetchOptions.redirectOn401 !== false;
    const timeout = fetchOptions.timeout || 30000;
    const fetchOpts = { ...options };

    // When body is FormData, the browser must auto-set Content-Type with the
    // multipart boundary. Setting an explicit headers object prevents that,
    // so skip adding Authorization and rely on the cookie instead.
    const isFormData = options.body instanceof FormData;

    if (!isFormData && token) {
        let headers = options.headers ? { ...options.headers } : {};
        if (!headers['Authorization']) {
            headers['Authorization'] = 'Bearer ' + token;
        }
        if (Object.keys(headers).length > 0) {
            fetchOpts.headers = headers;
        }
    }

    try {
        // Create a timeout signal
        const timeoutController = new AbortController();
        const timeoutId = setTimeout(() => timeoutController.abort(), timeout);

        if (!fetchOpts.signal) {
            fetchOpts.signal = timeoutController.signal;
        }

        const response = await fetch(url, fetchOpts);
        clearTimeout(timeoutId);

        if (response.status === 401) {
            if (shouldRedirect) {
                // Redirect to login, preserving current path
                const redirectUrl = '/login?redirect=' + encodeURIComponent(window.location.pathname);
                window.location.href = redirectUrl;
            }
            throw new AuthError('Authentication required', 401);
        }

        if (response.status >= 400) {
            let details = null;
            try {
                details = await response.json();
            } catch (e) {
                // Ignore JSON parse errors for error responses
            }
            const message = (details && (details.detail || details.message)) || `HTTP error ${response.status}`;
            throw new ApiError(message, response.status, details);
        }

        return response;
    } catch (error) {
        // Re-throw AbortError as a timeout error
        if (error.name === 'AbortError') {
            throw new Error(`Request timed out after ${timeout}ms`);
        }
        // Re-throw our custom errors
        if (error instanceof AuthError || error instanceof ApiError) {
            throw error;
        }
        // Wrap network errors
        throw new Error(`Network error: ${error.message || 'Failed to fetch'}`);
    }
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
// Pagination
// ============================================================

/**
 * Pagination - Table pagination utility supporting both client-side and server-side modes
 *
 * @example Client-side (hides/shows rows in DOM)
 * const pagination = new Pagination({
 *     tableSelector: '.my-table',
 *     paginationSelector: '#my-pagination',
 *     defaultPageSize: 10,
 *     pageSizes: [10, 25, 50, 100]
 * });
 * pagination.init();
 *
 * @example Server-side (calls onPageChange callback)
 * const pagination = new Pagination({
 *     paginationSelector: '#my-pagination',
 *     defaultPageSize: 10,
 *     pageSizes: [10, 25, 50, 100],
 *     onPageChange: function(page, pageSize) {
 *         // Fetch data for page and re-render table
 *         loadTableData(page, pageSize);
 *     },
 *     onUpdateControls: function(totalRows, totalPages, currentPage, pageSize) {
 *         // Optional: call pagination.setTotals(totalRows, totalPages) after data loads
 *     }
 * });
 * pagination.init();
 */
class Pagination {
    /**
     * @param {Object} config - Configuration options
     * @param {string} [config.tableSelector] - CSS selector for the table element (client-side mode only)
     * @param {string} config.paginationSelector - CSS selector for the pagination controls container
     * @param {number} [config.defaultPageSize=10] - Default number of rows per page
     * @param {number[]} [config.pageSizes=[10, 25, 50, 100]] - Available page size options
     * @param {string} [config.storageKey] - SessionStorage key for persisting page size
     * @param {Function} [config.onPageChange] - Callback(page, pageSize) for server-side pagination
     * @param {number} [config.totalRows=0] - Total rows count (server-side mode)
     * @param {number} [config.totalPages=1] - Total pages count (server-side mode)
     */
    constructor(config) {
        this.tableSelector = config.tableSelector || '';
        this.paginationSelector = config.paginationSelector;
        this.defaultPageSize = config.defaultPageSize || 10;
        this.pageSizes = config.pageSizes || [10, 25, 50, 100];
        this.storageKey = config.storageKey || '';
        this.onPageChange = config.onPageChange || null;
        
        this.currentPage = 1;
        this.pageSize = this.defaultPageSize;
        this.totalRows = config.totalRows || 0;
        this.totalPages = config.totalPages || 1;
        this.rows = [];
        this._idPrefix = this._generateIdPrefix();
    }

    /**
     * Generate a unique ID prefix for this pagination instance
     * @returns {string}
     * @private
     */
    _generateIdPrefix() {
        const source = this.paginationSelector || this.tableSelector || 'pagination';
        return source.replace(/[^a-zA-Z0-9]/g, '_');
    }

    /**
     * Generate an element ID for this instance
     * @param {string} suffix - ID suffix
     * @returns {string}
     * @private
     */
    _id(suffix) {
        return `${this._idPrefix}_${suffix}`;
    }

    /**
     * Initialize the pagination controls
     */
    init() {
        const paginationEl = document.querySelector(this.paginationSelector);
        if (!paginationEl) {
            console.warn('Pagination container not found:', this.paginationSelector);
            return;
        }

        // Determine mode: server-side if onPageChange is provided
        const isServerSide = !!this.onPageChange;

        if (!isServerSide) {
            // Client-side mode: count rows from DOM
            const table = document.querySelector(this.tableSelector);
            if (!table) {
                console.warn('Table not found:', this.tableSelector);
                return;
            }

            const tbody = table.querySelector('tbody');
            if (!tbody) {
                console.warn('Table body not found in:', this.tableSelector);
                return;
            }

            this.rows = Array.from(tbody.querySelectorAll('tr'));
            this.totalRows = this.rows.length;
        }

        // Restore page size from session storage if available
        if (this.storageKey) {
            const saved = sessionStorage.getItem(this.storageKey);
            if (saved) {
                const size = parseInt(saved, 10);
                if (this.pageSizes.includes(size)) {
                    this.pageSize = size;
                }
            }
        }

        if (!isServerSide) {
            this.totalPages = Math.max(1, Math.ceil(this.totalRows / this.pageSize));
        }

        // Build pagination UI
        this._buildUI(paginationEl, isServerSide);

        // Apply initial pagination (client-side only)
        if (!isServerSide) {
            this._applyClientPagination();
        }
    }

    /**
     * Set totals from server response and update controls
     * @param {number} totalRows - Total number of rows
     * @param {number} totalPages - Total number of pages
     */
    setTotals(totalRows, totalPages) {
        this.totalRows = totalRows;
        this.totalPages = totalPages;
        this._updateControls();
    }

    /**
     * Show or hide the pagination container
     * @param {boolean} show
     */
    setVisible(show) {
        const paginationEl = document.querySelector(this.paginationSelector);
        if (paginationEl) {
            paginationEl.style.display = show ? '' : 'none';
        }
    }

    /**
     * Build the pagination UI elements
     * @param {HTMLElement} container - Pagination container element
     * @param {boolean} isServerSide - Whether using server-side pagination
     * @private
     */
    _buildUI(container, isServerSide) {
        container.innerHTML = '';

        // Info section
        const infoDiv = document.createElement('div');
        infoDiv.className = 'pagination-info';
        infoDiv.id = this._id('page-info');
        container.appendChild(infoDiv);

        // Buttons section
        const buttonsDiv = document.createElement('div');
        buttonsDiv.className = 'pagination-buttons';

        const self = this;

        // First page button
        const firstBtn = document.createElement('button');
        firstBtn.className = 'cyber-btn is-secondary';
        firstBtn.id = this._id('first-page');
        firstBtn.type = 'button';
        firstBtn.title = 'First Page';
        firstBtn.disabled = true;
        firstBtn.innerHTML = '&laquo;';
        firstBtn.addEventListener('click', () => self.goToPage(1));
        buttonsDiv.appendChild(firstBtn);

        // Previous page button
        const prevBtn = document.createElement('button');
        prevBtn.className = 'cyber-btn is-secondary';
        prevBtn.id = this._id('prev-page');
        prevBtn.type = 'button';
        prevBtn.title = 'Previous Page';
        prevBtn.disabled = true;
        prevBtn.innerHTML = '&lsaquo;';
        prevBtn.addEventListener('click', () => self.goToPage(self.currentPage - 1));
        buttonsDiv.appendChild(prevBtn);

        // Page numbers container
        const pageNumbersDiv = document.createElement('div');
        pageNumbersDiv.className = 'pagination-page-numbers';
        pageNumbersDiv.id = this._id('page-numbers');
        buttonsDiv.appendChild(pageNumbersDiv);

        // Next page button
        const nextBtn = document.createElement('button');
        nextBtn.className = 'cyber-btn is-secondary';
        nextBtn.id = this._id('next-page');
        nextBtn.type = 'button';
        nextBtn.title = 'Next Page';
        nextBtn.disabled = self.totalPages <= 1;
        nextBtn.innerHTML = '&rsaquo;';
        nextBtn.addEventListener('click', () => self.goToPage(self.currentPage + 1));
        buttonsDiv.appendChild(nextBtn);

        // Last page button
        const lastBtn = document.createElement('button');
        lastBtn.className = 'cyber-btn is-secondary';
        lastBtn.id = this._id('last-page');
        lastBtn.type = 'button';
        lastBtn.title = 'Last Page';
        lastBtn.disabled = self.totalPages <= 1;
        lastBtn.innerHTML = '&raquo;';
        lastBtn.addEventListener('click', () => self.goToPage(self.totalPages));
        buttonsDiv.appendChild(lastBtn);

        container.appendChild(buttonsDiv);

        // Page size selector
        const sizeDiv = document.createElement('div');
        sizeDiv.className = 'pagination-size';

        const label = document.createElement('label');
        label.textContent = 'Show:';
        label.setAttribute('for', this._id('page-size'));
        sizeDiv.appendChild(label);

        const select = document.createElement('select');
        select.id = this._id('page-size');
        select.className = 'cyber-select';
        this.pageSizes.forEach(size => {
            const option = document.createElement('option');
            option.value = size;
            option.textContent = size;
            if (size === this.pageSize) option.selected = true;
            select.appendChild(option);
        });
        select.addEventListener('change', (e) => {
            self.pageSize = parseInt(e.target.value, 10);
            if (self.storageKey) {
                sessionStorage.setItem(self.storageKey, self.pageSize);
            }
            self.goToPage(1);
        });
        sizeDiv.appendChild(select);

        const span = document.createElement('span');
        span.textContent = 'per page';
        sizeDiv.appendChild(span);

        container.appendChild(sizeDiv);
    }

    /**
     * Apply client-side pagination: hide/show rows for current page
     * @private
     */
    _applyClientPagination() {
        const start = (this.currentPage - 1) * this.pageSize;
        const end = start + this.pageSize;

        this.rows.forEach((row, index) => {
            if (index >= start && index < end) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });

        this._updateControls();
    }

    /**
     * Update pagination controls (buttons, page info)
     * @private
     */
    _updateControls() {
        const start = (this.currentPage - 1) * this.pageSize + 1;
        const end = Math.min(this.currentPage * this.pageSize, this.totalRows);
        const pageInfo = document.getElementById(this._id('page-info'));
        if (pageInfo) {
            pageInfo.textContent = `Showing ${start}–${end} of ${this.totalRows}`;
        }

        const firstBtn = document.getElementById(this._id('first-page'));
        const prevBtn = document.getElementById(this._id('prev-page'));
        const nextBtn = document.getElementById(this._id('next-page'));
        const lastBtn = document.getElementById(this._id('last-page'));

        if (firstBtn) firstBtn.disabled = this.currentPage === 1;
        if (prevBtn) prevBtn.disabled = this.currentPage === 1;
        if (nextBtn) nextBtn.disabled = this.currentPage >= this.totalPages;
        if (lastBtn) lastBtn.disabled = this.currentPage >= this.totalPages;

        this._renderPageNumbers();
    }

    /**
     * Render page number buttons with ellipsis for large page counts
     * @private
     */
    _renderPageNumbers() {
        const container = document.getElementById(this._id('page-numbers'));
        if (!container) return;

        container.innerHTML = '';

        if (this.totalPages <= 1) return;

        // Determine which page numbers to show
        const pages = this._getPageNumbers();

        const self = this;
        pages.forEach(page => {
            if (page === '...') {
                const ellipsis = document.createElement('span');
                ellipsis.className = 'pagination-ellipsis';
                ellipsis.textContent = '...';
                container.appendChild(ellipsis);
            } else {
                const btn = document.createElement('button');
                btn.className = 'cyber-btn is-secondary page-number' + (page === self.currentPage ? ' active' : '');
                btn.type = 'button';
                btn.textContent = page;
                btn.addEventListener('click', () => self.goToPage(page));
                container.appendChild(btn);
            }
        });
    }

    /**
     * Calculate which page numbers to display (with ellipsis for large sets)
     * @returns {(number|string)[]}
     * @private
     */
    _getPageNumbers() {
        const pages = [];
        const dp = 2; // pages on each side of current

        if (this.totalPages <= 7) {
            // Show all pages if 7 or fewer
            for (let i = 1; i <= this.totalPages; i++) {
                pages.push(i);
            }
        } else {
            pages.push(1);

            const start = Math.max(2, this.currentPage - dp);
            const end = Math.min(this.totalPages - 1, this.currentPage + dp);

            if (start > 2) {
                pages.push('...');
            }

            for (let i = start; i <= end; i++) {
                pages.push(i);
            }

            if (end < this.totalPages - 1) {
                pages.push('...');
            }

            pages.push(this.totalPages);
        }

        return pages;
    }

    /**
     * Navigate to a specific page
     * @param {number} page - Page number to navigate to
     */
    goToPage(page) {
        if (page < 1 || page > this.totalPages) return;
        this.currentPage = page;

        if (this.onPageChange) {
            // Server-side mode: call callback
            this.onPageChange(page, this.pageSize);
        } else {
            // Client-side mode: hide/show rows
            this._applyClientPagination();
        }
    }
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
