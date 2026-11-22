/**
 * Glyph - Diff Highlighting
 * Self-contained line-diff utilities for the prediction details page.
 *
 * CSP-safe: all DOM writes use createElement / textContent / classList only
 * (no innerHTML with data, no inline handlers). No dependencies.
 *
 * Exposed on `window`:
 *   - computeLineDiff(source, target)
 *   - buildDiffColumn(rows)
 *   - countDiffRows(rows)
 *   - initDiffHighlight()
 */
'use strict';

/**
 * Compute a line-based diff via longest common subsequence.
 * @param {string} source
 * @param {string} target
 * @returns {{source: Array<{no: number|null, text: string, type: string}>, target: Array<{no: number|null, text: string, type: string}>}}
 */
window.computeLineDiff = function computeLineDiff(source, target) {
    var srcLines = String(source || '').split('\n');
    var tgtLines = String(target || '').split('\n');
    var n = srcLines.length;
    var m = tgtLines.length;

    // Guard: avoid an O(n*m) blow-up on pathological inputs (e.g. very large
    // function bodies). Fall back to a plain aligned listing so the tab never
    // freezes. The listing keeps both columns row-aligned (equal counts) so
    // synchronized scrolling stays in sync.
    if (n * m > 4000000) {
        console.warn(
            'computeLineDiff: input too large (' + n + ' x ' + m +
            ' lines); falling back to a plain aligned listing.'
        );
        var fallback = { source: [], target: [] };
        var len = Math.max(n, m);
        for (var k = 0; k < len; k++) {
            fallback.source.push(
                k < n
                    ? { no: k + 1, text: srcLines[k], type: 'context' }
                    : { no: null, text: '', type: 'context' }
            );
            fallback.target.push(
                k < m
                    ? { no: k + 1, text: tgtLines[k], type: 'context' }
                    : { no: null, text: '', type: 'context' }
            );
        }
        return fallback;
    }

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
};

/**
 * Build one column of diff rows as DOM nodes (no innerHTML with data).
 * @param {Array<{no: number|null, text: string, type: string}>} rows
 * @returns {DocumentFragment}
 */
window.buildDiffColumn = function buildDiffColumn(rows) {
    var frag = document.createDocumentFragment();
    rows.forEach(function (row) {
        var line = document.createElement('div');
        line.className = 'diff-line ' + row.type;
        if (row.no === null) {
            line.classList.add('placeholder');
        }

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
};

/**
 * Count the number of non-context rows (added + removed) in one diff column.
 * @param {Array<{no: number|null, text: string, type: string}>} rows
 * @returns {number}
 */
window.countDiffRows = function countDiffRows(rows) {
    var count = 0;
    rows.forEach(function (row) {
        if (row.type !== 'context') {
            count++;
        }
    });
    return count;
};

/**
 * Initialize diff highlighting on the prediction details page.
 *
 * Reads the two side-by-side <pre> blocks, computes a line diff, and replaces
 * each <pre> with a .diff-lines column so changed lines are highlighted. The
 * <pre> markup is left as the no-JS fallback. No-op on pages that do not have
 * the two token panes.
 */
window.initDiffHighlight = function initDiffHighlight() {
    var predPre = document.querySelector('#prediction_tokens_div pre');
    var modelPre = document.querySelector('#model_tokens_div pre');
    if (!predPre || !modelPre) {
        return;
    }

    // The browser has already unescaped the Jinja-escaped text, so reading
    // textContent gives the original code verbatim.
    var predText = predPre.textContent;
    var modelText = modelPre.textContent;

    var diff = window.computeLineDiff(predText, modelText);

    var predCol = document.createElement('div');
    predCol.className = 'diff-lines';
    predCol.setAttribute('role', 'region');
    predCol.setAttribute('aria-label', 'Predicted function diff');
    predCol.appendChild(window.buildDiffColumn(diff.source));
    predPre.replaceWith(predCol);

    var modelCol = document.createElement('div');
    modelCol.className = 'diff-lines';
    modelCol.setAttribute('role', 'region');
    modelCol.setAttribute('aria-label', 'Original function diff');
    modelCol.appendChild(window.buildDiffColumn(diff.target));
    modelPre.replaceWith(modelCol);

    var summary = document.getElementById('diff-summary');
    if (summary) {
        var n = window.countDiffRows(diff.source);
        if (n === 0) {
            summary.classList.add('is-identical');
            summary.textContent =
                'No differences \u2014 predicted and original functions are identical.';
        } else {
            summary.classList.remove('is-identical');
            summary.textContent =
                n + ' difference line(s) between predicted and original function.';
        }
    }
};
