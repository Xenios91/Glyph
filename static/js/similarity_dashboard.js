/**
 * Glyph - Similarity Dashboard JavaScript
 * Handles binary selection, similarity computation, and result visualization
 */
'use strict';

(function () {
    'use strict';

    // ============================================================
    // State
    // ============================================================

    /** @type {Array<{id: number, name: string}>} */
    var binaries = [];

    /** @type {number|null} */
    var currentComputationId = null;

    /** @type {Array<Object>} */
    var currentMatrix = [];

    /** @type {number|null} */
    var pollIntervalId = null;

    // ============================================================
    // DOM Ready
    // ============================================================

    document.addEventListener('DOMContentLoaded', function () {
        initBinarySelection();
        initSavedComputations();
        initSelectionControls();
        initComputeButton();
        initViewToggle();
        initTableSorting();
        initHeatmapTooltip();
    });

    // ============================================================
    // Binary Selection
    // ============================================================

    /**
     * Load binaries and populate selection list
     */
    async function initBinarySelection() {
        try {
            var response = await authenticatedFetch('/api/v1/binaries/list');
            var data = await response.json();

            if (data.success && data.data && data.data.items) {
                binaries = data.data.items.map(function (b) {
                    return { id: b.id, name: b.name };
                });
                renderBinaryCheckboxes();
            } else {
                showElement('no-binaries');
                hideElement('binaries-loading');
            }
        } catch (err) {
            console.error('Failed to load binaries:', err);
            showToast('Failed to load binaries', 'error');
            hideElement('binaries-loading');
        }
    }

    /**
     * Render binary checkboxes in the selection list
     */
    function renderBinaryCheckboxes() {
        var container = document.getElementById('binaries-list');
        var emptyState = document.getElementById('no-binaries');
        var loading = document.getElementById('binaries-loading');

        if (!container) return;

        hideElement('binaries-loading');

        if (binaries.length === 0) {
            showElement('no-binaries');
            return;
        }

        container.innerHTML = '';
        showElement('binaries-list');

        binaries.forEach(function (binary) {
            var item = document.createElement('div');
            item.className = 'binary-checkbox-item';

            var checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = 'binary-' + binary.id;
            checkbox.value = binary.id;
            checkbox.className = 'binary-checkbox';
            checkbox.addEventListener('change', updateSelectionCount);

            var label = document.createElement('label');
            label.htmlFor = 'binary-' + binary.id;
            label.textContent = binary.name;

            var idSpan = document.createElement('span');
            idSpan.className = 'binary-id';
            idSpan.textContent = '(id: ' + binary.id + ')';

            label.appendChild(idSpan);
            item.appendChild(checkbox);
            item.appendChild(label);
            container.appendChild(item);
        });

        // Enable select all / deselect all buttons
        var selectAllBtn = document.getElementById('select-all-btn');
        var deselectAllBtn = document.getElementById('deselect-all-btn');
        if (selectAllBtn) selectAllBtn.disabled = false;
        if (deselectAllBtn) deselectAllBtn.disabled = false;
    }

    // ============================================================
    // Selection Controls
    // ============================================================

    function initSelectionControls() {
        var selectAllBtn = document.getElementById('select-all-btn');
        var deselectAllBtn = document.getElementById('deselect-all-btn');

        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', function () {
                var checkboxes = document.querySelectorAll('.binary-checkbox');
                checkboxes.forEach(function (cb) { cb.checked = true; });
                updateSelectionCount();
            });
        }

        if (deselectAllBtn) {
            deselectAllBtn.addEventListener('click', function () {
                var checkboxes = document.querySelectorAll('.binary-checkbox');
                checkboxes.forEach(function (cb) { cb.checked = false; });
                updateSelectionCount();
            });
        }
    }

    /**
     * Update selection count and enable/disable compute button
     */
    function updateSelectionCount() {
        var checkboxes = document.querySelectorAll('.binary-checkbox:checked');
        var count = checkboxes.length;
        var countEl = document.getElementById('selection-count');
        var computeBtn = document.getElementById('compute-btn');

        if (countEl) {
            countEl.textContent = count + ' selected';
        }

        if (computeBtn) {
            computeBtn.disabled = count < 2;
        }
    }

    /**
     * Get selected binary IDs
     * @returns {number[]}
     */
    function getSelectedBinaryIds() {
        var ids = [];
        document.querySelectorAll('.binary-checkbox:checked').forEach(function (cb) {
            ids.push(parseInt(cb.value, 10));
        });
        return ids;
    }

    // ============================================================
    // Compute Similarity
    // ============================================================

    function initComputeButton() {
        var btn = document.getElementById('compute-btn');
        if (!btn) return;

        btn.addEventListener('click', startSimilarityComputation);
    }

    /**
     * Start a new similarity computation
     */
    async function startSimilarityComputation() {
        var binaryIds = getSelectedBinaryIds();
        if (binaryIds.length < 2) {
            showToast('Select at least 2 binaries to compare.', 'warning');
            return;
        }

        var taskName = document.getElementById('task-name-input').value.trim();
        if (!taskName) {
            showToast('Please enter a task name.', 'warning');
            return;
        }

        var threshold = parseFloat(document.getElementById('threshold-input').value);
        if (isNaN(threshold) || threshold < 0 || threshold > 1) {
            showToast('Match threshold must be between 0 and 1.', 'warning');
            return;
        }

        // Show progress panel
        showElement('progress-panel');
        hideElement('results-panel');
        document.getElementById('compute-btn').disabled = true;
        document.getElementById('progress-text').textContent = 'Starting computation...';
        setProgressWidth(0);

        try {
            var payload = JSON.stringify({
                task_name: taskName,
                binary_ids: binaryIds,
                match_threshold: threshold
            });

            var response = await authenticatedFetch('/api/v1/tasks/similarity-computation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: payload
            });

            var data = await response.json();

            if (!data.success) {
                throw new Error(data.message || 'Computation failed to start');
            }

            var taskUuid = data.data.task_uuid;
            document.getElementById('progress-text').textContent = 'Computing similarity matrix...';
            pollTaskProgress(taskUuid);

        } catch (err) {
            console.error('Failed to start computation:', err);
            showToast(err.message || 'Failed to start computation', 'error');
            hideElement('progress-panel');
            document.getElementById('compute-btn').disabled = false;
        }
    }

    /**
     * Poll task status until completion
     * @param {string} taskUuid
     */
    async function pollTaskProgress(taskUuid) {
        var maxAttempts = 600; // 5 minutes at 0.5s intervals
        var attempts = 0;

        if (pollIntervalId) {
            clearInterval(pollIntervalId);
        }

        pollIntervalId = setInterval(async function () {
            attempts++;

            try {
                var response = await authenticatedFetch('/api/v1/tasks/' + taskUuid + '/status');
                var data = await response.json();

                if (!data.success) {
                    throw new Error('Failed to get task status');
                }

                var status = data.data.status;
                var progress = 0;

                if (status === 'starting') {
                    progress = 5;
                    document.getElementById('progress-text').textContent = 'Initializing...';
                } else if (status === 'processing') {
                    progress = 20 + Math.min(75, attempts * 2);
                    document.getElementById('progress-text').textContent = 'Computing pairwise similarities...';
                } else if (status === 'completed') {
                    progress = 100;
                    document.getElementById('progress-text').textContent = 'Computation complete!';
                    setProgressWidth(progress);

                    clearInterval(pollIntervalId);
                    pollIntervalId = null;

                    hideElement('progress-panel');
                    document.getElementById('compute-btn').disabled = false;

                    // Reload saved computations and display the latest
                    await loadSavedComputations();
                    var latestComp = getLatestComputation();
                    if (latestComp) {
                        await loadComputationResults(latestComp.id);
                    }
                    return;
                } else if (status === 'error') {
                    clearInterval(pollIntervalId);
                    pollIntervalId = null;

                    hideElement('progress-panel');
                    document.getElementById('compute-btn').disabled = false;
                    showToast('Computation failed. Check logs for details.', 'error');
                    return;
                }

                if (attempts >= maxAttempts) {
                    clearInterval(pollIntervalId);
                    pollIntervalId = null;
                    hideElement('progress-panel');
                    document.getElementById('compute-btn').disabled = false;
                    showToast('Computation timed out.', 'error');
                    return;
                }

                setProgressWidth(progress);

            } catch (err) {
                console.error('Error polling task status:', err);
            }
        }, 500);
    }

    // ============================================================
    // Saved Computations
    // ============================================================

    function initSavedComputations() {
        loadSavedComputations();
    }

    /**
     * Load saved computations from the API
     */
    async function loadSavedComputations() {
        var loading = document.getElementById('saved-loading');
        var savedList = document.getElementById('saved-list');
        var noSaved = document.getElementById('no-saved');

        try {
            var response = await authenticatedFetch('/api/v1/tasks/similarity-computations');
            var data = await response.json();

            hideElement('saved-loading');

            if (data.success && data.data && data.data.length > 0) {
                renderSavedComputations(data.data);
                showElement('saved-list');
                hideElement('no-saved');
            } else {
                hideElement('saved-list');
                showElement('no-saved');
            }
        } catch (err) {
            console.error('Failed to load saved computations:', err);
            hideElement('saved-loading');
            showElement('no-saved');
        }
    }

    /**
     * Render saved computations list
     * @param {Array<Object>} computations
     */
    function renderSavedComputations(computations) {
        var container = document.getElementById('saved-list');
        if (!container) return;

        container.innerHTML = '';

        computations.forEach(function (comp) {
            var item = document.createElement('div');
            item.className = 'saved-computation-item';

            var statusClass = 'status-' + (comp.status || 'pending');

            var metaText = comp.binary_count + ' binaries · ' +
                comp.total_comparisons + ' comparisons · ' +
                (comp.created_at ? new Date(comp.created_at).toLocaleString() : 'N/A');

            item.innerHTML =
                '<div class="saved-computation-info">' +
                    '<div class="saved-computation-name">' + escapeHtml(comp.task_name) + '</div>' +
                    '<div class="saved-computation-meta">' + metaText + '</div>' +
                    '<span class="saved-computation-status ' + statusClass + '">' + escapeHtml(comp.status) + '</span>' +
                '</div>' +
                '<div class="saved-computation-actions">' +
                    '<button class="cyber-btn is-primary btn-load" data-id="' + comp.id + '">Load</button>' +
                    '<button class="cyber-btn is-secondary btn-delete" data-id="' + comp.id + '">Delete</button>' +
                '</div>';

            // Click on the item to load results
            item.addEventListener('click', function (e) {
                if (e.target.closest('.btn-delete') || e.target.closest('.btn-load')) return;
                loadComputationResults(comp.id);
            });

            container.appendChild(item);
        });

        // Event delegation for action buttons
        container.addEventListener('click', function (e) {
            var target = e.target;

            if (target.classList.contains('btn-load')) {
                e.stopPropagation();
                var id = parseInt(target.getAttribute('data-id'), 10);
                loadComputationResults(id);
            }

            if (target.classList.contains('btn-delete')) {
                e.stopPropagation();
                var id = parseInt(target.getAttribute('data-id'), 10);
                deleteComputation(id);
            }
        });
    }

    /**
     * Get the latest computation from the saved list
     * @returns {Object|null}
     */
    function getLatestComputation() {
        var items = document.querySelectorAll('.saved-computation-item');
        if (items.length === 0) return null;

        var firstItem = items[0];
        var loadBtn = firstItem.querySelector('.btn-load');
        if (!loadBtn) return null;

        return { id: parseInt(loadBtn.getAttribute('data-id'), 10) };
    }

    /**
     * Load and display results for a specific computation
     * @param {number} computationId
     */
    async function loadComputationResults(computationId) {
        try {
            var response = await authenticatedFetch('/api/v1/tasks/similarity-computations/' + computationId);
            var data = await response.json();

            if (!data.success) {
                throw new Error(data.message || 'Failed to load computation');
            }

            var comp = data.data;
            currentComputationId = comp.computation_id;
            currentMatrix = comp.matrix || [];

            displayResults(comp);
        } catch (err) {
            console.error('Failed to load computation results:', err);
            showToast(err.message || 'Failed to load results', 'error');
        }
    }

    /**
     * Delete a saved computation
     * @param {number} computationId
     */
    async function deleteComputation(computationId) {
        if (!confirm('Are you sure you want to delete this computation?')) return;

        try {
            var response = await authenticatedFetch('/api/v1/tasks/similarity-computations/' + computationId, {
                method: 'DELETE'
            });
            var data = await response.json();

            if (data.success) {
                showToast('Computation deleted.', 'success');
                await loadSavedComputations();

                if (currentComputationId === computationId) {
                    hideElement('results-panel');
                    currentComputationId = null;
                    currentMatrix = [];
                }
            } else {
                throw new Error(data.message || 'Failed to delete');
            }
        } catch (err) {
            console.error('Failed to delete computation:', err);
            showToast(err.message || 'Failed to delete computation', 'error');
        }
    }

    // ============================================================
    // Results Display
    // ============================================================

    /**
     * Display computation results
     * @param {Object} comp
     */
    function displayResults(comp) {
        var panel = document.getElementById('results-panel');
        var header = document.getElementById('results-header');

        // Update header
        header.innerHTML =
            '<span class="task-name">' + escapeHtml(comp.task_name) + '</span>' +
            '<span class="task-meta">' + comp.binary_count + ' binaries · ' +
            comp.matrix.length + ' pairs · Status: ' + escapeHtml(comp.status) + '</span>';

        showElement('results-panel');

        // Render heatmap and table
        renderHeatmap(comp.matrix);
        renderTable(comp.matrix);

        // Scroll to results
        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // ============================================================
    // View Toggle
    // ============================================================

    function initViewToggle() {
        var heatmapBtn = document.getElementById('heatmap-btn');
        var tableBtn = document.getElementById('table-btn');

        if (heatmapBtn) {
            heatmapBtn.addEventListener('click', function () {
                heatmapBtn.classList.add('is-active');
                heatmapBtn.setAttribute('aria-pressed', 'true');
                tableBtn.classList.remove('is-active');
                tableBtn.setAttribute('aria-pressed', 'false');
                showElement('heatmap-container');
                hideElement('table-container');
            });
        }

        if (tableBtn) {
            tableBtn.addEventListener('click', function () {
                tableBtn.classList.add('is-active');
                tableBtn.setAttribute('aria-pressed', 'true');
                heatmapBtn.classList.remove('is-active');
                heatmapBtn.setAttribute('aria-pressed', 'false');
                hideElement('heatmap-container');
                showElement('table-container');
            });
        }
    }

    // ============================================================
    // Heatmap Rendering
    // ============================================================

    /**
     * Render similarity heatmap on canvas
     * @param {Array<Object>} matrix
     */
    function renderHeatmap(matrix) {
        var canvas = document.getElementById('heatmap-canvas');
        if (!canvas) return;

        var ctx = canvas.getContext('2d');
        if (!ctx) return;

        if (matrix.length === 0) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#666';
            ctx.font = '14px monospace';
            ctx.textAlign = 'center';
            ctx.fillText('No similarity data to display', canvas.width / 2, canvas.height / 2);
            return;
        }

        // Collect unique binary IDs and names
        var binaryMap = {};
        matrix.forEach(function (pair) {
            if (!binaryMap[pair.binary_a_id]) {
                binaryMap[pair.binary_a_id] = pair.binary_a_name;
            }
            if (!binaryMap[pair.binary_b_id]) {
                binaryMap[pair.binary_b_id] = pair.binary_b_name;
            }
        });

        var binaryIds = Object.keys(binaryMap).map(Number).sort(function (a, b) { return a - b; });
        var n = binaryIds.length;

        if (n === 0) return;

        // Build similarity lookup
        var simLookup = {};
        matrix.forEach(function (pair) {
            var key = pair.binary_a_id + '_' + pair.binary_b_id;
            var keyRev = pair.binary_b_id + '_' + pair.binary_a_id;
            simLookup[key] = pair.overall_similarity;
            simLookup[keyRev] = pair.overall_similarity;
        });

        // Calculate canvas size
        var labelWidth = 120;
        var labelHeight = 24;
        var cellSize = Math.max(30, Math.min(80, Math.floor((Math.min(canvas.parentElement.clientWidth - labelWidth - 40, 600)) / n)));
        var canvasSize = labelWidth + n * cellSize;

        canvas.width = canvasSize + 20;
        canvas.height = labelHeight + n * cellSize + 20;

        // Clear
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw top labels
        ctx.fillStyle = '#ccc';
        ctx.font = '11px monospace';
        ctx.textAlign = 'center';
        binaryIds.forEach(function (id, i) {
            var name = binaryMap[id];
            var shortName = name.length > 12 ? name.substring(0, 10) + '..' : name;
            ctx.fillText(shortName, labelWidth + i * cellSize + cellSize / 2, labelHeight - 4);
        });

        // Draw cells and left labels
        binaryIds.forEach(function (idA, i) {
            // Left label
            ctx.fillStyle = '#ccc';
            ctx.textAlign = 'right';
            var name = binaryMap[idA];
            var shortName = name.length > 15 ? name.substring(0, 13) + '..' : name;
            ctx.fillText(shortName, labelWidth - 6, i * cellSize + cellSize / 2 + 4);

            // Cells
            binaryIds.forEach(function (idB, j) {
                var key = idA + '_' + idB;
                var similarity = simLookup[key] || 0;

                // Color: white -> yellow -> red
                var color = getSimilarityColor(similarity);
                ctx.fillStyle = color;
                ctx.fillRect(labelWidth + j * cellSize, labelHeight + i * cellSize, cellSize - 1, cellSize - 1);

                // Draw score in cell if large enough
                if (cellSize >= 40) {
                    ctx.fillStyle = similarity > 0.5 ? '#000' : '#333';
                    ctx.font = '10px monospace';
                    ctx.textAlign = 'center';
                    ctx.fillText(similarity.toFixed(2), labelWidth + j * cellSize + cellSize / 2, labelHeight + i * cellSize + cellSize / 2 + 4);
                }
            });
        });

        // Store metadata for tooltip
        canvas._similarityData = { binaryIds: binaryIds, binaryMap: binaryMap, simLookup: simLookup, cellSize: cellSize, labelWidth: labelWidth, labelHeight: labelHeight };
    }

    /**
     * Get color for similarity score (white -> yellow -> red)
     * @param {number} score
     * @returns {string}
     */
    function getSimilarityColor(score) {
        var clamped = Math.max(0, Math.min(1, score));
        var r, g, b;

        if (clamped < 0.5) {
            var t = clamped * 2;
            r = 255;
            g = 255;
            b = Math.round(255 * (1 - t));
        } else {
            var t = (clamped - 0.5) * 2;
            r = 255;
            g = Math.round(255 * (1 - t));
            b = 0;
        }

        return '#' + toHex(r) + toHex(g) + toHex(b);
    }

    /**
     * Convert number to hex string
     * @param {number} n
     * @returns {string}
     */
    function toHex(n) {
        var hex = n.toString(16);
        return hex.length === 1 ? '0' + hex : hex;
    }

    // ============================================================
    // Heatmap Tooltip
    // ============================================================

    function initHeatmapTooltip() {
        var canvas = document.getElementById('heatmap-canvas');
        var tooltip = document.getElementById('heatmap-tooltip');
        if (!canvas || !tooltip) return;

        canvas.addEventListener('mousemove', function (e) {
            var data = canvas._similarityData;
            if (!data) return;

            var rect = canvas.getBoundingClientRect();
            var x = e.clientX - rect.left;
            var y = e.clientY - rect.top;

            var col = Math.floor((x - data.labelWidth) / data.cellSize);
            var row = Math.floor((y - data.labelHeight) / data.cellSize);

            if (row >= 0 && row < data.binaryIds.length && col >= 0 && col < data.binaryIds.length) {
                var idA = data.binaryIds[row];
                var idB = data.binaryIds[col];
                var key = idA + '_' + idB;
                var similarity = data.simLookup[key] || 0;

                tooltip.innerHTML =
                    '<strong>' + escapeHtml(data.binaryMap[idA]) + '</strong> vs ' +
                    '<strong>' + escapeHtml(data.binaryMap[idB]) + '</strong><br>' +
                    'Similarity: ' + similarity.toFixed(4);
                tooltip.style.display = 'block';
                tooltip.style.left = (e.clientX - rect.left + 15) + 'px';
                tooltip.style.top = (e.clientY - rect.top - 10) + 'px';
            } else {
                tooltip.style.display = 'none';
            }
        });

        canvas.addEventListener('mouseleave', function () {
            tooltip.style.display = 'none';
        });
    }

    // ============================================================
    // Table Rendering
    // ============================================================

    /**
     * Render similarity pairs table
     * @param {Array<Object>} matrix
     */
    function renderTable(matrix) {
        var tbody = document.getElementById('similarity-tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        matrix.forEach(function (pair) {
            var row = document.createElement('tr');

            var color = getSimilarityColor(pair.overall_similarity);

            row.innerHTML =
                '<td>' + escapeHtml(pair.binary_a_name) + ' <small style="color:#888">(id: ' + pair.binary_a_id + ')</small></td>' +
                '<td>' + escapeHtml(pair.binary_b_name) + ' <small style="color:#888">(id: ' + pair.binary_b_id + ')</small></td>' +
                '<td><span class="similarity-badge" style="background:' + color + '; color:' + (pair.overall_similarity > 0.5 ? '#000' : '#333') + '">' +
                    pair.overall_similarity.toFixed(4) + '</span></td>' +
                '<td>' + pair.matched_function_count + '</td>' +
                '<td>' + pair.total_function_comparisons + '</td>';

            tbody.appendChild(row);
        });

        // Initialize pagination after rendering table rows
        initSimilarityPagination();
    }

    /**
     * Initialize pagination for the similarity table
     */
    function initSimilarityPagination() {
        var paginationEl = document.getElementById('similarity-pagination');
        if (!paginationEl) return;

        var table = document.querySelector('#table-container .cyber-table');
        if (!table) return;

        var rows = table.querySelectorAll('tbody tr');
        if (rows.length > 0) {
            paginationEl.style.display = '';
            var pagination = new Pagination({
                tableSelector: '#table-container .cyber-table',
                paginationSelector: '#similarity-pagination',
                defaultPageSize: 10,
                pageSizes: [10, 25, 50, 100],
                storageKey: 'glyph_similarity_page_size'
            });
            pagination.init();
        } else {
            paginationEl.style.display = 'none';
        }
    }

    // ============================================================
    // Table Sorting
    // ============================================================

    function initTableSorting() {
        var headers = document.querySelectorAll('.cyber-table th[data-sort]');
        headers.forEach(function (th) {
            th.addEventListener('click', function () {
                var sortKey = th.getAttribute('data-sort');
                sortTable(sortKey);
            });
        });
    }

    /**
     * Sort the similarity table
     * @param {string} sortKey
     */
    function sortTable(sortKey) {
        if (currentMatrix.length === 0) return;

        // Determine sort direction
        var th = document.querySelector('th[data-sort="' + sortKey + '"]');
        var currentDir = th ? th.getAttribute('aria-sort') : 'none';
        var ascending = currentDir !== 'ascending';

        // Reset all headers
        document.querySelectorAll('.cyber-table th[data-sort]').forEach(function (h) {
            h.setAttribute('aria-sort', 'none');
        });
        if (th) {
            th.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
        }

        // Sort matrix
        var sorted = currentMatrix.slice().sort(function (a, b) {
            var valA, valB;

            switch (sortKey) {
                case 'binary_a':
                    valA = a.binary_a_name;
                    valB = b.binary_a_name;
                    return ascending ? valA.localeCompare(valB) : valB.localeCompare(valA);
                case 'binary_b':
                    valA = a.binary_b_name;
                    valB = b.binary_b_name;
                    return ascending ? valA.localeCompare(valB) : valB.localeCompare(valA);
                case 'similarity':
                    valA = a.overall_similarity;
                    valB = b.overall_similarity;
                    return ascending ? valA - valB : valB - valA;
                case 'matched':
                    valA = a.matched_function_count;
                    valB = b.matched_function_count;
                    return ascending ? valA - valB : valB - valA;
                case 'comparisons':
                    valA = a.total_function_comparisons;
                    valB = b.total_function_comparisons;
                    return ascending ? valA - valB : valB - valA;
                default:
                    return 0;
            }
        });

        currentMatrix = sorted;
        renderTable(sorted);
    }

    // ============================================================
    // Utility Functions
    // ============================================================

    /**
     * Show an element by ID
     * @param {string} id
     */
    function showElement(id) {
        var el = document.getElementById(id);
        if (el) el.style.display = '';
    }

    /**
     * Hide an element by ID
     * @param {string} id
     */
    function hideElement(id) {
        var el = document.getElementById(id);
        if (el) el.style.display = 'none';
    }

    /**
     * Set progress bar width
     * @param {number} percent
     */
    function setProgressWidth(percent) {
        var fill = document.getElementById('progress-bar-fill');
        if (fill) fill.style.width = Math.min(100, Math.max(0, percent)) + '%';
    }

    /**
     * Escape HTML to prevent XSS
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
