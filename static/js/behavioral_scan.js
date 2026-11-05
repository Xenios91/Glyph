/**
 * GLYPH — Behavioral Scan Page
 *
 * Scans a model, prediction task, or binary for malware-associated
 * behaviors using the behavioral signature catalog. Mirrors the
 * dangerous-functions scanner conventions (fetch patterns, JSON
 * envelope handling, sort/paginate, modal behavior, button loading
 * states) but without any LLM or taint-analysis features.
 */
'use strict';

/* ── DOM Elements ─────────────────────────────────────────────── */

const targetTypeSelect = document.getElementById('scan-target-type');
const targetSelect = document.getElementById('scan-target-select');
const scanBtn = document.getElementById('scan-btn');
const scanSummary = document.getElementById('scan-summary');
const scanResultsContainer = document.getElementById('scan-results-container');
const scanResultsBody = document.getElementById('scan-results-body');
const noResultsMessage = document.getElementById('no-results-message');
const scanError = document.getElementById('scan-error');
const scanErrorMessage = document.getElementById('scan-error-message');
const contextModal = document.getElementById('context-modal');
const modalCloseBtn = document.getElementById('modal-close-btn');
const storedResultsBanner = document.getElementById('stored-results-banner');
const storedResultsText = document.getElementById('stored-results-text');
const viewStoredBtn = document.getElementById('view-stored-btn');
const deleteStoredBtn = document.getElementById('delete-stored-btn');

const criticalCountEl = document.getElementById('critical-count');
const highCountEl = document.getElementById('high-count');
const mediumCountEl = document.getElementById('medium-count');
const lowCountEl = document.getElementById('low-count');
const totalCountEl = document.getElementById('total-count');
const totalScannedEl = document.getElementById('total-scanned');
const scanTargetNameEl = document.getElementById('scan-target-name');

const modalBehaviorNameEl = document.getElementById('modal-behavior-name');
const modalBehaviorCategoryEl = document.getElementById('modal-behavior-category');
const modalContainingFunctionEl = document.getElementById('modal-containing-function');
const modalSeverityEl = document.getElementById('modal-severity');
const modalAttckEl = document.getElementById('modal-attck');
const modalDescriptionEl = document.getElementById('modal-description');
const modalMatchedEvidenceEl = document.getElementById('modal-matched-evidence');
const containingCodeSection = document.getElementById('containing-code-section');
const modalContainingCodeEl = document.getElementById('modal-containing-code');

/* ── State ────────────────────────────────────────────────────── */

let availableModels = [];
let availablePredictions = [];
let availableBinaries = [];
let lastScanData = null;
let storedReportCache = {};
let scanInProgress = false;
let sortState = { key: null, direction: 'asc' };
let displayOrder = [];
let scanPagination = null;

/* ── Initialization ───────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
    loadAvailableTargets();
    setupEventListeners();
});

/**
 * Load the available scan targets (models, prediction tasks, binaries).
 */
async function loadAvailableTargets() {
    try {
        const [modelsResponse, binariesResponse] = await Promise.all([
            fetch('/api/v1/behavioral-scans/available-models'),
            fetch('/api/v1/binaries/list')
        ]);

        const modelsResult = await modelsResponse.json();
        const binariesResult = await binariesResponse.json();

        availableModels = (modelsResult.data && modelsResult.data.models) || [];
        availablePredictions =
            (modelsResult.data && modelsResult.data.prediction_tasks) || [];
        availableBinaries = (binariesResult.data && binariesResult.data.items) || [];

        // Support preselecting a binary via ?binary_id=<id>
        const binaryIdParam = getUrlParameter('binary_id');
        if (binaryIdParam) {
            const binary = availableBinaries.find(
                (b) => String(b.id) === String(binaryIdParam)
            );
            if (binary) {
                selectBinaryTarget(binary);
                return;
            }
        }

        updateTargetDropdown('model');
    } catch (err) {
        console.error('Failed to load available targets:', err);
        showScanError('Failed to load available targets. Please try again.');
    }
}

/**
 * Read a URL query parameter by name.
 */
function getUrlParameter(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name);
}

/**
 * Preselect a binary target (used with ?binary_id= links).
 */
