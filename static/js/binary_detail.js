/**
 * Glyph - Binary Detail JavaScript
 * Loads and displays binary details, functions, and call graph
 */
'use strict';

(function () {
    'use strict';

    // ============================================================
    // State
    // ============================================================

    /** @type {number} */
    var binaryId = parseInt(window.location.pathname.split('/').pop(), 10);

    /** @type {string} */
    var binaryName = '';

    /** @type {number} */
    var currentPage = 1;

    /** @type {number} */
    var currentPageSize = 10;

    /** @type {number} */
    var totalFunctions = 0;

    /** @type {number} */
    var totalPages = 0;

    /** @type {Pagination|null} */
    var pagination = null;

    // ============================================================
    // DOM Ready
    // ============================================================

    document.addEventListener('DOMContentLoaded', function () {
        initTabs();
        initPagination();
        initFunctionRowDelegation();
        loadBinaryDetail();
    });

    // ============================================================
    // Function Row Navigation
    // ============================================================

    /**
     * Initialize row click delegation for the functions table.
     * Rows carry data-function-name; clicking navigates to /getFunction
     * with the binary context (binary_id) so the raw decompiled code
     * is displayed.
     */
    function initFunctionRowDelegation() {
        initTableDelegation('#functions-table-wrapper .cyber-table', ['goToBinaryFunction']);
    }

    /**
     * Navigate to the /getFunction page for a function row.
     * @param {HTMLTableRowElement} row - the clicked table row
     */
    window.goToBinaryFunction = function (row) {
        var functionName = row.getAttribute('data-function-name');
        if (!functionName) return;
        var params = new URLSearchParams({
            model_name: binaryName || String(binaryId),
            function_name: functionName,
            binary_id: String(binaryId)
        });
        window.location.href = '/getFunction?' + params.toString();
    };

    /**
     * Initialize shared pagination instance (server-side mode)
     */
    function initPagination() {
        pagination = new Pagination({
            tableSelector: '#functions-table-wrapper .cyber-table',
            paginationSelector: '#functions-pagination',
            defaultPageSize: 10,
            pageSizes: [10, 25, 50, 100],
            storageKey: 'glyph_functions_page_size',
            onPageChange: function(page, pageSize) {
                currentPage = page;
                currentPageSize = pageSize;
                loadBinaryFunctions(binaryId);
            }
        });
        pagination.init();
    }

    // ============================================================
    // Tab Navigation
    // ============================================================

    /**
     * Initialize tab switching
     */
    function initTabs() {
        var tabButtons = document.querySelectorAll('.tab-btn');
        if (!tabButtons || tabButtons.length === 0) return;

        tabButtons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var targetTab = btn.getAttribute('data-tab');
                switchTab(targetTab);
            });

            // Keyboard support
            btn.addEventListener('keydown', function (e) {
                var tabList = Array.prototype.slice.call(tabButtons);
                var currentIndex = tabList.indexOf(btn);
                var newIndex = currentIndex;

                if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                    e.preventDefault();
                    newIndex = (currentIndex + 1) % tabList.length;
                } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                    e.preventDefault();
                    newIndex = (currentIndex - 1 + tabList.length) % tabList.length;
                } else if (e.key === 'Home') {
                    e.preventDefault();
                    newIndex = 0;
                } else if (e.key === 'End') {
                    e.preventDefault();
                    newIndex = tabList.length - 1;
                }

                if (newIndex !== currentIndex) {
                    tabList[newIndex].focus();
                    tabList[newIndex].click();
                }
            });
        });
    }

    /**
     * Switch to the specified tab
     * @param {string} tabId
     */
    function switchTab(tabId) {
        var tabButtons = document.querySelectorAll('.tab-btn');
        var tabPanels = document.querySelectorAll('.tab-panel');

        tabButtons.forEach(function (btn) {
            var isActive = btn.getAttribute('data-tab') === tabId;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });

        tabPanels.forEach(function (panel) {
            var panelId = 'panel-' + tabId;
            var isActive = panel.id === panelId;
            panel.classList.toggle('active', isActive);
            panel.setAttribute('aria-hidden', isActive ? 'false' : 'true');
        });
    }

    // Expose switchTab globally for testing
    window.switchTab = switchTab;

    // ============================================================
    // Load Binary Detail
    // ============================================================

    /**
     * Load and display binary details
     */
    async function loadBinaryDetail() {
        var loadingEl = document.getElementById('detail-loading');
        var errorEl = document.getElementById('detail-error');
        var contentEl = document.getElementById('detail-content');

        if (loadingEl) loadingEl.style.display = 'flex';
        if (errorEl) errorEl.classList.add('is-hidden');
        if (contentEl) contentEl.classList.add('is-hidden');

        try {
            // Load binary metadata
            var detailResponse = await authenticatedFetch('/api/v1/binaries/binaries/' + binaryId, {
                headers: { 'Accept': 'application/json' }
            });

            var detailData = await detailResponse.json();

            if (!detailResponse.ok) {
                throw new Error(detailData.detail || 'Failed to load binary details');
            }

            var binary = detailData.data;
            binaryName = binary.name || '';

            if (loadingEl) loadingEl.style.display = 'none';

            // Show main content card
            if (contentEl) contentEl.classList.remove('is-hidden');

            // Update subtitle
            var subtitle = document.getElementById('binary-subtitle');
            if (subtitle) {
                subtitle.textContent = binary.name + ' (ID: ' + binary.id + ')';
            }

            // Update the breadcrumb binary-name crumb
            var breadcrumbName = document.getElementById('breadcrumb-binary-name');
            if (breadcrumbName) {
                breadcrumbName.textContent = binary.name;
            }

            // Display binary info
            displayBinaryInfo(binary);

            // Populate the per-binary action row
            renderBinaryActions(binary);

            // Load functions
            await loadBinaryFunctions(binaryId);

        } catch (error) {
            console.error('Load binary detail error:', error);
            if (loadingEl) loadingEl.style.display = 'none';
            if (errorEl) {
                errorEl.classList.remove('is-hidden');
                var msgEl = document.getElementById('error-message');
                if (msgEl) msgEl.textContent = error.message;
            }
        }
    }

    /**
     * Display binary metadata
     * @param {Object} binary
     */
    function displayBinaryInfo(binary) {
        var grid = document.getElementById('info-grid');

        if (!grid) return;

        var date = formatDate(binary.created_at);
        var size = formatFileSize(binary.file_size);

        grid.innerHTML =
            '<div class="summary-item">' +
                '<span class="summary-label">Name</span>' +
                '<span class="summary-value">' + escapeHtml(binary.name) + '</span>' +
            '</div>' +
            '<div class="summary-item">' +
                '<span class="summary-label">ID</span>' +
                '<span class="summary-value">' + binary.id + '</span>' +
            '</div>' +
            '<div class="summary-item">' +
                '<span class="summary-label">File Size</span>' +
                '<span class="summary-value">' + size + '</span>' +
            '</div>' +
            '<div class="summary-item">' +
                '<span class="summary-label">MIME Type</span>' +
                '<span class="summary-value">' + escapeHtml(binary.mime_type) + '</span>' +
            '</div>' +
            '<div class="summary-item">' +
                '<span class="summary-label">Functions</span>' +
                '<span class="summary-value">' + binary.function_count + '</span>' +
            '</div>' +
            '<div class="summary-item">' +
                '<span class="summary-label">Uploaded</span>' +
                '<span class="summary-value">' + date + '</span>' +
            '</div>';
    }

    /**
     * Load and display binary functions with pagination
     * @param {number} id
     */
    async function loadBinaryFunctions(id) {
        var functionsEmpty = document.getElementById('functions-empty');
        var functionsTable = document.getElementById('functions-table-wrapper');
        var tbody = document.getElementById('functions-tbody');

        // Show skeleton rows in the functions table while the fetch is in
        // flight. The rows mirror the real columns (Function Name/Entrypoint)
        // so the layout does not shift when data arrives.
        if (functionsEmpty) functionsEmpty.classList.add('is-hidden');
        if (functionsTable) functionsTable.classList.remove('is-hidden');
        renderFunctionSkeletonRows(5);

        try {
            var url = '/api/v1/binaries/functions/' + id + '?page=' + currentPage + '&page_size=' + currentPageSize;
            var response = await authenticatedFetch(url, {
                headers: { 'Accept': 'application/json' }
            });

            var data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to load functions');
            }

            var paginated = data.data ? data.data : {};
            var functions = paginated.items || [];
            totalFunctions = paginated.total || 0;
            totalPages = paginated.total_pages || 0;

            if (!functions || functions.length === 0) {
                if (functionsEmpty) functionsEmpty.classList.remove('is-hidden');
                if (functionsTable) functionsTable.classList.add('is-hidden');
                if (pagination) pagination.setVisible(false);
                return;
            }

            if (tbody) {
                tbody.innerHTML = '';
                functions.forEach(function (fn) {
                    var row = document.createElement('tr');
                    row.classList.add('hover-row', 'clickable-row');
                    row.setAttribute('data-function-name', fn.function_name);
                    var entrypoint = fn.entrypoint ? '0x' + fn.entrypoint : 'N/A';
                    row.innerHTML =
                        '<td data-label="Function Name"><span class="binary-name">' + escapeHtml(fn.function_name) + '</span></td>' +
                        '<td data-label="Entrypoint">' + entrypoint + '</td>';
                    tbody.appendChild(row);
                });
            }

            if (functionsEmpty) functionsEmpty.classList.add('is-hidden');
            if (functionsTable) functionsTable.classList.remove('is-hidden');

            // Update shared pagination controls
            if (pagination) {
                pagination.setTotals(totalFunctions, totalPages);
                pagination.setVisible(true);
            }

        } catch (error) {
            console.error('Load functions error:', error);
            if (functionsEmpty) {
                functionsEmpty.classList.remove('is-hidden');
                var para = document.createElement('p');
                para.textContent = 'Error loading functions: ' + error.message;
                functionsEmpty.innerHTML = '';
                functionsEmpty.appendChild(para);
            }
            if (functionsTable) functionsTable.classList.add('is-hidden');
            if (pagination) pagination.setVisible(false);
        }
    }

    /**
     * Render placeholder skeleton rows in the functions table while a fetch
     * is in flight. The rows mirror the real columns (Function Name/
     * Entrypoint) so the layout does not shift when data arrives.
     * @param {number} count - Number of skeleton rows to render.
     */
    function renderFunctionSkeletonRows(count) {
        var tbody = document.getElementById('functions-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        for (var i = 0; i < count; i++) {
            var row = document.createElement('tr');
            row.className = 'skeleton-row';
            row.setAttribute('aria-hidden', 'true');
            row.innerHTML =
                '<td data-label="Function Name"><div class="skeleton skeleton-cell"></div></td>' +
                '<td data-label="Entrypoint"><div class="skeleton skeleton-cell is-narrow"></div></td>';
            tbody.appendChild(row);
        }
    }

    // ============================================================
    // Per-Binary Action Row
    // ============================================================

    /**
     * Populate the action row from the canonical BinaryActions list
     * (single source of truth shared with the library task modal).
     * @param {Object} binary
     */
    function renderBinaryActions(binary) {
        var actionsEl = document.getElementById('binary-actions');
        var listEl = document.getElementById('binary-actions-list');
        if (!actionsEl || !listEl || typeof window.BinaryActions === 'undefined') return;

        listEl.innerHTML = '';
        window.BinaryActions.actions.forEach(function (action) {
            var href = window.BinaryActions.buildHref(action.id, binary.id, binary.name);
            if (!href) return;
            var link = document.createElement('a');
            link.href = href;
            link.className = 'task-option';
            link.setAttribute('data-task-type', action.id);
            link.innerHTML =
                '<span class="task-option-name">' + escapeHtml(action.label) + '</span>' +
                '<span class="task-option-desc">' + escapeHtml(action.description) + '</span>';
            listEl.appendChild(link);
        });

        actionsEl.classList.remove('is-hidden');
    }

    // ============================================================
    // Utility Functions
    // ============================================================

    /**
     * Format file size
     * @param {number} bytes
     * @returns {string}
     */
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        var k = 1024;
        var sizes = ['B', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
    }

    /**
     * Format date string
     * @param {string} dateStr
     * @returns {string}
     */
    function formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        try {
            var date = new Date(dateStr + 'Z');
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (e) {
            return dateStr;
        }
    }

    /**
     * Escape HTML entities
     * @param {string} str
     * @returns {string}
     */
    function escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

})();
