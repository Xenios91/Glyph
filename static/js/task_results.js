/**
 * Glyph - Task Results JavaScript
 * Displays task execution results
 */
'use strict';

(function () {
    'use strict';

    // ============================================================
    // State
    // ============================================================

    /** @type {string} */
    var taskUuid = window.location.search.match(/task_uuid=([^&]+)/)?.[1] || '';

    // ============================================================
    // DOM Ready
    // ============================================================

    document.addEventListener('DOMContentLoaded', function () {
        bindComparisonsInteractions();
        bindDiffModal();

        if (!taskUuid) {
            showError('No task UUID provided');
            return;
        }
        loadResults();
    });

    // ============================================================
    // Load Results
    // ============================================================

    /**
     * Load task results from API
     */
    async function loadResults() {
        try {
            var response = await authenticatedFetch('/api/v1/tasks/' + taskUuid + '/results', {
                headers: { 'Accept': 'application/json' }
            });

            var data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to load results');
            }

            var result = data.data.result;
            var status = data.data.status;

            if (!result) {
                if (status === 'completed') {
                    showEmpty();
                } else {
                    showLoadingStatus(status);
                }
                return;
            }

            renderResults(result);

        } catch (error) {
            console.error('Load results error:', error);
            showError(error.message || 'Failed to load task results');
        }
    }

    // ============================================================
    // Render Results
    // ============================================================

    /**
     * Render task results
     * @param {Object} result
     */
    function renderResults(result) {
        // Hide loading
        var loadingEl = document.getElementById('results-loading');
        if (loadingEl) loadingEl.style.display = 'none';

        // Detect task type from result structure
        if (result.total_found !== undefined && result.results) {
            // Dangerous functions scan result
            renderDangerousFunctionsResults(result);
        } else {
            // Code reuse detection result (default)
            renderCodeReuseResults(result);
        }
    }

    /**
     * Render code reuse detection results
     * @param {Object} result
     */
    function renderCodeReuseResults(result) {
        var subtitle = document.getElementById('result-subtitle');
        if (subtitle) {
            subtitle.textContent = 'Source: ' + escapeHtml(result.source_binary_name || 'Unknown') +
                ' | Task: ' + taskUuid;
        }

        // Build summary
        var comparisons = result.comparisons || [];

        // Store match token pairs for the in-page diff modal (R12). Tokens
        // stay out of the DOM: VIEW buttons reference them by index.
        matchStore.length = 0;
        comparisons.forEach(function (comp) {
            matchStore.push((comp.matched_functions || []).map(function (match) {
                return {
                    source: match.source_tokens || '',
                    target: match.target_tokens || '',
                    sourceName: match.source_function_name || '',
                    targetName: match.target_function_name || ''
                };
            }));
        });
        var totalMatches = 0;
        var totalBinaries = comparisons.length;
        var maxSimilarity = 0;

        comparisons.forEach(function (comp) {
            var matches = comp.matched_functions || [];
            totalMatches += matches.length;
            if (comp.overall_similarity > maxSimilarity) {
                maxSimilarity = comp.overall_similarity;
            }
        });

        var summaryGrid = document.getElementById('summary-grid');
        if (summaryGrid) {
            summaryGrid.innerHTML =
                '<div class="summary-card">' +
                    '<span class="card-value">' + totalBinaries + '</span>' +
                    '<span class="card-label">Binaries Compared</span>' +
                '</div>' +
                '<div class="summary-card">' +
                    '<span class="card-value">' + totalMatches + '</span>' +
                    '<span class="card-label">Functions Matched</span>' +
                '</div>' +
                '<div class="summary-card">' +
                    '<span class="card-value">' + (maxSimilarity ? (maxSimilarity * 100).toFixed(1) + '%' : '0%') + '</span>' +
                    '<span class="card-label">Max Similarity</span>' +
                '</div>';
        }

        var summaryEl = document.getElementById('results-summary');
        if (summaryEl) summaryEl.classList.remove('is-hidden');

        // Render comparisons
        if (comparisons.length > 0) {
            var listEl = document.getElementById('comparisons-list');
            if (listEl) {
                listEl.innerHTML = comparisons.map(function (comp, idx) {
                    return renderComparisonBlock(comp, idx);
                }).join('');
            }

            var containerEl = document.getElementById('comparisons-container');
            if (containerEl) containerEl.classList.remove('is-hidden');
        } else {
            showEmpty();
        }
    }

    /**
     * Render dangerous functions scan results
     * @param {Object} result
     */
    function renderDangerousFunctionsResults(result) {
        var subtitle = document.getElementById('result-subtitle');
        if (subtitle) {
            subtitle.textContent = 'Binary: ' + escapeHtml(result.binary_name || result.model_name || 'Unknown') +
                ' | Task: ' + taskUuid;
        }

        // Build summary with severity breakdown
        var summaryGrid = document.getElementById('summary-grid');
        if (summaryGrid) {
            summaryGrid.innerHTML =
                '<div class="summary-card">' +
                    '<span class="card-value">' + (result.total_functions_scanned || 0) + '</span>' +
                    '<span class="card-label">Functions Scanned</span>' +
                '</div>' +
                '<div class="summary-card">' +
                    '<span class="card-value">' + (result.total_found || 0) + '</span>' +
                    '<span class="card-label">Dangerous Functions</span>' +
                '</div>' +
                '<div class="summary-card is-critical">' +
                    '<span class="card-value">' + (result.critical_count || 0) + '</span>' +
                    '<span class="card-label">Critical</span>' +
                '</div>' +
                '<div class="summary-card is-high">' +
                    '<span class="card-value">' + (result.high_count || 0) + '</span>' +
                    '<span class="card-label">High</span>' +
                '</div>' +
                '<div class="summary-card is-medium">' +
                    '<span class="card-value">' + (result.medium_count || 0) + '</span>' +
                    '<span class="card-label">Medium</span>' +
                '</div>' +
                '<div class="summary-card is-low">' +
                    '<span class="card-value">' + (result.low_count || 0) + '</span>' +
                    '<span class="card-label">Low</span>' +
                '</div>';
        }

        var summaryEl = document.getElementById('results-summary');
        if (summaryEl) summaryEl.classList.remove('is-hidden');

        // Render scan results
        var scanResults = result.results || [];
        if (scanResults.length > 0) {
            var listEl = document.getElementById('comparisons-list');
            if (listEl) {
                listEl.innerHTML = scanResults.map(function (scan, idx) {
                    return renderScanResultBlock(scan, idx);
                }).join('');
            }

            var containerEl = document.getElementById('comparisons-container');
            if (containerEl) containerEl.classList.remove('is-hidden');
        } else {
            showEmpty();
        }
    }

    /**
     * Render a single scan result block
     * @param {Object} scan
     * @param {number} idx
     * @returns {string}
     */
    function renderScanResultBlock(scan, idx) {
        var severityClass = getSeverityClass(scan.severity);
        var contextLines = (scan.usage_context || []).map(function (line) {
            return '<code class="usage-line">' + escapeHtml(line) + '</code>';
        }).join('');

        return '<div class="comparison-block">' +
            '<div class="comparison-header" role="button" tabindex="0" aria-expanded="false" data-comparison-idx="' + idx + '">' +
                '<span class="comparison-title">' + escapeHtml(scan.function_name) +
                    ' <span class="severity-badge ' + severityClass + '">' + escapeHtml(scan.severity) + '</span>' +
                '</span>' +
                '<span class="comparison-score">' +
                    escapeHtml(scan.category) + ' | ' + escapeHtml(scan.cwe) +
                '</span>' +
            '</div>' +
            '<div class="comparison-body" id="comparison-body-' + idx + '">' +
                '<div class="scan-details">' +
                    '<div class="detail-row">' +
                        '<span class="detail-label">Containing Function:</span>' +
                        '<span class="function-name">' + escapeHtml(scan.containing_function) + '</span>' +
                    '</div>' +
                    '<div class="detail-row">' +
                        '<span class="detail-label">Entrypoint:</span>' +
                        '<code>' + escapeHtml(scan.entrypoint) + '</code>' +
                    '</div>' +
                    '<div class="detail-row">' +
                        '<span class="detail-label">Description:</span>' +
                        '<span>' + escapeHtml(scan.description) + '</span>' +
                    '</div>' +
                    '<div class="detail-row">' +
                        '<span class="detail-label">Safe Alternative:</span>' +
                        '<span class="safe-alternative">' + escapeHtml(scan.safe_alternative) + '</span>' +
                    '</div>' +
                    (contextLines ?
                        '<div class="detail-row">' +
                            '<span class="detail-label">Usage Context:</span>' +
                            '<div class="usage-context">' + contextLines + '</div>' +
                        '</div>' : ''
                    ) +
                '</div>' +
            '</div>' +
        '</div>';
    }

    /**
     * Render a single comparison block
     * @param {Object} comp
     * @param {number} idx
     * @returns {string}
     */
    function renderComparisonBlock(comp, idx) {
        var scoreClass = getScoreClass(comp.overall_similarity);
        var matches = comp.matched_functions || [];

        var rows = matches.map(function (match, mi) {
            var mClass = getScoreClass(match.similarity_score);
            return '<tr>' +
                '<td><span class="function-name">' + escapeHtml(match.source_function_name) + '</span></td>' +
                '<td><span class="function-name">' + escapeHtml(match.target_function_name) + '</span></td>' +
                '<td><span class="score-cell ' + mClass + '">' + (match.similarity_score * 100).toFixed(1) + '%</span></td>' +
                '<td><button class="code-preview-btn" type="button" data-comp-idx="' + idx +
                    '" data-match-idx="' + mi +
                    '" aria-label="View code comparison for ' + escapeHtml(match.source_function_name) + '">VIEW</button></td>' +
            '</tr>';
        }).join('');

        return '<div class="comparison-block">' +
            '<div class="comparison-header" role="button" tabindex="0" aria-expanded="false" data-comparison-idx="' + idx + '">' +
                '<span class="comparison-title">' + escapeHtml(comp.target_binary_name) + '</span>' +
                '<span class="comparison-score ' + scoreClass + '">' +
                    (comp.overall_similarity * 100).toFixed(1) + '% similar (' + matches.length + ' matches)' +
                '</span>' +
            '</div>' +
            '<div class="comparison-body" id="comparison-body-' + idx + '">' +
                (matches.length > 0 ?
                    '<table class="match-table">' +
                        '<thead><tr><th>Source Function</th><th>Target Function</th><th>Score</th><th></th></tr></thead>' +
                        '<tbody>' + rows + '</tbody>' +
                    '</table>' :
                    '<p class="empty-state">No matching functions found.</p>'
                ) +
            '</div>' +
        '</div>';
    }

    // ============================================================
    // Interactivity
    // ============================================================

    /** @type {Array<Array<{source: string, target: string, sourceName: string, targetName: string}>>} */
    var matchStore = [];

    /** @type {number|null} */
    var diffModalOpen = false;

    /** @type {Element|null} */
    var diffModalTrigger = null;

    /**
     * Toggle comparison block open/closed
     * @param {number} idx
     */
    function toggleComparison(idx) {
        var body = document.getElementById('comparison-body-' + idx);
        if (!body) return;
        var isOpen = body.classList.toggle('is-open');
        var header = document.querySelector('.comparison-header[data-comparison-idx="' + idx + '"]');
        if (header) {
            header.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        }
    }

    /**
     * Compute a line-based diff via longest common subsequence.
     * @param {string} source
     * @param {string} target
     * @returns {{source: Array<{no: number|null, text: string, type: string}>, target: Array<{no: number|null, text: string, type: string}>}}
     */
    function computeLineDiff(source, target) {
        var srcLines = String(source || '').split('\n');
        var tgtLines = String(target || '').split('\n');
        var n = srcLines.length;
        var m = tgtLines.length;

        // LCS dynamic-programming table.
        var dp = [];
        for (var i = 0; i <= n; i++) {
            dp.push(new Array(m + 1).fill(0));
        }
        for (var i2 = n - 1; i2 >= 0; i2--) {
            for (var j = m - 1; j >= 0; j--) {
                dp[i2][j] = srcLines[i2] === tgtLines[j]
                    ? dp[i2 + 1][j + 1] + 1
                    : Math.max(dp[i2 + 1][j], dp[i2][j + 1]);
            }
        }

        var out = { source: [], target: [] };
        var si = 0;
        var ti = 0;
        while (si < n && ti < m) {
            if (srcLines[si] === tgtLines[ti]) {
                out.source.push({ no: si + 1, text: srcLines[si], type: 'context' });
                out.target.push({ no: ti + 1, text: tgtLines[ti], type: 'context' });
                si++;
                ti++;
            } else if (dp[si + 1][ti] >= dp[si][ti + 1]) {
                out.source.push({ no: si + 1, text: srcLines[si], type: 'removed' });
                out.target.push({ no: null, text: '', type: 'removed' });
                si++;
            } else {
                out.source.push({ no: null, text: '', type: 'added' });
                out.target.push({ no: ti + 1, text: tgtLines[ti], type: 'added' });
                ti++;
            }
        }
        while (si < n) {
            out.source.push({ no: si + 1, text: srcLines[si], type: 'removed' });
            out.target.push({ no: null, text: '', type: 'removed' });
            si++;
        }
        while (ti < m) {
            out.source.push({ no: null, text: '', type: 'added' });
            out.target.push({ no: ti + 1, text: tgtLines[ti], type: 'added' });
            ti++;
        }
        return out;
    }

    /**
     * Build one column of diff rows as DOM nodes (no innerHTML with data).
     * @param {Array<{no: number|null, text: string, type: string}>} rows
     * @returns {DocumentFragment}
     */
    function buildDiffColumn(rows) {
        var frag = document.createDocumentFragment();
        rows.forEach(function (row) {
            var line = document.createElement('div');
            line.className = 'diff-line ' + row.type;

            var no = document.createElement('span');
            no.className = 'line-no';
            no.textContent = row.no !== null ? String(row.no) : '';

            var text = document.createElement('span');
            text.className = 'line-text';
            text.textContent = row.text;

            line.appendChild(no);
            line.appendChild(text);
            frag.appendChild(line);
        });
        return frag;
    }

    /**
     * Open the in-page code diff modal for a matched function pair.
     * @param {string} sourceCode
     * @param {string} targetCode
     * @param {string} sourceName
     * @param {string} targetName
     * @param {Element} [trigger]
     */
    function openDiffModal(sourceCode, targetCode, sourceName, targetName, trigger) {
        var overlay = document.getElementById('diff-modal-overlay');
        if (!overlay) return;

        var diff = computeLineDiff(sourceCode, targetCode);

        var sourceCol = document.getElementById('diff-source-lines');
        var targetCol = document.getElementById('diff-target-lines');
        if (sourceCol) {
            sourceCol.textContent = '';
            sourceCol.appendChild(buildDiffColumn(diff.source));
        }
        if (targetCol) {
            targetCol.textContent = '';
            targetCol.appendChild(buildDiffColumn(diff.target));
        }

        var sourceLabel = document.querySelector('#diff-source-col .diff-col-label');
        if (sourceLabel) sourceLabel.textContent = 'SOURCE: ' + (sourceName || 'unknown');
        var targetLabel = document.querySelector('#diff-target-col .diff-col-label');
        if (targetLabel) targetLabel.textContent = 'TARGET: ' + (targetName || 'unknown');

        diffModalTrigger = trigger || null;
        overlay.classList.add('is-visible');
        diffModalOpen = true;

        var closeBtn = document.getElementById('diff-modal-close');
        if (closeBtn) closeBtn.focus();
    }

    /**
     * Close the in-page code diff modal.
     */
    function closeDiffModal() {
        var overlay = document.getElementById('diff-modal-overlay');
        if (!overlay) return;
        overlay.classList.remove('is-visible');
        diffModalOpen = false;
        if (diffModalTrigger && typeof diffModalTrigger.focus === 'function') {
            diffModalTrigger.focus();
        }
        diffModalTrigger = null;
    }

    /**
     * Wire delegated interactions: comparison header toggles and
     * code-diff VIEW buttons (inline handlers are blocked by CSP).
     */
    function bindComparisonsInteractions() {
        var list = document.getElementById('comparisons-list');
        if (!list) return;

        list.addEventListener('click', function (event) {
            var target = event.target;
            if (!target || !target.closest) return;

            var previewBtn = target.closest('.code-preview-btn');
            if (previewBtn) {
                var compIdx = parseInt(previewBtn.dataset.compIdx, 10);
                var matchIdx = parseInt(previewBtn.dataset.matchIdx, 10);
                var entry = matchStore[compIdx] && matchStore[compIdx][matchIdx];
                if (entry) {
                    openDiffModal(entry.source, entry.target, entry.sourceName, entry.targetName, previewBtn);
                }
                return;
            }

            var header = target.closest('.comparison-header');
            if (header) {
                var idx = parseInt(header.dataset.comparisonIdx, 10);
                if (!isNaN(idx)) toggleComparison(idx);
            }
        });

        list.addEventListener('keydown', function (event) {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            var header = event.target && event.target.closest ? event.target.closest('.comparison-header') : null;
            if (!header) return;
            event.preventDefault();
            var idx = parseInt(header.dataset.comparisonIdx, 10);
            if (!isNaN(idx)) toggleComparison(idx);
        });
    }

    /**
     * Wire diff modal dismissal (close button, overlay click, Escape).
     */
    function bindDiffModal() {
        var overlay = document.getElementById('diff-modal-overlay');
        if (!overlay) return;

        overlay.addEventListener('click', function (event) {
            if (event.target === overlay) closeDiffModal();
        });

        var closeBtn = document.getElementById('diff-modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', closeDiffModal);
        }

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && diffModalOpen) closeDiffModal();
        });
    }

    // ============================================================
    // State Display
    // ============================================================

    /**
     * Show empty state
     */
    function showEmpty() {
        var loadingEl = document.getElementById('results-loading');
        if (loadingEl) loadingEl.style.display = 'none';

        var emptyEl = document.getElementById('results-empty');
        if (emptyEl) emptyEl.classList.remove('is-hidden');
    }

    /**
     * Show loading status for in-progress tasks
     * @param {string} status
     */
    function showLoadingStatus(status) {
        var subtitle = document.getElementById('result-subtitle');
        if (subtitle) {
            subtitle.textContent = 'Task status: ' + status.toUpperCase() + ' (waiting for completion)';
        }
    }

    /**
     * Show error state
     * @param {string} message
     */
    function showError(message) {
        var loadingEl = document.getElementById('results-loading');
        if (loadingEl) loadingEl.style.display = 'none';

        var errorEl = document.getElementById('results-error');
        var errorMsg = document.getElementById('error-message');
        if (errorEl) errorEl.classList.remove('is-hidden');
        if (errorMsg) errorMsg.textContent = message;
    }

    // ============================================================
    // Helpers
    // ============================================================

    /**
     * Get CSS class for similarity score
     * @param {number} score
     * @returns {string}
     */
    function getScoreClass(score) {
        if (score >= 0.8) return 'high';
        if (score >= 0.5) return 'medium';
        return 'low';
    }

    /**
     * Get CSS class for severity level
     * @param {string} severity
     * @returns {string}
     */
    function getSeverityClass(severity) {
        if (!severity) return '';
        return severity.toLowerCase();
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