function selectBinaryTarget(binary) {
    targetTypeSelect.value = 'binary';
    updateTargetDropdown('binary');
    setTimeout(() => {
        targetSelect.value = String(binary.id);
        updateScanButtonState();
        checkStoredResults();
    }, 100);
}

/* ── Event Listeners ──────────────────────────────────────────── */

function setupEventListeners() {
    if (targetTypeSelect) {
        targetTypeSelect.addEventListener('change', () => {
            updateTargetDropdown(targetTypeSelect.value);
            updateScanButtonState();
        });
    }

    if (targetSelect) {
        targetSelect.addEventListener('change', () => {
            updateScanButtonState();
            checkStoredResults();
        });
    }

    if (scanBtn) {
        scanBtn.addEventListener('click', () => {
            runScan();
        });
    }

    if (modalCloseBtn) {
        modalCloseBtn.addEventListener('click', () => {
            closeModal();
        });
    }

    if (contextModal) {
        contextModal.addEventListener('click', (e) => {
            if (e.target === contextModal) {
                closeModal();
            }
        });
    }

    if (viewStoredBtn) {
        viewStoredBtn.addEventListener('click', () => {
            viewStoredResults();
        });
    }

    if (deleteStoredBtn) {
        deleteStoredBtn.addEventListener('click', () => {
            deleteStoredResults();
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (contextModal && contextModal.style.display !== 'none') {
                closeModal();
            }
        }
    });

    document.querySelectorAll('.back-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            window.location.href = '/';
        });
    });

    document
        .querySelectorAll('.scan-results-table th[data-sort]')
        .forEach((th) => {
            th.addEventListener('click', () => {
                toggleSort(th.getAttribute('data-sort'));
            });
        });
}

/* ── Sorting ──────────────────────────────────────────────────── */

/**
 * Numeric rank used to order severity values.
 */
function severityRank(severity) {
    const ranks = { critical: 0, high: 1, medium: 2, low: 3 };
    return ranks[String(severity || '').toLowerCase()] ?? 99;
}

/**
 * Extract a sort key value for a finding.
 */
function getSortValue(key, finding) {
    if (key === 'severity') {
        return severityRank(finding.severity);
    }
    return String(finding[key] || '').toLowerCase();
}

/**
 * Toggle the sort direction for a column (or start sorting by it).
 */
function toggleSort(key) {
    if (sortState.key === key) {
        sortState.direction =
            sortState.direction === 'asc' ? 'desc' : 'asc';
    } else {
        sortState.key = key;
        sortState.direction = 'asc';
    }
    applySort();
    updateSortIndicators();
}

/**
 * Re-sort the display order and re-render the table.
 */
function applySort() {
    const results = lastScanData ? lastScanData.results : [];
    const indexed = results.map((finding, originalIndex) => ({
        finding,
        originalIndex
    }));

    indexed.sort((a, b) => {
        const av = getSortValue(sortState.key, a.finding);
        const bv = getSortValue(sortState.key, b.finding);
        let cmp;
        if (typeof av === 'number' && typeof bv === 'number') {
            cmp = av - bv;
        } else {
            cmp = String(av).localeCompare(String(bv));
        }
        if (cmp === 0) {
            cmp = a.originalIndex - b.originalIndex;
        }
        return sortState.direction === 'asc' ? cmp : -cmp;
    });

    displayOrder = indexed.map((entry) => entry.finding);
    renderResultsTable();
}

/**
 * Update the aria-sort attributes on the sortable headers.
 */
function updateSortIndicators() {
    document
        .querySelectorAll('.scan-results-table th[data-sort]')
        .forEach((th) => {
            const key = th.getAttribute('data-sort');
            if (key === sortState.key) {
                th.setAttribute('aria-sort', sortState.direction);
            } else {
                th.setAttribute('aria-sort', 'none');
            }
        });
}

/**
 * Rebuild the results table body from displayOrder.
 */
function renderResultsTable() {
    if (!scanResultsBody) return;
    scanResultsBody.innerHTML = '';
    displayOrder.forEach((finding, index) => {
        const row = createResultRow(finding, index);
        scanResultsBody.appendChild(row);
    });

    if (scanPagination) {
        scanPagination.rows = Array.from(
            scanResultsBody.querySelectorAll('tr')
        );
        scanPagination._applyClientPagination();
    }
}

