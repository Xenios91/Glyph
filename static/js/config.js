/**
 * Glyph - Configuration Page JavaScript
 * Handles configuration form interactions and saving
 * Uses native fetch API and event listeners
 */

/**
 * Update slider display value and sync with input field
 * @param {string} sliderId - ID of the slider element
 * @param {string} labelId - ID of the display label element
 * @param {string} unit - Unit suffix (e.g., ' MB', ' cores')
 */
function updateSlider(sliderId, labelId, unit) {
    const slider = document.getElementById(sliderId);
    if (!slider) return;
    
    document.getElementById(labelId).textContent = slider.value + unit;
    
    const map = { 
        'max-file-size': 'max-file-size-input', 
        'cpu-cores': 'cpu-cores-input' 
    };
    
    if (map[sliderId]) {
        const input = document.getElementById(map[sliderId]);
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
    
    const clamped = Math.min(
        Math.max(parseInt(value) || slider.min, slider.min), 
        slider.max
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
 * @param {string} okMsg - Success message
 * @param {string} errMsg - Error message
 */
function showStatus(success, okMsg, errMsg) {
    const box = document.getElementById('save-status');
    const msg = document.getElementById('save-status-msg');
    
    if (!box || !msg) return;
    
    box.style.display = 'block';
    box.classList.remove('is-success', 'is-error');
    
    if (success === true) { 
        box.classList.add('is-success'); 
        msg.textContent = okMsg; 
    } else if (success === false) { 
        box.classList.add('is-error'); 
        msg.textContent = errMsg; 
    } else { 
        msg.textContent = okMsg; 
    }
}

/**
 * Save configuration to server
 */
async function saveConfig() {
    const maxFileSizeSlider = document.getElementById('max-file-size');
    const cpuCoresSlider = document.getElementById('cpu-cores');
    
    if (!maxFileSizeSlider || !cpuCoresSlider) {
        Toast.error('Configuration form not fully loaded');
        return;
    }
    
    const config = {
        max_file_size_mb: parseInt(maxFileSizeSlider.value),
        cpu_cores: parseInt(cpuCoresSlider.value),
    };
    
    try {
        const response = await fetch('/api/v1/config/save', getFetchOptionsWithCsrf({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        }));
        
        if (response.ok) {
            const data = await response.json();
            showStatus(
                true,
                data.message ? `[ ✔ ] ${data.message}` : '[ ✔ ] CONFIGURATION SAVED SUCCESSFULLY.',
                ''
            );
            Toast.success('Configuration saved successfully');
        } else {
            const errorData = await response.json().catch(() => ({}));
            const errorMessage = errorData.detail || errorData.message || 'Failed to save configuration';
            showStatus(false, '', `[ ✘ ] ERROR: ${errorMessage}`);
            Toast.error(errorMessage);
        }
    } catch (error) {
        console.error('Config save error:', error);
        showStatus(false, '', '[ ✘ ] ERROR: NETWORK FAILURE.');
        Toast.error('Network error. Please try again.');
    }
}

/**
 * Reset all configuration values to defaults
 */
function resetDefaults() {
    const maxFileSizeSlider = document.getElementById('max-file-size');
    const maxFileSizeInput = document.getElementById('max-file-size-input');
    const cpuCoresSlider = document.getElementById('cpu-cores');
    const cpuCoresInput = document.getElementById('cpu-cores-input');
    
    if (maxFileSizeSlider) {
        maxFileSizeSlider.value = 512;
        updateSlider('max-file-size', 'max-file-size-val', ' MB');
    }
    if (maxFileSizeInput) {
        maxFileSizeInput.value = 512;
    }
    
    if (cpuCoresSlider) {
        cpuCoresSlider.value = 2;
        updateSlider('cpu-cores', 'cpu-cores-val', ' cores');
    }
    if (cpuCoresInput) {
        cpuCoresInput.value = 2;
    }
    
    showStatus(null, '[ ↺ ] DEFAULTS RESTORED. PRESS SAVE TO APPLY.', '');
    Toast.info('Defaults restored. Press Save to apply.');
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
    
    // Bind input field events
    const maxFileSizeInput = document.getElementById('max-file-size-input');
    const cpuCoresInput = document.getElementById('cpu-cores-input');
    
    if (maxFileSizeInput) {
        maxFileSizeInput.addEventListener('input', (e) => {
            syncFromInput('max-file-size', 'max-file-size-val', e.target.value, ' MB');
        });
    }
    
    if (cpuCoresInput) {
        cpuCoresInput.addEventListener('input', (e) => {
            syncFromInput('cpu-cores', 'cpu-cores-val', e.target.value, ' cores');
        });
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initConfigPage);
} else {
    initConfigPage();
}
