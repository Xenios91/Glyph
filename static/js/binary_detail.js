/**
 * Glyph - Binary Detail JavaScript
 * Loads and displays binary details and functions
 */
'use strict';

(function () {
    'use strict';

    // ============================================================
    // State
    // ============================================================

    /** @type {number} */
    var binaryId = parseInt(window.location.pathname.split('/').pop(), 10);

    // ============================================================
    // DOM Ready
    // ============================================================

    document.addEventListener('DOMContentLoaded', function () {
        loadBinaryDetail();
    });

    // ============================================================
    // Load Binary Detail
    // ============================================================

    /**
     * Load and display binary details
     */
    async function loadBinaryDetail() {
        var loadingEl = document.getElementById('detail-loading');
        var errorEl = document.getElementById('detail-error');
        var infoEl = document.getElementById('binary-info');
        var functionsContainer = document.getElementById('functions-container');

        if (loadingEl) loadingEl.style.display = 'flex';
        if (errorEl) errorEl.style.display = 'none';
        if (infoEl) infoEl.style.display = 'none';
        if (functionsContainer) functionsContainer.style.display = 'none';

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
        var infoEl = document.getElementById('binary-info');
        var grid = document.getElementById('info-grid');

        if (!infoEl || !grid) return;

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

        infoEl.style.display = 'block';
    }

    /**
     * Load and display binary functions
     * @param {number} binaryId
     */
    async function loadBinaryFunctions(binaryId) {
        var functionsContainer = document.getElementById('functions-container');
        var functionsEmpty = document.getElementById('functions-empty');
        var functionsTable = document.getElementById('functions-table-wrapper');
        var tbody = document.getElementById('functions-tbody');

        if (!functionsContainer) return;
        functionsContainer.style.display = 'block';

        try {
            var response = await authenticatedFetch('/api/v1/binaries/functions/' + binaryId, {
                headers: { 'Accept': 'application/json' }
            });

            var data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to load functions');
            }

            var functions = data.data ? data.data.functions : [];

            if (!functions || functions.length === 0) {
                if (functionsEmpty) functionsEmpty.style.display = 'block';
                if (functionsTable) functionsTable.style.display = 'none';
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

        } catch (error) {
            console.error('Load functions error:', error);
            if (functionsEmpty) {
                functionsEmpty.style.display = 'block';
                functionsEmpty.innerHTML = '<p>Error loading functions: ' + error.message + '</p>';
            }
            if (functionsTable) functionsTable.style.display = 'none';
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
