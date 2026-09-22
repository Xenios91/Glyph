/**
 * Glyph - Configuration Page JavaScript
 * Handles configuration form interactions and saving
 * Uses native fetch API and event listeners
 */
'use strict';

/**
 * Update slider display value and sync with input field
 * @param {string} sliderId - ID of the slider element
 * @param {string} labelId - ID of the display label element
 * @param {string} unit - Unit suffix (e.g., ' MB', ' cores')
 */
function updateSlider(sliderId, labelId, unit) {
    const slider = document.getElementById(sliderId);
    if (!slider) return;

    const label = document.getElementById(labelId);
    if (label) {
        label.textContent = slider.value + unit;
    }

    // Sync with precision input field
    const inputMap = {
        'max-file-size': 'max-file-size-input',
        'cpu-cores': 'cpu-cores-input'
    };

    if (inputMap[sliderId]) {
        const input = document.getElementById(inputMap[sliderId]);
        if (input) {
            input.value = slider.value;
        }
    }
}

/**
 * Sync slider from input field value
 * @param {string} sliderId - ID of the slider element
 * @param {string} labelId - ID of the display label element
 * @param {string} value - Value from input field
 * @param {string} unit - Unit suffix
 */
function syncFromInput(sliderId, labelId, value, unit) {
    const slider = document.getElementById(sliderId);
    if (!slider) return;

    // Parse and clamp the value
    const parsedValue = parseInt(value) || 0;
    const clamped = Math.min(
        Math.max(parsedValue, parseInt(slider.min) || 1),
        parseInt(slider.max) || 100
    );

    slider.value = clamped;

    const label = document.getElementById(labelId);
    if (label) {
        label.textContent = clamped + unit;
    }
}

/**
 * Show status message to user
 * @param {boolean|null} success - true for success, false for error, null for info
 * @param {string} message - Message to display
 */
function showStatus(success, message) {
    const box = document.getElementById('save-status');
    const msg = document.getElementById('save-status-msg');
    const icon = box?.querySelector('.status-icon');

    if (!box || !msg) return;

    // Remove hidden attribute to show the status
    box.removeAttribute('hidden');

    // Reset classes
    box.classList.remove('is-success', 'is-error', 'is-info');

    if (success === true) {
        box.classList.add('is-success');
        if (icon) icon.textContent = '✓';
        msg.textContent = message || 'CONFIGURATION SAVED SUCCESSFULLY';
    } else if (success === false) {
        box.classList.add('is-error');
        if (icon) icon.textContent = '✗';
        msg.textContent = message || 'ERROR SAVING CONFIGURATION';
    } else {
        box.classList.add('is-info');
        if (icon) icon.textContent = 'ℹ';
        msg.textContent = message || 'INFORMATION';
    }

    // Auto-hide success messages after 3 seconds
    if (success === true) {
        setTimeout(() => {
            box.setAttribute('hidden', '');
        }, 3000);
    }
}

/**
 * Hide status message
 */
function hideStatus() {
    const box = document.getElementById('save-status');
    if (box) {
        box.setAttribute('hidden', '');
    }
}

/**
 * Collect LLM settings field elements from the page
 * @returns {Object|null} Map of field id to element, or null if the card is missing
 */
function collectLlmSettings() {
    const ids = [
        'llm-enabled',
        'llm-base-url',
        'llm-port',
        'llm-api-path',
        'llm-model',
        'llm-api-key',
        'llm-api-key-clear',
        'llm-timeout',
        'llm-temperature',
        'llm-max-concurrent'
    ];

    const els = {};
    for (const id of ids) {
        const el = document.getElementById(id);
        if (!el) return null;
        els[id] = el;
    }
    return els;
}

/**
 * Build the LLM section of the config save payload
 * @param {Object} els - LLM field elements from collectLlmSettings()
 * @returns {Object} LLM settings payload
 */
function buildLlmPayload(els) {
    const payload = {
        enabled: els['llm-enabled'].checked,
        base_url: els['llm-base-url'].value.trim(),
        port: els['llm-port'].value.trim() === '' ? null : parseInt(els['llm-port'].value, 10),
        api_path: els['llm-api-path'].value.trim(),
        model: els['llm-model'].value.trim(),
        timeout_seconds: parseFloat(els['llm-timeout'].value),
        temperature: parseFloat(els['llm-temperature'].value),
        max_concurrent: parseInt(els['llm-max-concurrent'].value, 10)
    };

    // api_key semantics: clear checkbox = explicit "" (clears stored key);
    // non-empty input = replace; blank input = key omitted entirely (no-op)
    if (els['llm-api-key-clear'].checked) {
        payload.api_key = '';
    } else {
        const key = els['llm-api-key'].value;
        if (key) {
            payload.api_key = key;
        }
    }

    return payload;
}