/* ── Target Dropdown ──────────────────────────────────────────── */

/**
 * Repopulate the target dropdown for the selected target type.
 */
function updateTargetDropdown(type) {
    if (!targetSelect) return;

    targetSelect.disabled = true;
    targetSelect.innerHTML = '<option value="">Loading...</option>';

    let options = [];
    if (type === 'model') {
        options = availableModels.map((name) => ({ value: name, label: name }));
    } else if (type === 'prediction') {
        options = availablePredictions.map((name) => ({
            value: name,
            label: name
        }));
    } else if (type === 'binary') {
        options = availableBinaries.map((binary) => ({
            value: binary.id,
            label: binary.name
        }));
    }

    if (options.length === 0) {
        targetSelect.innerHTML = '<option value="">No targets available</option>';
        targetSelect.disabled = true;
        updateScanButtonState();
        return;
    }

    let html = '<option value="">Select a target...</option>';
    options.forEach((opt) => {
        html += `<option value="${escapeHtml(opt.value)}">${escapeHtml(opt.label)}</option>`;
    });
    targetSelect.innerHTML = html;
    targetSelect.disabled = false;
    updateScanButtonState();
}

/* ── Scan Button State ────────────────────────────────────────── */

/**
 * Whether the currently selected target already has results loaded
 * or findings from a previous scan.
 */
function hasScannedCurrentTarget() {
    return isCurrentTargetResultsLoaded() || hasFindingsForCurrentTarget();
}

/**
 * Enable/disable the scan button based on current state.
 */
function updateScanButtonState() {
    if (!scanBtn) return;
    scanBtn.disabled =
        scanInProgress || !targetSelect.value || hasScannedCurrentTarget();
    updateViewStoredButtonState();
}

/**
 * Resolve the display name of the currently selected target.
 */
function getCurrentTargetName() {
    if (!targetSelect || !targetSelect.value) return null;
    const targetValue = targetSelect.value;
    const type = targetTypeSelect ? targetTypeSelect.value : 'model';

    if (type === 'binary') {
        const binary = availableBinaries.find(
            (b) => String(b.id) === String(parseInt(targetValue, 10))
        );
        return binary ? binary.name : `Binary ${targetValue}`;
    }
    return targetValue;
}

/**
 * Whether the last scan produced findings for the current target.
 */
function hasFindingsForCurrentTarget() {
    return (
        !!lastScanData &&
        lastScanData.results.length > 0 &&
        lastScanData.model_name === getCurrentTargetName()
    );
}

/* ── Scan Execution ───────────────────────────────────────────── */

/**
 * POST the scan request and return the report data.
 */
async function performScan() {
    const targetValue = targetSelect.value;
    const type = targetTypeSelect.value;

    let body;
    if (type === 'binary') {
        body = { binaryId: parseInt(targetValue, 10) };
    } else if (type === 'prediction') {
        body = { taskName: targetValue };
    } else {
        body = { modelName: targetValue };
    }

    const response = await fetch('/api/v1/behavioral-scans/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });

    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(
            (result.error && result.error.message) ||
                `Scan failed (${response.status})`
        );
    }

    return { data: result.data, targetName: getCurrentTargetName() };
}

/**
 * Run a behavioral scan for the selected target.
 */
async function runScan() {
    if (scanInProgress || !targetSelect.value) return;

    setScanLoading(true);
    scanInProgress = true;
    hideResults();
    hideError();
    hideStoredResultsBanner();

    try {
        const { data, targetName } = await performScan();
        displayResults(data, targetName);
        storedReportCache[targetName] = data;
        checkStoredResults();
    } catch (err) {
        console.error('Scan failed:', err);
        showScanError(err.message || 'Scan failed. Please try again.');
    } finally {
        scanInProgress = false;
        setScanLoading(false);
    }
}

/**
 * Toggle the scan button between its normal and loading states.
 */
