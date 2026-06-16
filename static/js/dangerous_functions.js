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

// Severity count elements
const criticalCountEl = document.getElementById('critical-count');
const highCountEl = document.getElementById('high-count');
const mediumCountEl = document.getElementById('medium-count');
const lowCountEl = document.getElementById('low-count');
const totalCountEl = document.getElementById('total-count');
const totalScannedEl = document.getElementById('total-scanned');
const scanTargetNameEl = document.getElementById('scan-target-name');

// ── State ─────────────────────────────────────────────────────

let availableModels = [];
let availablePredictions = [];

// ── Initialization ────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadAvailableTargets();
    setupEventListeners();
});

/**
 * Load available models and prediction tasks from the API.
 */
async function loadAvailableTargets() {
    try {
        const response = await fetch('/api/v1/dangerous-functions/available-models');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const result = await response.json();
        const data = result.data;
        availableModels = data.models || [];
        availablePredictions = data.prediction_tasks || [];
        updateTargetDropdown('model');
    } catch (error) {
        console.error('Failed to load available targets:', error);
        showScanError('Failed to load available targets. Please try again.');
    }
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

    // Close modal on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && contextModal && contextModal.style.display !== 'none') {
            closeModal();
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
 * @param {string} type - 'model' or 'prediction'
 */
function updateTargetDropdown(type) {
    if (!targetSelect) return;

    targetSelect.disabled = true;
    targetSelect.innerHTML = '<option value="">Loading...</option>';
    scanBtn.disabled = true;

    const targets = type === 'model' ? availableModels : availablePredictions;

    if (targets.length === 0) {
        targetSelect.innerHTML = '<option value="">No targets available</option>';
        targetSelect.disabled = true;
        return;
    }

    targetSelect.innerHTML = '<option value="">Select a target...</option>';
    targets.forEach((target) => {
        const option = document.createElement('option');
        option.value = target;
        option.textContent = target;
        targetSelect.appendChild(option);
    });

    targetSelect.disabled = false;
}

/**
 * Update scan button state based on target selection.
 */
function updateScanButtonState() {
    if (!scanBtn || !targetSelect) return;
    scanBtn.disabled = !targetSelect.value;
}

// ── Scan Execution ────────────────────────────────────────────

/**
 * Run the dangerous function scan.
 */
async function runScan() {
    if (!targetSelect || !targetSelect.value) return;

    const targetType = targetTypeSelect ? targetTypeSelect.value : 'model';
    const targetName = targetSelect.value;

    // UI: Show loading state
    setScanLoading(true);
    hideResults();
    hideError();

    const body = targetType === 'model'
        ? { modelName: targetName }
        : { taskName: targetName };

    try {
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

        const data = result.data;
        displayResults(data, targetName);

    } catch (error) {
        console.error('Scan failed:', error);
        showScanError(error.message || 'Scan failed. Please try again.');
    } finally {
        setScanLoading(false);
    }
}

/**
 * Set the scan button loading state.
 * @param {boolean} loading - Whether the scan is in progress.
 */
function setScanLoading(loading) {
    if (!scanBtn) return;

    scanBtn.disabled = loading;
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

    if (results.length === 0) {
        // No dangerous functions found
        scanSummary.style.display = '';
        scanResultsContainer.style.display = 'none';
        noResultsMessage.style.display = '';
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

// ── UI Helpers ────────────────────────────────────────────────

/**
 * Hide all results sections.
 */
function hideResults() {
    if (scanSummary) scanSummary.style.display = 'none';
    if (scanResultsContainer) scanResultsContainer.style.display = 'none';
    if (noResultsMessage) noResultsMessage.style.display = 'none';
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