/**
 * Show LLM connection test result status
 * @param {boolean|null} success - true for success, false for error, null for info
 * @param {string} message - Message to display
 */
function setLlmTestStatus(success, message) {
    const box = document.getElementById('llm-test-status');
    const msg = document.getElementById('llm-test-status-msg');
    const icon = box?.querySelector('.llm-test-status-icon');

    if (!box || !msg) return;

    box.removeAttribute('hidden');
    box.classList.remove('is-success', 'is-error', 'is-info');

    if (success === true) {
        box.classList.add('is-success');
        if (icon) icon.textContent = '✓';
    } else if (success === false) {
        box.classList.add('is-error');
        if (icon) icon.textContent = '✗';
    } else {
        box.classList.add('is-info');
        if (icon) icon.textContent = 'ℹ';
    }
    msg.textContent = message;
}

/**
 * Clear LLM connection test status
 */
function clearLlmTestStatus() {
    const box = document.getElementById('llm-test-status');
    if (box) {
        box.setAttribute('hidden', '');
        box.classList.remove('is-success', 'is-error', 'is-info');
    }
}

/**
 * Test the LLM endpoint connection
 */
async function testLlmConnection() {
    const btn = document.getElementById('llm-test-btn');
    if (!btn) return;

    btn.disabled = true;
    btn.classList.add('is-loading');

    try {
        const response = await fetch('/api/v1/config/llm-test', { method: 'POST' });

        if (response.ok) {
            const data = await response.json();
            if (data.data && data.data.ok) {
                setLlmTestStatus(true, `OK — ${data.data.model} responded in ${data.data.elapsed_ms} ms`);
            } else {
                setLlmTestStatus(false, (data.data && data.data.error) || 'CONNECTION TEST FAILED');
            }
        } else if (response.status === 503) {
            setLlmTestStatus(null, 'Save your LLM settings first, then test.');
        } else if (response.status === 429) {
            setLlmTestStatus(false, 'Too many test attempts. Wait a minute and try again.');
        } else {
            const errorData = await response.json().catch(() => ({}));
            const errorMessage =
                (errorData.detail && errorData.detail.error && errorData.detail.error.message) ||
                'CONNECTION TEST FAILED';
            setLlmTestStatus(false, errorMessage);
        }
    } catch (error) {
        console.error('LLM test error:', error);
        setLlmTestStatus(false, 'NETWORK ERROR - PLEASE TRY AGAIN');
    } finally {
        btn.disabled = false;
        btn.classList.remove('is-loading');
    }
}

/**
 * Save configuration to server
 */
async function saveConfig() {
    const maxFileSizeSlider = document.getElementById('max-file-size');
    const cpuCoresSlider = document.getElementById('cpu-cores');

    if (!maxFileSizeSlider || !cpuCoresSlider) {
        showStatus(false, 'Configuration form not fully loaded');
        return;
    }

    const config = {
        max_file_size_mb: parseInt(maxFileSizeSlider.value),
        cpu_cores: parseInt(cpuCoresSlider.value),
    };

    // Include LLM settings when the LLM card is present
    const llmEls = collectLlmSettings();
    if (llmEls) {
        const bad = [];
        const portValue = llmEls['llm-port'].value.trim();
        if (portValue !== '' && !Number.isFinite(parseInt(portValue, 10))) {
            bad.push('port');
        }
        if (!Number.isFinite(parseFloat(llmEls['llm-timeout'].value))) {
            bad.push('timeout');
        }
        if (!Number.isFinite(parseFloat(llmEls['llm-temperature'].value))) {
            bad.push('temperature');
        }
        if (!Number.isFinite(parseInt(llmEls['llm-max-concurrent'].value, 10))) {
            bad.push('max_concurrent');
        }
        if (bad.length) {
            showStatus(false, 'INVALID NUMERIC VALUE(S): ' + bad.join(', '));
            return;
        }
        config.llm = buildLlmPayload(llmEls);
    }

    try {
        const response = await fetch('/api/v1/config/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        if (response.ok) {
            const data = await response.json();
            showStatus(
                true,
                data.message || 'CONFIGURATION SAVED SUCCESSFULLY'
            );
            clearLlmTestStatus();
            if (typeof Toast !== 'undefined') {
                Toast.success('Configuration saved successfully');
            }
        } else {
            const errorData = await response.json().catch(() => ({}));
            const errorMessage = errorData.detail || errorData.message || 'Failed to save configuration';
            showStatus(false, errorMessage);
            if (typeof Toast !== 'undefined') {
                Toast.error(errorMessage);
            }
        }
    } catch (error) {
        console.error('Config save error:', error);
        showStatus(false, 'NETWORK ERROR - PLEASE TRY AGAIN');
        if (typeof Toast !== 'undefined') {
            Toast.error('Network error. Please try again.');
        }
    }
}

/**
 * Reset all configuration values to defaults
 */
