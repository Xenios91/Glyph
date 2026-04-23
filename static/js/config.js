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
                data.message || 'CONFIGURATION SAVED SUCCESSFULLY'
            );
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
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initConfigPage);
} else {
    initConfigPage();
}
