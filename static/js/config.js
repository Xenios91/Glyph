/**
 * Glyph - Configuration Page JavaScript
 * Handles configuration form interactions and saving
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
        document.getElementById(map[sliderId]).value = slider.value;
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
    document.getElementById(labelId).textContent = clamped + unit;
}

/**
 * Save configuration to server
 */
async function saveConfig() {
    const config = {
        max_file_size_mb: parseInt(document.getElementById('max-file-size').value),
        cpu_cores: parseInt(document.getElementById('cpu-cores').value),
    };
    
    try {
        const response = await fetch('/api/v1/config/save', getFetchOptionsWithCsrf({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        }));
        
        showStatus(
            response.ok,
            '[ ✔ ] CONFIGURATION SAVED SUCCESSFULLY.',
            '[ ✘ ] ERROR: FAILED TO SAVE CONFIGURATION.'
        );
    } catch (error) {
        showStatus(false, '', '[ ✘ ] ERROR: NETWORK FAILURE.');
    }
}

/**
 * Reset all configuration values to defaults
 */
function resetDefaults() {
    document.getElementById('max-file-size').value = 512;
    updateSlider('max-file-size', 'max-file-size-val', ' MB');
    document.getElementById('max-file-size-input').value = 512;
    
    document.getElementById('cpu-cores').value = 2;
    updateSlider('cpu-cores', 'cpu-cores-val', ' cores');
    document.getElementById('cpu-cores-input').value = 2;
    
    showStatus(null, '[ ↺ ] DEFAULTS RESTORED. PRESS SAVE TO APPLY.', '');
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
 * Initialize config page event listeners
 */
function initConfigPage() {
    // Bind save button
    const saveBtn = document.querySelector('button[onclick="saveConfig()"]');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveConfig);
    }
    
    // Bind reset button
    const resetBtn = document.querySelector('button[onclick="resetDefaults()"]');
    if (resetBtn) {
        resetBtn.addEventListener('click', resetDefaults);
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initConfigPage);
} else {
    initConfigPage();
}
