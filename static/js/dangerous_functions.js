/**
 * Glyph - Dangerous Function Scanner JavaScript
 * Handles scanning binaries for dangerous/insecure functions
 * and displaying results with severity indicators and usage context.
 */
'use strict';

// ── DOM Elements ──────────────────────────────────────────────

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

// Stored scan results banner elements
const storedResultsBanner = document.getElementById('stored-results-banner');
const storedResultsText = document.getElementById('stored-results-text');
const viewStoredBtn = document.getElementById('view-stored-btn');
const clearStoredBtn = document.getElementById('clear-stored-btn');

// LLM analysis elements
const llmCheckBtn = document.getElementById('llm-check-btn');
const llmModal = document.getElementById('llm-modal');
const llmModalCloseBtn = document.getElementById('llm-modal-close-btn');
const llmModalRetryBtn = document.getElementById('llm-modal-retry-btn');

// Severity count elements
const criticalCountEl = document.getElementById('critical-count');
const highCountEl = document.getElementById('high-count');
const mediumCountEl = document.getElementById('medium-count');
const lowCountEl = document.getElementById('low-count');
const totalCountEl = document.getElementById('total-count');
const totalScannedEl = document.getElementById('total-scanned');
const scanTargetNameEl = document.getElementById('scan-target-name');

// ── State ─────────────────────────────────────────────

let availableModels = [];
let availablePredictions = [];
let availableBinaries = [];

// Last scan report data (findings are sent to the LLM endpoint from here)
let lastScanData = null;
// Cached stored scan reports keyed by target name (filled on target selection)
let storedReportCache = {};
// True while a scan request is in flight (prevents concurrent scans/LLM runs)
let scanInProgress = false;
// Per-row LLM results keyed by row index:
// {status, analysis, error, model, source: 'stored'|'fresh', modifiedAt?, elapsedMs?}
let llmResults = {};
// Row index currently open in the LLM modal
let llmModalOpenIndex = null;

// ── Initialization ────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadAvailableTargets();
    setupEventListeners();
});

/**
 * Load available models, prediction tasks, and binaries from the API.
 */
async function loadAvailableTargets() {
    try {
        const [modelsResponse, binariesResponse] = await Promise.all([
            fetch('/api/v1/dangerous-functions/available-models'),
            fetch('/api/v1/binaries/list')
        ]);

        if (!modelsResponse.ok) {
            throw new Error(`HTTP ${modelsResponse.status}: ${modelsResponse.statusText}`);
        }
        const modelsResult = await modelsResponse.json();
        const modelsData = modelsResult.data;
        availableModels = modelsData.models || [];
        availablePredictions = modelsData.prediction_tasks || [];

        if (binariesResponse.ok) {
            const binariesResult = await binariesResponse.json();
            availableBinaries = binariesResult.data?.items || [];
        }

        // Check for binary_id URL parameter before populating dropdowns
        const binaryId = getUrlParameter('binary_id');
        if (binaryId) {
            const binary = availableBinaries.find(b => String(b.id) === String(binaryId));
            if (binary) {
                selectBinaryTarget(binary);
                return;
            }
        }

        updateTargetDropdown('model');
    } catch (error) {
        console.error('Failed to load available targets:', error);
        showScanError('Failed to load available targets. Please try again.');
    }
}

/**
 * Read a URL query parameter.
 * @param {string} name - Parameter name.
 * @returns {string|null} Parameter value or null.
 */
function getUrlParameter(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name);
}

/**
 * Pre-select a binary as the scan target.
 * @param {Object} binary - Binary object with id and name.
 */
function selectBinaryTarget(binary) {
    if (targetTypeSelect) {
        targetTypeSelect.value = 'binary';
        targetTypeSelect.dispatchEvent(new Event('change'));
    }

    // Wait for dropdown to populate, then select
    setTimeout(() => {
        if (targetSelect) {
            targetSelect.value = String(binary.id);
            updateScanButtonState();
            checkStoredResults();
        }
    }, 100);
}

