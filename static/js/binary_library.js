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

    /** @type {number|undefined} */
    let uploadTimer = undefined;

    // ============================================================
    // DOM Ready
    // ============================================================

    document.addEventListener('DOMContentLoaded', function () {
        initDragAndDrop();
        initFileInput();
        initEventDelegation();
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
                deleteBinary(id);
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
     * Show the task selection modal
     * @param {string} binaryId
     * @param {string} binaryName
     */
    function showTaskSelectionModal(binaryId, binaryName) {
        var overlay = document.getElementById('task-modal-overlay');
        if (!overlay) return;

        // Update links with the correct binary_id and binary_name
        var links = overlay.querySelectorAll('a.task-option');
        links.forEach(function (link) {
            var taskType = link.getAttribute('data-task-type');
            // Dangerous functions navigates to the dedicated scanner page
            if (taskType === 'dangerous_functions') {
                link.href = '/getDangerousFunctions?binary_id=' + binaryId;
            } else if (taskType === 'ml_training') {
                // ML Training navigates to the create model page with binary pre-selected
                link.href = '/create-model?binary_id=' + binaryId;
            } else if (taskType === 'ml_prediction') {
                // ML Prediction navigates to the create prediction page with binary pre-selected
                link.href = '/create-prediction?binary_id=' + binaryId;
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
     */
    async function deleteBinary(binaryId) {
        if (!confirm('Are you sure you want to delete this binary?')) return;

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
     * Handle selected file and trigger upload
     * @param {File} file
     */
    function handleFileSelect(file) {
        if (isUploading) return;

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
     * Upload binary to server
     * @param {File} file
     * @param {string} name
     */
    async function uploadBinary(file, name) {
        if (isUploading) return;

        isUploading = true;
        showUploadProgress(true);
        setProgressText('Uploading ' + file.name + '...');
        setProgressWidth(20);
        hideUploadError();

        var formData = new FormData();
        formData.append('name', name);
        formData.append('binary_file', file);

        try {
            setProgressText('Decompiling binary...');
            setProgressWidth(50);

            var response = await authenticatedFetch('/api/v1/binaries/uploadBinary', {
                method: 'POST',
                body: formData
            });

            setProgressWidth(80);
            setProgressText('Saving functions...');

            var data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Upload failed');
            }

            setProgressWidth(100);
            setProgressText('Upload complete!');

            setTimeout(function () {
                showUploadProgress(false);
                Toast.success('Binary "' + name + '" uploaded successfully');
                loadBinaries();
                resetUploadForm();
            }, 800);

        } catch (error) {
            console.error('Upload error:', error);
            showUploadProgress(false);
            showUploadError(error.message || 'Upload failed');
        } finally {
            isUploading = false;
        }
    }

    // ============================================================
    // Load Binaries
    // ============================================================

    /**
     * Load and display binaries list
     */
    async function loadBinaries() {
        var loadingEl = document.getElementById('binaries-loading');
        var emptyEl = document.getElementById('binaries-empty');
        var tableWrapper = document.getElementById('binaries-table-wrapper');
        var tbody = document.getElementById('binaries-tbody');

        if (loadingEl) loadingEl.style.display = 'flex';
        if (emptyEl) emptyEl.style.display = 'none';
        if (tableWrapper) tableWrapper.style.display = 'none';

        try {
            var response = await authenticatedFetch('/api/v1/binaries/list', {
                headers: { 'Accept': 'application/json' }
            });

            var data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to load binaries');
            }

            var binaries = data.data ? data.data.binaries : [];

            if (loadingEl) loadingEl.style.display = 'none';

            if (!binaries || binaries.length === 0) {
                if (emptyEl) emptyEl.style.display = 'block';
                return;
            }

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

            if (tableWrapper) tableWrapper.style.display = 'block';

        } catch (error) {
            console.error('Load binaries error:', error);
            if (loadingEl) loadingEl.style.display = 'none';
            if (emptyEl) emptyEl.style.display = 'block';
            emptyEl.innerHTML = '<p>Error loading binaries: ' + error.message + '</p>';
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

        return '<td><span class="binary-name">' + escapeHtml(binary.name) + '</span></td>' +
            '<td>' + size + '</td>' +
            '<td><span class="function-badge">' + funcCount + '</span></td>' +
            '<td><span class="date-cell">' + date + '</span></td>' +
            '<td>' +
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
        if (progress) progress.style.display = show ? 'block' : 'none';
        if (dropZone) {
            dropZone.style.pointerEvents = show ? 'none' : '';
            dropZone.style.opacity = show ? '0.5' : '';
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
     * Show upload error
     * @param {string} message
     */
    function showUploadError(message) {
        var el = document.getElementById('upload-error');
        if (el) {
            el.textContent = message;
            el.style.display = 'block';
        }
    }

    /**
     * Hide upload error
     */
    function hideUploadError() {
        var el = document.getElementById('upload-error');
        if (el) {
            el.textContent = '';
            el.style.display = 'none';
        }
    }

    /**
     * Reset upload form
     */
    function resetUploadForm() {
        var nameInput = document.getElementById('binary-name');
        var fileInput = document.getElementById('upload-binary');
        if (nameInput) nameInput.value = '';
        if (fileInput) fileInput.value = '';
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