function setScanLoading(loading) {
    if (!scanBtn) return;
    const btnText = scanBtn.querySelector('.btn-text');
    const btnLoading = scanBtn.querySelector('.btn-loading');
    scanBtn.disabled = loading || !targetSelect.value;
    if (btnText) btnText.style.display = loading ? 'none' : '';
    if (btnLoading) btnLoading.style.display = loading ? '' : 'none';
}

/* ── Results Display ──────────────────────────────────────────── */

/**
 * Render the scan summary, severity cards, and results table.
 */
function displayResults(data, targetName) {
    if (!data) return;

    lastScanData = data;
    scanTargetNameEl.textContent = targetName || data.model_name || '';
    criticalCountEl.textContent = data.critical_count || 0;
    highCountEl.textContent = data.high_count || 0;
    mediumCountEl.textContent = data.medium_count || 0;
    lowCountEl.textContent = data.low_count || 0;
    totalCountEl.textContent = data.total_found || 0;
    totalScannedEl.textContent = data.total_functions_scanned || 0;

    sortState = { key: null, direction: 'asc' };
    displayOrder = data.results || [];
    updateScanButtonState();

    if (!displayOrder.length) {
        scanSummary.style.display = '';
        noResultsMessage.style.display = '';
        scanResultsContainer.style.display = 'none';
        return;
    }

    scanSummary.style.display = '';
    scanResultsContainer.style.display = '';
    noResultsMessage.style.display = 'none';
    updateSortIndicators();
    renderResultsTable();

    if (typeof Pagination !== 'undefined') {
        scanPagination = new Pagination({
            tableSelector: '.scan-results-table',
            paginationSelector: '#scan-results-pagination',
            defaultPageSize: 10,
            pageSizes: [10, 25, 50, 100],
            storageKey: 'glyph_behavioral_scan_results_page_size'
        });
        scanPagination.init();
    }
}

/* ── Stored Results Banner ────────────────────────────────────── */

/**
 * Check whether the current target has a stored scan report and
 * show/hide the banner accordingly.
 */
async function checkStoredResults() {
    const targetName = getCurrentTargetName();
    if (!targetName) {
        hideStoredResultsBanner();
        return;
    }

    let report = storedReportCache[targetName];
    if (!report) {
        try {
            const response = await fetch(
                `/api/v1/behavioral-scans/scan-results?target_name=${encodeURIComponent(targetName)}`
            );
            const result = await response.json().catch(() => ({}));
            report = (result && result.data) || null;
            if (report) {
                storedReportCache[targetName] = report;
            }
        } catch (err) {
            console.error('Failed to check stored results:', err);
            return;
        }
    }

    // Guard against the target changing while the request was in flight.
    if (getCurrentTargetName() !== targetName) return;

    if (!report) {
        hideStoredResultsBanner();
        return;
    }

    const count = report.total_found || 0;
    storedResultsText.textContent = `Stored scan results available for this target (${count} finding${count === 1 ? '' : 's'}).`;
    storedResultsBanner.style.display = '';
    updateViewStoredButtonState();

    if (!hasFindingsForCurrentTarget()) {
        displayResults(report, targetName);
    }
}

/**
 * Show the cached stored report for the current target.
 */
function viewStoredResults() {
    const targetName = getCurrentTargetName();
    const report = storedReportCache[targetName];
    if (!report) return;
    displayResults(report, targetName);
    checkStoredResults();
}

/**
 * Whether the current target's results are already displayed.
 */
function isCurrentTargetResultsLoaded() {
    const targetName = getCurrentTargetName();
    return !!(targetName && lastScanData && lastScanData.model_name === targetName);
}

/**
 * Enable/disable the "View Stored Results" button.
 */
function updateViewStoredButtonState() {
    if (!viewStoredBtn) return;
    const targetName = getCurrentTargetName();
    const hasStoredReport = !!storedReportCache[targetName];
    viewStoredBtn.disabled =
        scanInProgress || !hasStoredReport || isCurrentTargetResultsLoaded();
}

/**
 * Delete the stored scan report for the current target.
 */
