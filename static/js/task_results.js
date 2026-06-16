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
            var response = await authenticatedFetch('/api/v1/tasks/tasks/' + taskUuid + '/results', {
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
        var subtitle = document.getElementById('result-subtitle');
        if (subtitle) {
            subtitle.textContent = 'Source: ' + escapeHtml(result.source_binary_name || 'Unknown') +
                ' | Task: ' + taskUuid;
        }

        // Hide loading
        var loadingEl = document.getElementById('results-loading');
        if (loadingEl) loadingEl.style.display = 'none';

        // Build summary
        var comparisons = result.comparisons || [];
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
        if (summaryEl) summaryEl.style.display = 'block';

        // Render comparisons
        if (comparisons.length > 0) {
            var listEl = document.getElementById('comparisons-list');
            if (listEl) {
                listEl.innerHTML = comparisons.map(function (comp, idx) {
                    return renderComparisonBlock(comp, idx);
                }).join('');
            }

            var containerEl = document.getElementById('comparisons-container');
            if (containerEl) containerEl.style.display = 'block';
        } else {
            showEmpty();
        }
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

        var rows = matches.map(function (match) {
            var mClass = getScoreClass(match.similarity_score);
            return '<tr>' +
                '<td><span class="function-name">' + escapeHtml(match.source_function_name) + '</span></td>' +
                '<td><span class="function-name">' + escapeHtml(match.target_function_name) + '</span></td>' +
                '<td><span class="score-cell ' + mClass + '">' + (match.similarity_score * 100).toFixed(1) + '%</span></td>' +
                '<td><button class="code-preview-btn" onclick="showCodeDiff(\'' +
                    escapeJs(match.source_tokens) + '\', \'' + escapeJs(match.target_tokens) + '\')">VIEW</button></td>' +
            '</tr>';
        }).join('');

        return '<div class="comparison-block">' +
            '<div class="comparison-header" onclick="toggleComparison(' + idx + ')">' +
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

    /**
     * Toggle comparison block open/closed
     * @param {number} idx
     */
    window.toggleComparison = function (idx) {
        var body = document.getElementById('comparison-body-' + idx);
        if (body) {
            body.classList.toggle('is-open');
        }
    };

    /**
     * Show code diff in a new window
     * @param {string} sourceCode
     * @param {string} targetCode
     */
    window.showCodeDiff = function (sourceCode, targetCode) {
        var win = window.open('', '_blank', 'width=800,height=600');
        if (win) {
            win.document.write(
                '<!doctype html><html><head><title>Code Comparison</title>' +
                '<style>body{font-family:monospace;background:#111;color:#ccc;padding:20px;}' +
                '.panel{float:left;width:48%;min-height:400px;border:1px solid #333;padding:10px;overflow:auto;}' +
                '.label{font-weight:bold;color:#7dd8d8;margin-bottom:10px;display:block;}' +
                'pre{white-space:pre-wrap;word-wrap:break-word;margin:0;}</style></head>' +
                '<body>' +
                '<div class="panel"><span class="label">Source</span><pre>' + escapeHtml(sourceCode) + '</pre></div>' +
                '<div class="panel"><span class="label">Target</span><pre>' + escapeHtml(targetCode) + '</pre></div>' +
                '</body></html>'
            );
            win.document.close();
        }
    };

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
        if (emptyEl) emptyEl.style.display = 'block';
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
        if (errorEl) errorEl.style.display = 'block';
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

    /**
     * Escape for JavaScript string
     * @param {string} str
     * @returns {string}
     */
    function escapeJs(str) {
        if (!str) return '';
        return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, '\\n');
    }

})();