/**
 * Setup event listeners for controls.
 */
function setupEventListeners() {
    if (targetTypeSelect) {
        targetTypeSelect.addEventListener('change', (e) => {
            updateTargetDropdown(e.target.value);
        });
    }

    if (targetSelect) {
        targetSelect.addEventListener('change', () => {
            updateScanButtonState();
            checkStoredResults();
        });
    }

    if (scanBtn) {
        scanBtn.addEventListener('click', runScan);
    }

    if (modalCloseBtn) {
        modalCloseBtn.addEventListener('click', closeModal);
    }

    // Close modal on background click
    if (contextModal) {
        contextModal.addEventListener('click', (e) => {
            if (e.target === contextModal) {
                closeModal();
            }
        });
    }

    if (llmCheckBtn) {
        llmCheckBtn.addEventListener('click', runLLMAnalysis);
    }

    if (llmModalCloseBtn) {
        llmModalCloseBtn.addEventListener('click', closeLlmModal);
    }

    // Close LLM modal on background click
    if (llmModal) {
        llmModal.addEventListener('click', (e) => {
            if (e.target === llmModal) {
                closeLlmModal();
            }
        });
    }

    if (llmModalRetryBtn) {
        llmModalRetryBtn.addEventListener('click', () => {
            if (llmModalOpenIndex !== null) {
                retryLlmFinding(llmModalOpenIndex);
            }
        });
    }

    if (viewStoredBtn) {
        viewStoredBtn.addEventListener('click', viewStoredResults);
    }

    if (clearStoredBtn) {
        clearStoredBtn.addEventListener('click', clearStoredResults);
    }

    // Close modals on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape') return;
        if (contextModal && contextModal.style.display !== 'none') {
            closeModal();
        }
        if (llmModal && llmModal.style.display !== 'none') {
            closeLlmModal();
        }
    });

    // Back button
    const backBtn = document.querySelector('.back-btn');
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            window.location.href = '/';
        });
    }
}

/**
 * Update the target dropdown based on selected target type.
 * @param {string} type - 'model', 'prediction', or 'binary'
 */
function updateTargetDropdown(type) {
    if (!targetSelect) return;

    targetSelect.disabled = true;
    targetSelect.innerHTML = '<option value="">Loading...</option>';
    scanBtn.disabled = true;
    updateLlmButtonState();

    let targets;
    if (type === 'model') {
        targets = availableModels;
    } else if (type === 'prediction') {
        targets = availablePredictions;
    } else if (type === 'binary') {
        targets = availableBinaries;
    } else {
        targets = availableModels;
    }

    if (targets.length === 0) {
        targetSelect.innerHTML = '<option value="">No targets available</option>';
        targetSelect.disabled = true;
        return;
    }

    targetSelect.innerHTML = '<option value="">Select a target...</option>';
    targets.forEach((target) => {
        const option = document.createElement('option');
        if (type === 'binary') {
            // For binaries, value is the id and text is the name
            option.value = target.id;
            option.textContent = target.name;
        } else {
            option.value = target;
            option.textContent = target;
        }
        targetSelect.appendChild(option);
    });

    targetSelect.disabled = false;
    updateLlmButtonState();
}

/**
 * Update scan button state based on target selection.
 * The "Check with LLM" button follows the same target-selection rule.
 */
function updateScanButtonState() {
    if (!scanBtn || !targetSelect) return;
    scanBtn.disabled = !targetSelect.value;
    updateLlmButtonState();
}

// ── Scan Execution ────────────────────────────────────────────

/**
 * Determine the display name of the currently selected target.
 * @returns {string|null} Target name, or null when no target is selected.
 */
function getCurrentTargetName() {
    if (!targetTypeSelect || !targetSelect || !targetSelect.value) return null;

    const targetType = targetTypeSelect.value;
    const targetValue = targetSelect.value;

    if (targetType === 'binary') {
        const binary = availableBinaries.find(b => b.id === parseInt(targetValue, 10));
        return binary ? binary.name : `Binary ${targetValue}`;
    }
    return targetValue;
}

