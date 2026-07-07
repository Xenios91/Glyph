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
        loadBinaryDetail();
    });

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
        if (errorEl) errorEl.style.display = 'none';
        if (contentEl) contentEl.style.display = 'none';

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

            if (loadingEl) loadingEl.style.display = 'none';

            // Show main content card
            if (contentEl) contentEl.style.display = 'block';

            // Update subtitle
            var subtitle = document.getElementById('binary-subtitle');
            if (subtitle) {
                subtitle.textContent = binary.name + ' (ID: ' + binary.id + ')';
            }

            // Display binary info
            displayBinaryInfo(binary);

            // Load functions
            await loadBinaryFunctions(binaryId);

        } catch (error) {
            console.error('Load binary detail error:', error);
            if (loadingEl) loadingEl.style.display = 'none';
            if (errorEl) {
                errorEl.style.display = 'block';
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
                if (functionsEmpty) functionsEmpty.style.display = 'block';
                if (functionsTable) functionsTable.style.display = 'none';
                if (pagination) pagination.setVisible(false);
                return;
            }

            if (tbody) {
                tbody.innerHTML = '';
                functions.forEach(function (fn) {
                    var row = document.createElement('tr');
                    row.classList.add('hover-row');
                    var entrypoint = fn.entrypoint ? '0x' + fn.entrypoint : 'N/A';
                    var lineCount = fn.raw_code_lines || 0;
                    row.innerHTML =
                        '<td><span class="binary-name">' + escapeHtml(fn.function_name) + '</span></td>' +
                        '<td>' + entrypoint + '</td>' +
                        '<td><span class="function-badge">' + lineCount + '</span></td>';
                    tbody.appendChild(row);
                });
            }

            if (functionsEmpty) functionsEmpty.style.display = 'none';
            if (functionsTable) functionsTable.style.display = 'block';

            // Update shared pagination controls
            if (pagination) {
                pagination.setTotals(totalFunctions, totalPages);
                pagination.setVisible(true);
            }

        } catch (error) {
            console.error('Load functions error:', error);
            if (functionsEmpty) {
                functionsEmpty.style.display = 'block';
                var para = document.createElement('p');
                para.textContent = 'Error loading functions: ' + error.message;
                functionsEmpty.innerHTML = '';
                functionsEmpty.appendChild(para);
            }
            if (functionsTable) functionsTable.style.display = 'none';
            if (pagination) pagination.setVisible(false);
        }
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
