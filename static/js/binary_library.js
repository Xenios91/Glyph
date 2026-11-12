/**
 * Glyph - Binary Library JavaScript
 * Handles binary listing, uploading, and task execution
 */
'use strict';

(function () {
    'use strict';

    // ============================================================
    // State
    // ============================================================

    /** @type {boolean} */
    let isUploading = false;

    /** @type {XMLHttpRequest|null} Active upload request (aborted by CANCEL). */
    let activeUpload = null;

    /** @type {number} Current page (server-side pagination). */
    let currentPage = 1;

    /** @type {number} Current page size (server-side pagination). */
    let pageSize = 50;

    /** @type {Pagination|null} Server-side pagination instance. */
    let pagination = null;

    /** @type {number} Configured maximum upload size in MB. */
    let maxFileSizeMB = 512;

    /**
     * True while the in-flight upload transfer has not completed. Drives the
     * beforeunload guard so users are warned before leaving mid-transfer
     * (ported from the former standalone upload page).
     * @type {boolean}
     */
    let isUploadInProgress = false;

    /** @type {string|null} StatusBar client ID for the active upload. */
    let statusBarClientId = null;

    /** Page-size options, capped at the API maximum (200). */
    const PAGE_SIZES = [10, 25, 50, 100, 200];
    const PAGE_SIZE_STORAGE_KEY = 'glyph_binaries_page_size';

    /**
     * Determine the initial page size, honoring a previously saved choice so
     * the first fetch matches the page size the Pagination control will show.
     * @returns {number}
     */
    function getInitialPageSize() {
        try {
            var saved = sessionStorage.getItem(PAGE_SIZE_STORAGE_KEY);
            if (saved) {
                var size = parseInt(saved, 10);
                if (PAGE_SIZES.indexOf(size) !== -1) return size;
            }
        } catch (e) { /* ignore storage errors */ }
        return 50;
    }

    // ============================================================
    // DOM Ready
    // ============================================================

    document.addEventListener('DOMContentLoaded', function () {
        pageSize = getInitialPageSize();
        initUploadConfig();
        initDragAndDrop();
        initFileInput();
        initEventDelegation();
        initTaskModalOptions();
        loadBinaries();
    });

    // ============================================================
    // Event Delegation for Dynamic Elements
    // ============================================================

    /**
     * Initialize event delegation for dynamically created table buttons
     */
    function initEventDelegation() {
        var tbody = document.getElementById('binaries-tbody');
        if (!tbody) return;

        tbody.addEventListener('click', function (e) {
            var target = e.target;

            // Run Task button - show task selection modal
            if (target.classList.contains('btn-run-task')) {
                e.preventDefault();
                e.stopPropagation();
                var binaryId = target.getAttribute('data-binary-id');
                var binaryName = target.getAttribute('data-binary-name');
                showTaskSelectionModal(binaryId, binaryName);
                return;
            }

            // Delete binary button
            if (target.classList.contains('btn-delete-binary')) {
                e.preventDefault();
                e.stopPropagation();
                var id = target.getAttribute('data-binary-id');
                var row = target.closest('tr');
                var nameEl = row ? row.querySelector('.binary-name') : null;
                var binaryName = nameEl ? nameEl.textContent : '';
                deleteBinary(id, binaryName);
                return;
            }
        });

        // Handle row click to navigate to details
        tbody.addEventListener('click', function (e) {
            var row = e.target.closest('tr');
            if (!row) return;

            // Don't navigate if clicking a button or link inside the row
            var target = e.target;
            if (target.classList.contains('action-btn') || target.closest('.action-btn') || target.closest('.action-group')) {
                return;
            }

            var binaryId = row.getAttribute('data-binary-id');
            if (binaryId) {
                window.location.href = '/binary/' + binaryId;
            }
        });
    }

    // ============================================================
    // Task Selection Modal
    // ============================================================

    /**
     * Render the task modal options from the canonical BinaryActions list
     * (static/js/binary_actions.js) so the modal stays a thin wrapper over
     * the single source of truth.
     */
    function initTaskModalOptions() {
        var container = document.getElementById('task-modal-options');
        if (!container || typeof window.BinaryActions === 'undefined') return;

        container.innerHTML = '';
        window.BinaryActions.actions.forEach(function (action) {
            var link = document.createElement('a');
            link.href = '#';
            link.className = 'task-option';
            link.setAttribute('data-task-type', action.id);

            var name = document.createElement('span');
            name.className = 'task-option-name';
            name.textContent = action.label;

            var desc = document.createElement('span');
            desc.className = 'task-option-desc';
            desc.textContent = action.description;

            link.appendChild(name);
            link.appendChild(desc);
            container.appendChild(link);
        });
    }

    /**
     * Show the task selection modal
     * @param {string} binaryId
     * @param {string} binaryName
     */
    function showTaskSelectionModal(binaryId, binaryName) {
        var overlay = document.getElementById('task-modal-overlay');
        if (!overlay) return;

        // Update each link with the deep link for this binary, derived from
        // the canonical BinaryActions list (single source of truth).
        var links = overlay.querySelectorAll('a.task-option');
        links.forEach(function (link) {
            var taskType = link.getAttribute('data-task-type');
            var href = window.BinaryActions
                ? window.BinaryActions.buildHref(taskType, binaryId, binaryName)
                : null;
            if (href) {
                link.href = href;
            }
        });

        overlay.classList.add('is-visible');
    }

    /**
     * Hide the task selection modal
     */
    function hideTaskSelectionModal() {
        var overlay = document.getElementById('task-modal-overlay');
        if (overlay) {
            overlay.classList.remove('is-visible');
        }
    }

    // Expose hide function globally
    window.hideTaskSelectionModal = hideTaskSelectionModal;

    // Cancel button handler
    var cancelBtn = document.getElementById('task-modal-cancel');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            hideTaskSelectionModal();
        });
    }

    // Close modal when clicking outside the modal content
    document.addEventListener('click', function (e) {
        var overlay = document.getElementById('task-modal-overlay');
        if (!overlay) return;
        if (e.target === overlay) {
            hideTaskSelectionModal();
        }
    });

    // Close modal on Escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            var overlay = document.getElementById('task-modal-overlay');
            if (overlay && overlay.classList.contains('is-visible')) {
                hideTaskSelectionModal();
            }
        }
    });

    // ============================================================
    // Binary Actions
    // ============================================================

    /**
     * Delete a binary
     * @param {string} binaryId
     * @param {string} [binaryName]
     */
    async function deleteBinary(binaryId, binaryName) {
        var nameText = binaryName ? ' "' + binaryName + '"' : '';
        var confirmed = await showConfirm({
            title: 'Delete Binary',
            message: 'Are you sure you want to delete binary' + nameText + '?',
            confirmLabel: 'Delete',
            cancelLabel: 'Cancel'
        });
        if (!confirmed) return;

        try {
            var response = await authenticatedFetch('/api/v1/binaries/binaries/' + binaryId, {
                method: 'DELETE'
            });

            if (!response.ok) {
                var data = await response.json();
                throw new Error(data.detail || 'Failed to delete binary');
            }

            Toast.success('Binary deleted successfully');
            loadBinaries();
        } catch (error) {
            console.error('Delete binary error:', error);
            Toast.error(error.message || 'Failed to delete binary');
        }
    }

    // ============================================================
    // Drag and Drop
    // ============================================================

    /**
     * Initialize drag and drop handlers
     */
    function initDragAndDrop() {
        var dropZone = document.getElementById('drop-zone');
        if (!dropZone) return;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(function (type) {
            dropZone.addEventListener(type, function (e) {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        dropZone.addEventListener('dragenter', function () {
            dropZone.classList.add('is-dragover');
        });

        dropZone.addEventListener('dragover', function () {
            dropZone.classList.add('is-dragover');
        });

        dropZone.addEventListener('dragleave', function (e) {
            if (!dropZone.contains(e.relatedTarget)) {
                dropZone.classList.remove('is-dragover');
            }
        });

        dropZone.addEventListener('drop', function (e) {
            dropZone.classList.remove('is-dragover');
            var files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelect(files[0]);
            }
        });
    }

    /**
     * Initialize file input handler
     */
    function initFileInput() {
        var input = document.getElementById('upload-binary');
        if (!input) return;

        input.addEventListener('change', function () {
            if (input.files && input.files.length > 0) {
                handleFileSelect(input.files[0]);
            }
        });
    }

    // ============================================================
    // File Upload
    // ============================================================

    /**
     * Handle a selected file: validate it against the configured limits,
     * then trigger the upload.
     * @param {File} file
     */
    function handleFileSelect(file) {
        if (isUploading) return;

        var error = validateFile(file);
        if (error) {
            markUploadField(error);
            return;
        }
        clearUploadFieldError();

        var nameInput = document.getElementById('binary-name');
        var binaryName = nameInput ? nameInput.value.trim() : '';

        // Auto-fill name from filename if empty
        if (!binaryName) {
            binaryName = file.name.replace(/\.[^/.]+$/, '');
            if (nameInput) nameInput.value = binaryName;
        }

        uploadBinary(file, binaryName);
    }

    /**
     * Validate a file against the configured size limit before any upload
     * starts. Binaries are not MIME-typed, so size is the meaningful check;
     * an empty selection is rejected as well.
     * @param {File} file
     * @returns {string|null} An error message, or null if the file is valid.
     */
    function validateFile(file) {
        if (!file || file.size === 0) {
            return 'Selected file is empty.';
        }
        var maxBytes = maxFileSizeMB * 1024 * 1024;
        if (file.size > maxBytes) {
            return 'File is ' + formatFileSize(file.size) +
                ', which exceeds the ' + maxFileSizeMB + ' MB upload limit.';
        }
        return null;
    }

    /**
     * Upload a binary with real progress reporting.
     *
     * The transfer phase (0-100% of the file upload) is driven by
     * XMLHttpRequest.upload.onprogress. Once the transfer completes, the bar
     * switches to an indeterminate "Processing..." state while the server
     * decompiles and saves the binary; 100% is only shown on a confirmed
     * success response. CANCEL aborts the in-flight request.
     * @param {File} file
     * @param {string} name
     */
    function uploadBinary(file, name) {
        if (isUploading) return;

        isUploading = true;
        showUploadProgress(true);
        setProgressIndeterminate(false);
        setProgressWidth(0);
        setProgressText('Uploading ' + file.name + '... 0%');
        hideUploadError();
        clearUploadFieldError();

        // Warn the user before leaving while the file transfer is in flight;
        // the guard lifts once the transfer completes (see progress handler).
        setUploadGuard(true);

        // Register with the global status bar so the upload is tracked
        // alongside model/prediction tasks (mirrors create_model.js).
        statusBarClientId = null;
        if (typeof StatusBar !== 'undefined') {
            statusBarClientId = StatusBar.registerUpload(file.name);
        }

        var formData = new FormData();
        formData.append('name', name);
        formData.append('binary_file', file);

        var xhr = new XMLHttpRequest();
        activeUpload = xhr;

        xhr.open('POST', '/api/v1/binaries/uploadBinary', true);
        // Same-origin request: the auth cookie is sent automatically, matching
        // how authenticatedFetch() handles FormData uploads (it relies on the
        // cookie rather than an Authorization header for multipart bodies).

        xhr.upload.addEventListener('progress', function (e) {
            if (!e.lengthComputable) return;
            var pct = Math.round((e.loaded / e.total) * 100);
            setProgressWidth(pct);
            setProgressText('Uploading ' + file.name + '... ' + pct + '%');
            if (statusBarClientId && typeof StatusBar !== 'undefined') {
                StatusBar.updateUploadProgress(statusBarClientId, pct);
            }
            // The file is fully sent once the transfer hits 100%; leaving at
            // that point no longer loses data, so the unload guard can lift.
            if (pct >= 100) {
                setUploadGuard(false);
            }
        });

        xhr.addEventListener('load', function () {
            var status = xhr.status;
            var data = null;
            try {
                data = JSON.parse(xhr.responseText);
            } catch (parseError) {
                data = null;
            }

            setUploadGuard(false);

            if (status >= 200 && status < 300 && data) {
                // Confirmed success: only now show 100%.
                setProgressIndeterminate(false);
                setProgressWidth(100);
                setProgressText('Upload complete!');
                // Transition the status bar entry to the server-side task so
                // processing is tracked and polled like other tasks.
                var taskUuid = data.data && data.data.uuid;
                if (statusBarClientId && taskUuid && typeof StatusBar !== 'undefined') {
                    StatusBar.uploadComplete(statusBarClientId, taskUuid);
                }
                statusBarClientId = null;
                setTimeout(function () {
                    showUploadProgress(false);
                    isUploading = false;
                    activeUpload = null;
                    Toast.success('Binary "' + name + '" uploaded successfully');
                    // New uploads are listed first (created_at desc), so
                    // refresh from page 1.
                    currentPage = 1;
                    loadBinaries();
                    resetUploadForm();
                }, 800);
            } else {
                var message = (data && data.detail) ? data.detail : ('Upload failed (HTTP ' + status + ')');
                isUploading = false;
                activeUpload = null;
                showUploadProgress(false);
                removeStatusBarEntry();
                showUploadError(message);
            }
        });

        xhr.addEventListener('error', function () {
            isUploading = false;
            activeUpload = null;
            showUploadProgress(false);
            setUploadGuard(false);
            removeStatusBarEntry();
            showUploadError('Network error: could not reach the server.');
        });

        xhr.addEventListener('abort', function () {
            isUploading = false;
            activeUpload = null;
            showUploadProgress(false);
            setUploadGuard(false);
            removeStatusBarEntry();
            showUploadError('Upload cancelled.');
        });

        // Once the file has been fully sent (upload complete) but the response
        // has not yet arrived, the server is processing (decompiling + saving) —
        // show an indeterminate bar instead of a false percentage.
        xhr.upload.addEventListener('load', function () {
            setProgressIndeterminate(true);
            setProgressText('Processing...');
        });

        xhr.send(formData);
    }

    /**
     * Abort the active upload request (CANCEL affordance).
     */
    function cancelUpload() {
        if (activeUpload && activeUpload.readyState !== 4) {
            activeUpload.abort();
        }
    }

    // ============================================================
    // Load Binaries
    // ============================================================

    /**
     * Load and display a page of binaries using server-side pagination.
     *
     * The `page` and `page_size` query params are sent to the API and the
     * server's total drives the pagination controls, so users with more
     * binaries than one page can always reach every item.
     */
    async function loadBinaries() {
        var emptyEl = document.getElementById('binaries-empty');
        var tableWrapper = document.getElementById('binaries-table-wrapper');
        var paginationEl = document.getElementById('binaries-pagination');
        var tbody = document.getElementById('binaries-tbody');

        // Show skeleton rows in the table while the fetch is in flight.
        if (emptyEl) emptyEl.classList.add('is-hidden');
        if (tableWrapper) tableWrapper.classList.remove('is-hidden');
        if (paginationEl) paginationEl.classList.add('is-hidden');
        renderSkeletonRows(5);

        try {
            var queryParams = 'page=' + encodeURIComponent(currentPage) +
                '&page_size=' + encodeURIComponent(pageSize);
            var response = await authenticatedFetch('/api/v1/binaries/list?' + queryParams, {
                headers: { 'Accept': 'application/json' }
            });

            var data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to load binaries');
            }

            var payload = data.data || {};
            var binaries = payload.items || [];
            var total = payload.total || 0;
            var totalPages = payload.total_pages || 0;

            if (tbody) {
                tbody.innerHTML = '';
                binaries.forEach(function (binary) {
                    var row = document.createElement('tr');
                    row.setAttribute('data-binary-id', binary.id);
                    row.classList.add('hover-row');
                    row.style.cursor = 'pointer';
                    row.innerHTML = renderBinaryRow(binary);
                    tbody.appendChild(row);
                });
            }

            if (total === 0) {
                if (tableWrapper) tableWrapper.classList.add('is-hidden');
                if (emptyEl) emptyEl.classList.remove('is-hidden');
                return;
            }

            if (tableWrapper) tableWrapper.classList.remove('is-hidden');

            // Server-side pagination: the server total drives the controls.
            if (paginationEl) {
                paginationEl.classList.remove('is-hidden');
                if (!pagination) {
                    pagination = new Pagination({
                        paginationSelector: '#binaries-pagination',
                        defaultPageSize: pageSize,
                        pageSizes: PAGE_SIZES,
                        storageKey: PAGE_SIZE_STORAGE_KEY,
                        totalRows: total,
                        totalPages: totalPages,
                        onPageChange: function (page, size) {
                            currentPage = page;
                            pageSize = size;
                            loadBinaries();
                        }
                    });
                    pagination.init();
                }
                // Keep the control's page size in sync with what we requested.
                pagination.pageSize = pageSize;
                pagination.currentPage = currentPage;
                pagination.setTotals(total, totalPages);
            }

        } catch (error) {
            console.error('Load binaries error:', error);
            if (tbody) tbody.innerHTML = '';
            if (tableWrapper) tableWrapper.classList.add('is-hidden');
            if (paginationEl) paginationEl.classList.add('is-hidden');
            if (emptyEl) {
                emptyEl.classList.remove('is-hidden');
                var para = document.createElement('p');
                para.textContent = 'Error loading binaries: ' + error.message;
                emptyEl.innerHTML = '';
                emptyEl.appendChild(para);
            }
        }
    }

    /**
     * Render placeholder skeleton rows in the binaries table while a fetch
     * is in flight. The rows mirror the real columns (Name/Size/Functions/
     * Uploaded/Actions) so the layout does not shift when data arrives.
     * @param {number} count - Number of skeleton rows to render.
     */
    function renderSkeletonRows(count) {
        var tbody = document.getElementById('binaries-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        for (var i = 0; i < count; i++) {
            var row = document.createElement('tr');
            row.className = 'skeleton-row';
            row.setAttribute('aria-hidden', 'true');
            row.innerHTML =
                '<td data-label="Name"><div class="skeleton skeleton-cell"></div></td>' +
                '<td data-label="Size"><div class="skeleton skeleton-cell is-narrow"></div></td>' +
                '<td data-label="Functions"><div class="skeleton skeleton-cell is-narrow"></div></td>' +
                '<td data-label="Uploaded"><div class="skeleton skeleton-cell"></div></td>' +
                '<td data-label="Actions"><div class="skeleton is-button"></div></td>';
            tbody.appendChild(row);
        }
    }

    /**
     * Render a single binary row
     * @param {Object} binary
     * @returns {string}
     */
    function renderBinaryRow(binary) {
        var size = formatFileSize(binary.file_size);
        var date = formatDate(binary.created_at);
        var funcCount = binary.function_count || 0;

        return '<td data-label="Name"><span class="binary-name">' + escapeHtml(binary.name) + '</span></td>' +
            '<td data-label="Size">' + size + '</td>' +
            '<td data-label="Functions"><span class="function-badge">' + funcCount + '</span></td>' +
            '<td data-label="Uploaded"><span class="date-cell">' + date + '</span></td>' +
            '<td data-label="Actions">' +
                '<div class="action-group">' +
                    '<button class="action-btn is-success btn-run-task" data-binary-id="' + binary.id + '" data-binary-name="' + escapeHtml(binary.name) + '" title="Run analysis task">RUN TASK</button>' +
                    '<a href="/binary/' + binary.id + '" class="action-btn btn-binary-details" data-binary-id="' + binary.id + '" title="View details">DETAILS</a>' +
                    '<button class="action-btn is-danger btn-delete-binary" data-binary-id="' + binary.id + '" title="Delete binary">DELETE</button>' +
                '</div>' +
            '</td>';
    }

    // ============================================================
    // Task Execution
    // ============================================================

    /**
     * Redirect to task execution page for a binary
     * @param {number} binaryId
     * @param {string} binaryName
     */
    window.runTaskOnBinary = function (binaryId, binaryName) {
        window.location.href = '/run-task?binary_id=' + binaryId + '&binary_name=' + encodeURIComponent(binaryName);
    };

    // ============================================================
    // UI Helpers
    // ============================================================

    /**
     * Show/hide upload progress
     * @param {boolean} show
     */
    function showUploadProgress(show) {
        var progress = document.getElementById('upload-progress');
        var dropZone = document.getElementById('drop-zone');
        if (progress) progress.classList.toggle('is-hidden', !show);
        if (dropZone) {
            dropZone.style.pointerEvents = show ? 'none' : '';
            dropZone.style.opacity = show ? '0.5' : '';
        }
    }

    /**
     * Initialize upload configuration: read the configured max file size from
     * the page (rendered server-side from settings) and wire up the CANCEL
     * affordance.
     */
    function initUploadConfig() {
        var hint = document.getElementById('upload-limit-hint');
        if (hint) {
            var mb = parseInt(hint.getAttribute('data-max-mb'), 10);
            if (!isNaN(mb) && mb > 0) {
                maxFileSizeMB = mb;
            }
        }

        var cancelBtn = document.getElementById('upload-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', function (e) {
                e.preventDefault();
                cancelUpload();
            });
        }
    }

    /**
     * Set progress text
     * @param {string} text
     */
    function setProgressText(text) {
        var el = document.getElementById('progress-text');
        if (el) el.textContent = text;
    }

    /**
     * Set progress bar width
     * @param {number} width - percentage 0-100
     */
    function setProgressWidth(width) {
        var el = document.getElementById('progress-fill');
        if (el) el.style.width = width + '%';
    }

    /**
     * Toggle the indeterminate (animated) state of the progress bar, used
     * while the server processes the upload after the transfer completes.
     * @param {boolean} on
     */
    function setProgressIndeterminate(on) {
        var el = document.getElementById('progress-fill');
        if (el) el.classList.toggle('is-indeterminate', !!on);
    }

    /**
     * Show upload error
     * @param {string} message
     */
    function showUploadError(message) {
        var el = document.getElementById('upload-error');
        if (el) {
            el.textContent = message;
            el.classList.remove('is-hidden');
        }
    }

    /**
     * Hide upload error
     */
    function hideUploadError() {
        var el = document.getElementById('upload-error');
        if (el) {
            el.textContent = '';
            el.classList.add('is-hidden');
        }
    }

    /**
     * Mark the upload field with an inline validation error: red border on
     * the drop zone, aria-invalid on the file input, and the message in the
     * inline error region (ported from the standalone upload page's
     * markField() pattern).
     * @param {string} message
     */
    function markUploadField(message) {
        var dropZone = document.getElementById('drop-zone');
        var fileInput = document.getElementById('upload-binary');
        if (dropZone) dropZone.classList.add('is-error');
        if (fileInput) fileInput.setAttribute('aria-invalid', 'true');
        showUploadError(message);
    }

    /**
     * Clear the inline field-error state from the drop zone and file input.
     */
    function clearUploadFieldError() {
        var dropZone = document.getElementById('drop-zone');
        var fileInput = document.getElementById('upload-binary');
        if (dropZone) dropZone.classList.remove('is-error');
        if (fileInput) fileInput.removeAttribute('aria-invalid');
        hideUploadError();
    }

    /**
     * Warn the user before leaving the page while a file transfer is in
     * flight (ported from the standalone upload page).
     * @param {BeforeUnloadEvent} e
     */
    function handleBeforeUnload(e) {
        if (isUploadInProgress) {
            e.preventDefault();
            e.returnValue = 'Upload is in progress. Are you sure you want to leave?';
            return e.returnValue;
        }
    }

    /**
     * Arm or disarm the beforeunload guard. Armed when the upload starts;
     * disarmed once the transfer completes or the request reaches any
     * terminal state.
     * @param {boolean} on
     */
    function setUploadGuard(on) {
        if (on) {
            isUploadInProgress = true;
            window.addEventListener('beforeunload', handleBeforeUnload);
        } else {
            isUploadInProgress = false;
            window.removeEventListener('beforeunload', handleBeforeUnload);
        }
    }

    /**
     * Remove the active upload from the status bar on terminal
     * failure/cancel (success transitions to the server task instead).
     */
    function removeStatusBarEntry() {
        if (statusBarClientId && typeof StatusBar !== 'undefined') {
            StatusBar.removeEntry(statusBarClientId);
        }
        statusBarClientId = null;
    }

    /**
     * Reset upload form
     */
    function resetUploadForm() {
        var nameInput = document.getElementById('binary-name');
        var fileInput = document.getElementById('upload-binary');
        if (nameInput) nameInput.value = '';
        if (fileInput) fileInput.value = '';
        setProgressIndeterminate(false);
        setProgressWidth(0);
    }

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