/**
 * True when the last scan produced findings for the currently selected target.
 * @returns {boolean} Whether findings are available for the current target.
 */
function hasFindingsForCurrentTarget() {
    return !!(
        lastScanData &&
        Array.isArray(lastScanData.results) &&
        lastScanData.results.length > 0 &&
        lastScanData.model_name === getCurrentTargetName()
    );
}

/**
 * Perform a scan request for the currently selected target.
 * @returns {Promise<{data: Object, targetName: string}>} Scan report data and display name.
 */
async function performScan() {
    if (!targetSelect || !targetSelect.value) {
        throw new Error('No target selected');
    }

    const targetType = targetTypeSelect ? targetTypeSelect.value : 'model';
    const targetValue = targetSelect.value;
    const targetName = getCurrentTargetName() || targetValue;

    let body;
    if (targetType === 'binary') {
        body = { binaryId: parseInt(targetValue, 10) };
    } else if (targetType === 'model') {
        body = { modelName: targetValue };
    } else {
        body = { taskName: targetValue };
    }

    const response = await fetch('/api/v1/dangerous-functions/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });

    const result = await response.json();

    if (!response.ok) {
        const errorMsg = result.error?.message || `Scan failed (${response.status})`;
        throw new Error(errorMsg);
    }

    return { data: result.data, targetName };
}

/**
 * Run the dangerous function scan.
 */
async function runScan() {
    if (!targetSelect || !targetSelect.value) return;

    // UI: Show loading state
    setScanLoading(true);
    scanInProgress = true;
    hideResults();
    hideError();
    hideStoredResultsBanner();
    resetLlmState();

    try {
        const { data, targetName } = await performScan();
        displayResults(data, targetName);
        // The fresh scan just overwrote the stored report for this target
        storedReportCache[targetName] = data;
    } catch (error) {
        console.error('Scan failed:', error);
        showScanError(error.message || 'Scan failed. Please try again.');
    } finally {
        scanInProgress = false;
        setScanLoading(false);
    }
}

/**
 * Set the scan button loading state.
 * @param {boolean} loading - Whether the scan is in progress.
 */
function setScanLoading(loading) {
    if (!scanBtn) return;

    if (loading) {
        scanBtn.disabled = true;
    } else {
        updateScanButtonState();
    }

    const btnText = scanBtn.querySelector('.btn-text');
    const btnLoading = scanBtn.querySelector('.btn-loading');

    if (btnText) btnText.style.display = loading ? 'none' : '';
    if (btnLoading) btnLoading.style.display = loading ? '' : 'none';
}

// ── Results Display ───────────────────────────────────────────

/**
 * Display scan results.
 * @param {Object} data - Scan report data.
 * @param {string} targetName - Name of the scanned target.
 */
function displayResults(data, targetName) {
    // Update summary
    if (scanTargetNameEl) scanTargetNameEl.textContent = targetName;
    if (criticalCountEl) criticalCountEl.textContent = data.critical_count || 0;
    if (highCountEl) highCountEl.textContent = data.high_count || 0;
    if (mediumCountEl) mediumCountEl.textContent = data.medium_count || 0;
    if (lowCountEl) lowCountEl.textContent = data.low_count || 0;
    if (totalCountEl) totalCountEl.textContent = data.total_found || 0;
    if (totalScannedEl) totalScannedEl.textContent = data.total_functions_scanned || 0;

    const results = data.results || [];

    // New scan: reset LLM state (stored results are re-fetched below)
    lastScanData = data;
    llmResults = {};
    llmModalOpenIndex = null;

    if (results.length === 0) {
        // No dangerous functions found
        scanSummary.style.display = '';
        scanResultsContainer.style.display = 'none';
        noResultsMessage.style.display = '';
        updateLlmButtonState();
        return;
    }

    // Show results
    scanSummary.style.display = '';
    scanResultsContainer.style.display = '';
    noResultsMessage.style.display = 'none';

    // Build results table
    if (scanResultsBody) {
        scanResultsBody.innerHTML = '';
        results.forEach((result, index) => {
            const row = createResultRow(result, index);
            scanResultsBody.appendChild(row);
        });
    }

    // Refresh LLM badges (placeholders first; stored results fill in asynchronously)
    renderLlmBadges();
    updateLlmButtonState();

    // Pre-populate badges from stored LLM results for this target (non-blocking)
    loadStoredLlmResults(data.model_name);

    // Initialize pagination
    const paginationEl = document.getElementById('scan-results-pagination');
    if (paginationEl) {
        paginationEl.style.display = '';
        const pagination = new Pagination({
            tableSelector: '.scan-results-table',
            paginationSelector: '#scan-results-pagination',
            defaultPageSize: 10,
            pageSizes: [10, 25, 50, 100],
            storageKey: 'glyph_scan_results_page_size'
        });
        pagination.init();
    }
}

// ── Stored Scan Results ───────────────────────────────────────

/**
 * Check whether the currently selected target has stored scan results
 * and show the banner when it does.
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
                `/api/v1/dangerous-functions/scan-results?target_name=${encodeURIComponent(targetName)}`
            );
            if (!response.ok) return;
            const result = await response.json();
            report = result.data || null;
            storedReportCache[targetName] = report;
        } catch (error) {
            console.warn('Failed to check stored scan results:', error);
            return;
        }
    }

    // A target may have been changed while the request was in flight
    if (getCurrentTargetName() !== targetName) return;

    const hasResults = !!(report && Array.isArray(report.results) && report.results.length > 0);
    if (!hasResults) {
        hideStoredResultsBanner();
        return;
    }

    if (storedResultsText) {
        storedResultsText.textContent =
            `Stored scan results available for this target ` +
            `(${report.total_found || 0} finding${(report.total_found || 0) === 1 ? '' : 's'}).`;
    }
    if (storedResultsBanner) storedResultsBanner.style.display = '';
}

/**
 * Display the cached stored scan results for the current target.
 */
function viewStoredResults() {
    const targetName = getCurrentTargetName();
    const report = targetName ? storedReportCache[targetName] : null;
    if (!report || !Array.isArray(report.results)) return;
    displayResults(report, targetName);
    hideStoredResultsBanner();
}

/**
 * Delete the stored scan results for the current target.
 */
async function clearStoredResults() {
    const targetName = getCurrentTargetName();
    if (!targetName || !clearStoredBtn) return;

    const btnText = clearStoredBtn.querySelector('.btn-text');
    const btnLoading = clearStoredBtn.querySelector('.btn-loading');
    clearStoredBtn.disabled = true;
    if (btnText) btnText.style.display = 'none';
    if (btnLoading) btnLoading.style.display = '';

    try {
        const response = await fetch(
            `/api/v1/dangerous-functions/scan-results?target_name=${encodeURIComponent(targetName)}`,
            { method: 'DELETE' }
        );
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        delete storedReportCache[targetName];
        // The server also deletes the stored LLM analysis results for this
        // target, so drop them from memory and reset the row badges.
        if (lastScanData && lastScanData.model_name === targetName) {
            llmResults = {};
            renderLlmBadges();
            updateLlmButtonState();
        }
        hideStoredResultsBanner();
    } catch (error) {
        console.error('Failed to clear stored scan results:', error);
        showScanError('Failed to clear stored scan results. Please try again.');
    } finally {
        clearStoredBtn.disabled = false;
        if (btnText) btnText.style.display = '';
        if (btnLoading) btnLoading.style.display = 'none';
    }
}

/**
 * Hide the stored results banner.
 */
function hideStoredResultsBanner() {
    if (storedResultsBanner) storedResultsBanner.style.display = 'none';
}

/**
 * Create a table row for a scan result.
 * @param {Object} result - Scan result object.
 * @param {number} index - Row index for data attribute.
 * @returns {HTMLTableRowElement}
 */
function createResultRow(result, index) {
    const row = document.createElement('tr');
    row.setAttribute('data-index', index);
    row.classList.add('hover-row');
    row.style.cursor = 'pointer';

    const severityClass = result.severity.toLowerCase();
    const entrypoint = result.entrypoint ? '0x' + result.entrypoint : 'N/A';

    row.innerHTML = `
        <td>${escapeHtml(result.function_name)}</td>
        <td>${escapeHtml(result.containing_function)}</td>
        <td><span class="severity-badge ${severityClass}">${escapeHtml(result.severity)}</span></td>
        <td class="llm-cell"><span class="llm-badge llm-badge-placeholder">&ndash;</span></td>
    `;

    // Make entire row clickable
    row.addEventListener('click', () => {
        openContextModal(result);
    });

    return row;
}

/**
 * Open the usage context modal with result details.
 * @param {Object} result - Scan result object.
 */
function openContextModal(result) {
    const modalFunctionName = document.getElementById('modal-function-name');
    const modalContainingFunction = document.getElementById('modal-containing-function');
    const modalSeverity = document.getElementById('modal-severity');
    const modalCwe = document.getElementById('modal-cwe');
    const modalDescription = document.getElementById('modal-description');
    const modalSafeAlternative = document.getElementById('modal-safe-alternative');
    const modalUsageContext = document.getElementById('modal-usage-context');
    const containingCodeSection = document.getElementById('containing-code-section');
    const modalContainingCode = document.getElementById('modal-containing-code');

    if (modalFunctionName) modalFunctionName.textContent = result.function_name;
    if (modalContainingFunction) modalContainingFunction.textContent = result.containing_function;

    // Severity with colored badge
    if (modalSeverity) {
        const severityClass = (result.severity || '').toLowerCase();
        modalSeverity.innerHTML = `<span class="severity-badge ${severityClass}">${escapeHtml(result.severity)}</span>`;
    }

    if (modalCwe) modalCwe.textContent = result.cwe;
    if (modalDescription) modalDescription.textContent = result.description;
    if (modalSafeAlternative) modalSafeAlternative.textContent = result.safe_alternative;

    if (modalUsageContext) {
        const contextLines = result.usage_context || [];
        if (contextLines.length > 0) {
            modalUsageContext.textContent = contextLines.join('\n');
        } else {
            modalUsageContext.textContent = '(No usage context available)';
        }
    }

    // Show containing function code if available
    if (containingCodeSection && modalContainingCode) {
        const code = result.containing_function_code || '';
        if (code) {
            modalContainingCode.textContent = code;
            containingCodeSection.style.display = '';
        } else {
            containingCodeSection.style.display = 'none';
        }
    }

    if (contextModal) {
        contextModal.style.display = 'flex';
    }
}

/**
 * Close the usage context modal.
 */
function closeModal() {
    if (contextModal) {
        contextModal.style.display = 'none';
    }
}

// ── LLM Analysis ──────────────────────────────────────

/**
 * Reset LLM state at the start of a new scan.
 */
function resetLlmState() {
    lastScanData = null;
    llmResults = {};
    llmModalOpenIndex = null;
    updateLlmButtonState();
}

/**
 * Enable the "Check with LLM" button when a target is selected or the last
 * scan produced findings for that target. Clicking it runs a scan first when
 * no results are available yet for the selected target.
 */
function updateLlmButtonState() {
    if (!llmCheckBtn) return;
    const hasTarget = !!(targetSelect && targetSelect.value);
    llmCheckBtn.disabled = scanInProgress || !(hasFindingsForCurrentTarget() || hasTarget);
}

/**
 * Set the LLM button loading state (reuses the btn-text/btn-loading swap pattern).
 * @param {boolean} loading - Whether LLM analysis is in progress.
 */
function setLlmLoading(loading) {
    if (!llmCheckBtn) return;

    const btnText = llmCheckBtn.querySelector('.btn-text');
    const btnLoading = llmCheckBtn.querySelector('.btn-loading');

    if (btnText) btnText.style.display = loading ? 'none' : '';
    if (btnLoading) btnLoading.style.display = loading ? '' : 'none';

    if (loading) {
        llmCheckBtn.disabled = true;
    } else {
        updateLlmButtonState();
    }
}

/**
 * Format an ISO timestamp as "YYYY-MM-DD HH:MM UTC" for tooltips/labels.
 * @param {string|undefined} iso - ISO 8601 timestamp.
 * @returns {string}
 */
function formatUtcTimestamp(iso) {
    if (!iso) return 'unknown time';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return String(iso);
    const pad = (n) => String(n).padStart(2, '0');
    return (
        `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())} ` +
        `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())} UTC`
    );
}

/**
 * Fetch stored LLM results for a target and fill matching row badges.
 * Non-fatal: on failure the placeholder badges stay in place.
 * @param {string} targetName - The scanned target name (persistence key).
 */
async function loadStoredLlmResults(targetName) {
    if (!targetName) return;
    const expectedScan = lastScanData;

    try {
        const response = await fetch(
            `/api/v1/dangerous-functions/llm-results?target_name=${encodeURIComponent(targetName)}`
        );
        if (!response.ok) return;

        const result = await response.json();
        const storedResults = (result.data && result.data.results) || [];

        // Bail out if a newer scan has replaced the current one while fetching
        if (expectedScan !== lastScanData) return;

        storedResults.forEach((entry) => {
            const index = (expectedScan.results || []).findIndex(
                (r) =>
                    r.function_name === entry.function_name &&
                    r.containing_function === entry.containing_function &&
                    String(r.entrypoint ?? '') === String(entry.entrypoint ?? '')
            );
            if (index === -1) return;

            llmResults[index] = {
                status: entry.status,
                analysis: entry.analysis || '',
                error: entry.error || '',
                model: entry.model_name || '',
                source: 'stored',
                modifiedAt: entry.modified_at,
                elapsedMs: entry.elapsed_ms,
            };
        });

        renderLlmBadges();
    } catch (error) {
        console.warn('Failed to load stored LLM results:', error);
    }
}

/**
 * Render the LLM badge in each results row based on llmResults.
 */
function renderLlmBadges() {
    if (!scanResultsBody) return;

    scanResultsBody.querySelectorAll('tr[data-index]').forEach((row) => {
        const index = Number(row.getAttribute('data-index'));
        const cell = row.querySelector('.llm-cell');
        if (!cell) return;

        const entry = llmResults[index];
        if (!entry) {
            cell.innerHTML = '<span class="llm-badge llm-badge-placeholder">&ndash;</span>';
            return;
        }

        const isSuccess = entry.status === 'success';
        const finding =
            lastScanData && Array.isArray(lastScanData.results) ? lastScanData.results[index] : null;
        const findingName = finding && finding.function_name ? finding.function_name : '';
        const badge = document.createElement('button');
        badge.type = 'button';
        badge.className = `llm-badge ${isSuccess ? 'llm-badge-success' : 'llm-badge-error'}`;
        badge.textContent = isSuccess ? 'AI \u2713' : 'AI !';
        badge.title =
            entry.source === 'stored'
                ? `Stored ${formatUtcTimestamp(entry.modifiedAt)}`
                : 'New - just analyzed';
        badge.setAttribute('aria-label', isSuccess
            ? `View LLM analysis for ${findingName}`
            : `View LLM analysis error for ${findingName}`);
        badge.addEventListener('click', (e) => {
            e.stopPropagation();
            openLlmModal(index);
        });

        cell.innerHTML = '';
        cell.appendChild(badge);
    });
}

/**
 * Send all findings from the last scan to the LLM analysis endpoint.
 * When no scan has been run yet for the currently selected target, a scan is
 * performed first so the user can go straight from target selection to LLM
 * analysis.
 */
async function runLLMAnalysis() {
    // No scan results for the selected target yet: run a scan first
    if (!hasFindingsForCurrentTarget()) {
        if (!targetSelect || !targetSelect.value || scanInProgress) return;

        setLlmLoading(true);
        hideError();
        scanInProgress = true;
        resetLlmState();

        try {
            const { data, targetName } = await performScan();
            displayResults(data, targetName);
        } catch (error) {
            console.error('Scan failed:', error);
            showScanError(error.message || 'Scan failed. Please try again.');
            setLlmLoading(false);
            return;
        } finally {
            scanInProgress = false;
            updateLlmButtonState();
        }

        // The scan found nothing to analyze
        if (!hasFindingsForCurrentTarget()) {
            showErrorBanner(
                'No dangerous functions were found for this target, so there is nothing to analyze with the LLM.'
            );
            setLlmLoading(false);
            return;
        }
    }

    const scanData = lastScanData;
    const findings = scanData.results;

    setLlmLoading(true);
    hideError();

    try {
        const response = await fetch('/api/v1/dangerous-functions/llm-analysis', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_name: scanData.model_name,
                save: true,
                findings: findings,
            }),
        });

        if (response.status === 503) {
            showErrorBanner(
                'LLM analysis is not configured or disabled. Enable it in Settings (LLM Analysis), then try again.'
            );
            return;
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const message =
                (errorData.detail && errorData.detail.error && errorData.detail.error.message) ||
                `LLM analysis failed (${response.status})`;
            showErrorBanner(message);
            return;
        }

        const result = await response.json();
        if (scanData !== lastScanData) return; // a newer scan replaced these results

        const data = result.data || {};
        const resultsMap = data.results || {};
        findings.forEach((_, index) => {
            const entry = resultsMap[String(index)];
            if (!entry) return;
            llmResults[index] = {
                status: entry.status,
                analysis: entry.analysis || '',
                error: entry.error || '',
                model: entry.model || data.model || '',
                source: 'fresh',
                elapsedMs: entry.elapsed_ms,
            };
        });

        renderLlmBadges();

        if (typeof Toast !== 'undefined') {
            const succeeded = data.succeeded ?? 0;
            const total = data.total ?? findings.length;
            if (succeeded > 0) {
                Toast.success(`LLM analysis complete: ${succeeded}/${total} succeeded`);
            }
            if (data.failed > 0) {
                Toast.error(`${data.failed} finding(s) failed LLM analysis - click "AI !" to view details.`);
            }
        }
    } catch (error) {
        console.error('LLM analysis failed:', error);
        showErrorBanner('LLM analysis request failed. Please try again.');
    } finally {
        setLlmLoading(false);
    }
}