function resetDefaults() {
    const maxFileSizeSlider = document.getElementById('max-file-size');
    const maxFileSizeInput = document.getElementById('max-file-size-input');
    const maxFileSizeLabel = document.getElementById('max-file-size-val');

    const cpuCoresSlider = document.getElementById('cpu-cores');
    const cpuCoresInput = document.getElementById('cpu-cores-input');
    const cpuCoresLabel = document.getElementById('cpu-cores-val');

    // Reset max file size to default (512 MB)
    if (maxFileSizeSlider) {
        maxFileSizeSlider.value = 512;
    }
    if (maxFileSizeInput) {
        maxFileSizeInput.value = 512;
    }
    if (maxFileSizeLabel) {
        maxFileSizeLabel.textContent = '512 MB';
    }

    // Reset CPU cores to default (2)
    if (cpuCoresSlider) {
        cpuCoresSlider.value = 2;
    }
    if (cpuCoresInput) {
        cpuCoresInput.value = 2;
    }
    if (cpuCoresLabel) {
        cpuCoresLabel.textContent = '2 cores';
    }

    // Reset LLM settings to defaults
    const llmEls = collectLlmSettings();
    if (llmEls) {
        llmEls['llm-enabled'].checked = false;
        llmEls['llm-base-url'].value = 'https://api.openai.com';
        llmEls['llm-port'].value = '';
        llmEls['llm-api-path'].value = '/v1/chat/completions';
        llmEls['llm-model'].value = 'gpt-4o-mini';
        llmEls['llm-api-key'].value = '';
        llmEls['llm-api-key-clear'].checked = false;
        llmEls['llm-timeout'].value = 120;
        llmEls['llm-temperature'].value = 0.1;
        llmEls['llm-max-concurrent'].value = 5;
        clearLlmTestStatus();
    }

    showStatus(null, 'DEFAULTS RESTORED - PRESS SAVE TO APPLY');
    if (typeof Toast !== 'undefined') {
        Toast.info('Defaults restored. Press Save to apply.');
    }
}

/**
 * Initialize config page event listeners
 */
function initConfigPage() {
    // Bind save button
    const saveBtn = document.getElementById('save-config-btn');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveConfig);
    }

    // Bind reset button
    const resetBtn = document.getElementById('reset-defaults-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', resetDefaults);
    }

    // Bind slider events
    const maxFileSizeSlider = document.getElementById('max-file-size');
    const cpuCoresSlider = document.getElementById('cpu-cores');

    if (maxFileSizeSlider) {
        maxFileSizeSlider.addEventListener('input', () => {
            updateSlider('max-file-size', 'max-file-size-val', ' MB');
        });
    }

    if (cpuCoresSlider) {
        cpuCoresSlider.addEventListener('input', () => {
            updateSlider('cpu-cores', 'cpu-cores-val', ' cores');
        });
    }

    // Bind precision input field events
    const maxFileSizeInput = document.getElementById('max-file-size-input');
    const cpuCoresInput = document.getElementById('cpu-cores-input');

    if (maxFileSizeInput) {
        maxFileSizeInput.addEventListener('input', (e) => {
            const slider = document.getElementById('max-file-size');
            if (!slider) return;

            const min = parseInt(slider.min) || 1;
            const max = parseInt(slider.max) || 2048;
            let value = parseInt(e.target.value);

            // Clamp value to valid range
            if (isNaN(value) || value < min) {
                value = min;
            } else if (value > max) {
                value = max;
            }

            // Update input field with clamped value
            e.target.value = value;

            // Sync slider and label
            slider.value = value;
            const label = document.getElementById('max-file-size-val');
            if (label) label.textContent = value + ' MB';
        });
    }

    if (cpuCoresInput) {
        cpuCoresInput.addEventListener('input', (e) => {
            const slider = document.getElementById('cpu-cores');
            if (!slider) return;

            const min = parseInt(slider.min) || 1;
            const max = parseInt(slider.max) || 32;
            let value = parseInt(e.target.value);

            // Clamp value to valid range
            if (isNaN(value) || value < min) {
                value = min;
            } else if (value > max) {
                value = max;
            }

            // Update input field with clamped value
            e.target.value = value;

            // Sync slider and label
            slider.value = value;
            const label = document.getElementById('cpu-cores-val');
            if (label) label.textContent = value + ' cores';
        });
        }

        // Bind LLM test connection button
        const llmTestBtn = document.getElementById('llm-test-btn');
        if (llmTestBtn) {
            llmTestBtn.addEventListener('click', testLlmConnection);
        }

        // Clear stale LLM test results when LLM card fields change
        const llmCard = document.getElementById('llm-card');
        if (llmCard) {
            llmCard.addEventListener('input', clearLlmTestStatus);
            llmCard.addEventListener('change', clearLlmTestStatus);
        }
    }

// Initialize when DOM is ready using shared utility
onDomReady(initConfigPage);