async function deleteStoredResults() {
    const targetName = getCurrentTargetName();
    if (!targetName || !deleteStoredBtn) return;

    const btnText = deleteStoredBtn.querySelector('.btn-text');
    const btnLoading = deleteStoredBtn.querySelector('.btn-loading');
    deleteStoredBtn.disabled = true;
    if (btnText) btnText.style.display = 'none';
    if (btnLoading) btnLoading.style.display = '';

    try {
        const response = await fetch(
            `/api/v1/behavioral-scans/scan-results?target_name=${encodeURIComponent(targetName)}`,
            { method: 'DELETE' }
        );
        await response.json().catch(() => ({}));

        delete storedReportCache[targetName];
        if (lastScanData && lastScanData.model_name === targetName) {
            lastScanData = null;
            hideResults();
        }
        hideStoredResultsBanner();
        updateScanButtonState();
    } catch (err) {
        console.error('Failed to delete stored results:', err);
        showScanError('Failed to delete stored scan results.');
    } finally {
        deleteStoredBtn.disabled = false;
        if (btnText) btnText.style.display = '';
        if (btnLoading) btnLoading.style.display = 'none';
    }
}

/**
 * Hide the stored results banner.
 */
function hideStoredResultsBanner() {
    if (storedResultsBanner) {
        storedResultsBanner.style.display = 'none';
    }
    updateViewStoredButtonState();
}

/* ── Results Table Rows ───────────────────────────────────────── */

/**
 * Build a single results table row for a finding.
 */
function createResultRow(result, index) {
    const row = document.createElement('tr');
    row.setAttribute('data-index', index);
    row.classList.add('hover-row');
    row.style.cursor = 'pointer';

    const severityClass = String(result.severity || '').toLowerCase();
    row.innerHTML = `
        <td>${escapeHtml(result.behavior_name)}</td>
        <td>${escapeHtml(result.category)}</td>
        <td>${escapeHtml(result.containing_function)}</td>
        <td><span class="severity-badge ${severityClass}">${escapeHtml(result.severity)}</span></td>
    `;

    row.addEventListener('click', () => {
        openContextModal(result);
    });
    return row;
}

/* ── Finding Detail Modal ─────────────────────────────────────── */

/**
 * Open the finding detail modal for a behavioral scan result.
 */
function openContextModal(result) {
    if (!contextModal) return;

    modalBehaviorNameEl.textContent = result.behavior_name || '';
    modalBehaviorCategoryEl.textContent = result.category || '';
    modalContainingFunctionEl.textContent = result.containing_function || '';

    const severityClass = String(result.severity || '').toLowerCase();
    modalSeverityEl.innerHTML = `<span class="severity-badge ${severityClass}">${escapeHtml(result.severity)}</span>`;

    modalAttckEl.textContent = result.mitre_technique || '';
    modalDescriptionEl.textContent = result.description || '';

    const evidence = result.matched_evidence || [];
    modalMatchedEvidenceEl.textContent = evidence.length
        ? evidence.join('\n')
        : '(No matched evidence available)';

    const code = result.containing_function_code;
    if (code) {
        modalContainingCodeEl.textContent = code;
        containingCodeSection.style.display = '';
    } else {
        modalContainingCodeEl.textContent = '';
        containingCodeSection.style.display = 'none';
    }

    contextModal.style.display = 'flex';
}

/**
 * Close the finding detail modal.
 */
function closeModal() {
    if (contextModal) {
        contextModal.style.display = 'none';
    }
}

/* ── Helpers ──────────────────────────────────────────────────── */

/**
 * Hide all results-related UI.
 */
function hideResults() {
    if (scanSummary) scanSummary.style.display = 'none';
    if (scanResultsContainer) scanResultsContainer.style.display = 'none';
    if (noResultsMessage) noResultsMessage.style.display = 'none';
    hideStoredResultsBanner();
    lastScanData = null;
    displayOrder = [];
    scanPagination = null;
    updateScanButtonState();
}

/**
 * Show a scan error message.
 */
function showScanError(message) {
    hideResults();
    if (scanErrorMessage) {
        scanErrorMessage.textContent = message;
    }
    if (scanError) {
        scanError.style.display = '';
    }
}

/**
 * Hide the scan error message.
 */
function hideError() {
    if (scanError) {
        scanError.style.display = 'none';
    }
}

/**
 * Escape a string for safe insertion into HTML.
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(text ?? '')));
    return div.innerHTML;
}