/**
 * Re-analyze a single finding (per-finding retry from the LLM modal).
 * @param {number} index - Row index of the finding to retry.
 */
async function retryLlmFinding(index) {
    if (!lastScanData || !Array.isArray(lastScanData.results)) return;
    const scanData = lastScanData;
    const finding = scanData.results[index];
    if (!finding) return;

    setLlmLoading(true);

    try {
        const response = await fetch('/api/v1/dangerous-functions/llm-analysis', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_name: scanData.model_name,
                save: true,
                findings: [finding],
            }),
        });

        if (response.status === 503) {
            showErrorBanner(
                'LLM analysis is not configured or disabled. Enable it in Settings (LLM Analysis), then try again.'
            );
            return;
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const message =
                (errorData.detail && errorData.detail.error && errorData.detail.error.message) ||
                `LLM analysis failed (${response.status})`;
            showErrorBanner(message);
            return;
        }

        const result = await response.json();
        if (scanData !== lastScanData) return; // a newer scan replaced these results

        const data = result.data || {};
        const entry = (data.results || {})['0'];
        if (!entry) return;

        llmResults[index] = {
            status: entry.status,
            analysis: entry.analysis || '',
            error: entry.error || '',
            model: entry.model || data.model || '',
            source: 'fresh',
            elapsedMs: entry.elapsed_ms,
        };

        renderLlmBadges();

        // Refresh the modal if it is still open on this row
        if (llmModalOpenIndex === index) {
            openLlmModal(index);
        }
    } catch (error) {
        console.error('LLM retry failed:', error);
        showErrorBanner('LLM analysis request failed. Please try again.');
    } finally {
        setLlmLoading(false);
    }
}

/**
 * Open the LLM analysis modal for a row.
 * @param {number} index - Row index of the finding.
 */
function openLlmModal(index) {
    if (!llmModal) return;
    const entry = llmResults[index];
    const finding =
        lastScanData && Array.isArray(lastScanData.results) ? lastScanData.results[index] : null;
    if (!entry || !finding) return;

    llmModalOpenIndex = index;

    const elFunctionName = document.getElementById('llm-modal-function-name');
    const elContaining = document.getElementById('llm-modal-containing-function');
    const elSource = document.getElementById('llm-modal-source');
    const elModel = document.getElementById('llm-modal-model');
    const elElapsed = document.getElementById('llm-modal-elapsed');
    const errorSection = document.getElementById('llm-modal-error-section');
    const elErrorMessage = document.getElementById('llm-modal-error-message');
    const analysisSection = document.getElementById('llm-modal-analysis-section');
    const elAnalysis = document.getElementById('llm-modal-analysis');

    if (elFunctionName) elFunctionName.textContent = finding.function_name;
    if (elContaining) elContaining.textContent = finding.containing_function;
    if (elSource) {
        elSource.textContent =
            entry.source === 'stored'
                ? `Stored ${formatUtcTimestamp(entry.modifiedAt)}`
                : 'New - just analyzed';
    }
    if (elModel) elModel.textContent = entry.model || 'unknown';
    if (elElapsed) elElapsed.textContent = entry.elapsedMs != null ? `${entry.elapsedMs} ms` : 'N/A';

    const isSuccess = entry.status === 'success';
    if (errorSection) errorSection.style.display = isSuccess ? 'none' : '';
    if (analysisSection) analysisSection.style.display = isSuccess ? '' : 'none';
    if (!isSuccess && elErrorMessage) elErrorMessage.textContent = entry.error || 'Unknown error';
    if (isSuccess && elAnalysis) elAnalysis.textContent = entry.analysis || '';

    llmModal.style.display = 'flex';
}

/**
 * Close the LLM analysis modal.
 */
function closeLlmModal() {
    if (llmModal) {
        llmModal.style.display = 'none';
    }
    llmModalOpenIndex = null;
}

// ── UI Helpers ────────────────────────────────────────────────

/**
 * Hide all results sections.
 */
function hideResults() {
    if (scanSummary) scanSummary.style.display = 'none';
    if (scanResultsContainer) scanResultsContainer.style.display = 'none';
    if (noResultsMessage) noResultsMessage.style.display = 'none';
    hideStoredResultsBanner();
}

/**
 * Show a scan error message.
 * @param {string} message - Error message to display.
 */
function showScanError(message) {
    hideResults();
    if (scanErrorMessage) scanErrorMessage.textContent = message;
    if (scanError) scanError.style.display = '';
}

/**
 * Show the error banner without hiding existing results (for LLM failures).
 * @param {string} message - Error message to display.
 */
function showErrorBanner(message) {
    if (scanErrorMessage) scanErrorMessage.textContent = message;
    if (scanError) scanError.style.display = '';
}

/**
 * Hide the scan error message.
 */
function hideError() {
    if (scanError) scanError.style.display = 'none';
}

/**
 * Escape HTML to prevent XSS when rendering user data.
 * @param {string} text - Text to escape.
 * @returns {string}
 */
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(text)));
    return div.innerHTML;
}
