/**
 * Glyph - Upload Page JavaScript
 * Handles binary upload and ML type switching
 * Uses native fetch API instead of jQuery
 */

/**
 * Change ML type between training and prediction modes
 */
function changeMlType() {
    const generateModelBox = document.getElementById('generate-model-checkbox');
    const predictionDiv = document.getElementById('prediction-config');
    const trainingDiv = document.getElementById('training-config');
    
    if (!predictionDiv) {
        if (generateModelBox) generateModelBox.checked = true;
        if (trainingDiv) {
            trainingDiv.style.display = 'block';
            trainingDiv.classList.remove('hidden');
        }
        return;
    }
    
    if (generateModelBox.checked) {
        // Fade out prediction, fade in training
        predictionDiv.classList.add('hidden');
        setTimeout(() => {
            predictionDiv.style.display = 'none';
            trainingDiv.style.display = 'block';
            // Small delay to allow display:block to apply before removing hidden
            setTimeout(() => {
                trainingDiv.classList.remove('hidden');
            }, 10);
        }, 300);
    } else {
        // Fade out training, fade in prediction
        trainingDiv.classList.add('hidden');
        setTimeout(() => {
            trainingDiv.style.display = 'none';
            predictionDiv.style.display = 'block';
            // Small delay to allow display:block to apply before removing hidden
            setTimeout(() => {
                predictionDiv.classList.remove('hidden');
            }, 10);
        }, 300);
    }
}

/**
 * Show loading state for upload
 * @param {boolean} isLoading - Whether upload is in progress
 */
function setUploadLoading(isLoading) {
    const uploadBox = document.getElementById('upload-box');
    const uploadBtn = document.querySelector('#upload-box .cyber-btn');
    const dropZone = document.getElementById('drop-zone');
    
    if (isLoading) {
        if (uploadBox) {
            uploadBox.classList.add('is-disabled');
        }
        if (uploadBtn) {
            uploadBtn.classList.add('is-disabled');
            const originalText = uploadBtn.querySelector('span').textContent;
            uploadBtn.dataset.originalText = originalText;
            uploadBtn.querySelector('span').textContent = 'UPLOADING...';
        }
        if (dropZone) {
            dropZone.style.pointerEvents = 'none';
            dropZone.style.opacity = '0.5';
        }
    } else {
        if (uploadBox) {
            uploadBox.classList.remove('is-disabled');
        }
        if (uploadBtn && uploadBtn.dataset.originalText) {
            uploadBtn.classList.remove('is-disabled');
            uploadBtn.querySelector('span').textContent = uploadBtn.dataset.originalText;
            delete uploadBtn.dataset.originalText;
        }
        if (dropZone) {
            dropZone.style.pointerEvents = '';
            dropZone.style.opacity = '';
        }
    }
}

/**
 * Timer reference for auto-hiding the upload message
 * @type {number|undefined}
 */
let uploadMessageTimer = undefined;

/**
 * Flag to track if the processing message was already dismissed by the fallback timer.
 * Prevents showUploadStatus() from re-showing the message after a slow server response.
 * @type {boolean}
 */
let uploadMessageDismissed = false;

/**
 * Show the processing/uploading state immediately when upload starts
 */
function showUploadProcessing() {
    const uploadMessage = document.getElementById('upload-message');
    const uploadBox = document.getElementById('upload-box');
    
    if (!uploadMessage) return;
    
    const statusText = uploadMessage.querySelector('p:last-child');
    if (statusText) {
        statusText.textContent = '[ PROCESSING... YOUR BINARY IS BEING ANALYZED ]';
        statusText.style.color = 'var(--cyan)';
    }
    
    uploadMessage.style.display = 'block';
    if (uploadBox) {
        uploadBox.style.display = 'none';
    }
    
    // Set a fallback timer so the message auto-hides even if showUploadStatus is never called
    // (e.g., network hang, server never responds)
    if (uploadMessageTimer !== undefined) {
        clearTimeout(uploadMessageTimer);
    }
    uploadMessageTimer = setTimeout(() => {
        uploadMessageDismissed = true;
        console.log('[UPLOAD] Fallback timer: message dismissed');
        uploadMessage.style.display = 'none';
        if (uploadBox) {
            uploadBox.style.display = 'block';
        }
        setUploadLoading(false);
        resetUploadForm();
    }, 5000); // 5-second fallback
}

/**
 * Show upload status message
 * @param {string} message - The message to display
 * @param {boolean} isSuccess - Whether the upload was successful
 */
function showUploadStatus(message, isSuccess = true) {
    console.log('[UPLOAD] showUploadStatus called:', message, 'isSuccess:', isSuccess);
    
    // If the fallback timer already dismissed the message, don't re-show it
    if (uploadMessageDismissed) {
        console.log('[UPLOAD] Message already dismissed by fallback timer, showing brief toast instead');
        uploadMessageDismissed = false;
        setUploadLoading(false);
        if (isSuccess) {
            Toast.success(message || 'Binary uploaded successfully');
        } else {
            Toast.error(message || 'Upload failed');
        }
        resetUploadForm();
        return;
    }
    
    const uploadMessage = document.getElementById('upload-message');
    const uploadBox = document.getElementById('upload-box');
    
    if (!uploadMessage) {
        console.error('[UPLOAD] showUploadStatus: uploadMessage element not found!');
        return;
    }
    
    // Clear any existing auto-hide timer (e.g., from processing state)
    if (uploadMessageTimer !== undefined) {
        console.log('[UPLOAD] Clearing existing timer:', uploadMessageTimer);
        clearTimeout(uploadMessageTimer);
        uploadMessageTimer = undefined;
    }
    
    const statusText = uploadMessage.querySelector('p:last-child');
    if (statusText) {
        statusText.textContent = isSuccess
            ? `[ SUCCESS: ${message} ]`
            : `[ ERROR: ${message} ]`;
        statusText.style.color = isSuccess ? 'var(--green)' : 'var(--red)';
    }
    
    uploadMessage.style.display = 'block';
    if (uploadBox) {
        uploadBox.style.display = 'none';
    }
    
    // Auto-hide after 5 seconds
    console.log('[UPLOAD] Setting auto-hide timer for 5 seconds');
    uploadMessageTimer = setTimeout(() => {
        console.log('[UPLOAD] Auto-hide timer fired!');
        console.log('[UPLOAD] uploadMessage exists:', !!uploadMessage, 'uploadBox exists:', !!uploadBox);
        uploadMessage.style.display = 'none';
        if (uploadBox) {
            uploadBox.style.display = 'block';
        }
        console.log('[UPLOAD] After setting styles - uploadMessage.display:', uploadMessage.style.display, 'uploadBox.display:', uploadBox ? uploadBox.style.display : 'N/A');
        console.log('[UPLOAD] Computed style uploadMessage:', window.getComputedStyle(uploadMessage).display);
        console.log('[UPLOAD] Computed style uploadBox:', uploadBox ? window.getComputedStyle(uploadBox).display : 'N/A');
        resetUploadForm();
        console.log('[UPLOAD] After resetUploadForm - uploadMessage.display:', uploadMessage.style.display, 'uploadBox.display:', uploadBox ? uploadBox.style.display : 'N/A');
        console.log('[UPLOAD] Computed style uploadMessage after reset:', window.getComputedStyle(uploadMessage).display);
        console.log('[UPLOAD] Computed style uploadBox after reset:', uploadBox ? window.getComputedStyle(uploadBox).display : 'N/A');
    }, 5000);
    console.log('[UPLOAD] New timer ID:', uploadMessageTimer);
}

/**
 * Reset the upload form to initial state
 */
function resetUploadForm() {
    const generateModelCheckbox = document.getElementById('generate-model-checkbox');
    const trainingNameInput = document.getElementById('training-name');
    const predictionNameInput = document.getElementById('prediction-name');
    const mlClassTypeSelect = document.getElementById('ml_class_type');
    const fileInput = document.getElementById('upload-binary');
    
    if (generateModelCheckbox) generateModelCheckbox.checked = false;
    if (trainingNameInput) trainingNameInput.value = '';
    if (predictionNameInput) predictionNameInput.value = '';
    if (mlClassTypeSelect) mlClassTypeSelect.selectedIndex = 0;
    if (fileInput) fileInput.value = '';
    
    changeMlType();
}

/**
 * Validate upload form before submission
 * @returns {boolean} True if valid, false otherwise
 */
function validateUploadForm() {
    const selectedFile = document.getElementById('upload-binary').files[0];
    const generateModelCheckbox = document.getElementById('generate-model-checkbox');
    const predictionModelSelect = document.getElementById('prediction_model_selection');
    const mlClassTypeSelect = document.getElementById('ml_class_type');
    
    // Check if file is selected
    if (!selectedFile) {
        Toast.error('Please select a binary file to upload');
        return false;
    }
    
    // Validate file size (max 100MB)
    const maxSize = 100 * 1024 * 1024;
    if (selectedFile.size > maxSize) {
        Toast.error('File size exceeds 100MB limit');
        return false;
    }
    
    // Validate name field based on mode (training or prediction)
    const isTraining = generateModelCheckbox.checked;
    const nameInput = isTraining
        ? document.getElementById('training-name')
        : document.getElementById('prediction-name');
    if (!nameInput || !nameInput.value.trim()) {
        Toast.error('Please enter a name');
        nameInput?.focus();
        return false;
    }
    
    // Validate model selection for prediction
    if (!isTraining) {
        if (!predictionModelSelect || !predictionModelSelect.value) {
            Toast.error('Please select a model for prediction');
            predictionModelSelect?.focus();
            return false;
        }
    }
    
    // Validate ML class type
    if (!mlClassTypeSelect || !mlClassTypeSelect.value) {
        Toast.error('Please select an ML class type');
        return false;
    }
    
    return true;
}

/**
 * Upload binary file using native fetch API
 */
async function uploadBinary() {
    const t0 = performance.now();
    const log = (msg) => console.log(`[UPLOAD] ${((performance.now() - t0) / 1000).toFixed(2)}s ${msg}`);
    log('uploadBinary() called');
    
    // Validate form before upload
    if (!validateUploadForm()) {
        log('Validation failed, aborting');
        return;
    }
    log('Validation passed');
    
    const formData = new FormData();
    const selectedFile = document.getElementById('upload-binary').files[0];
    const trainingData = document.getElementById('generate-model-checkbox').checked;
    const nameInput = trainingData
        ? document.getElementById('training-name')
        : document.getElementById('prediction-name');
    const nameValue = nameInput ? nameInput.value.trim() : '';
    
    let modelName;
    if (trainingData) {
        modelName = nameValue;
    } else {
        modelName = document.getElementById('prediction_model_selection').value;
    }
    
    const mlClassType = document.getElementById('ml_class_type').value;
    
    formData.append('binary_file', selectedFile);
    formData.append('training_data', trainingData);
    formData.append('model_name', modelName);
    formData.append('name', nameValue);
    formData.append('ml_class_type', mlClassType);
    
    // Set loading state
    setUploadLoading(true);
    
    // Show upload message immediately so user sees feedback during upload
    showUploadProcessing();
    log('showUploadProcessing() done, awaiting fetch...');
    
    try {
        // Explicitly set Accept: application/json to prevent server returning HTML
        // (browser defaults to Accept: */* which triggers HTML response in endpoint)
        const headers = {
            'Accept': 'application/json'
        };
        const csrfToken = getCsrfToken();
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }

        log('Sending fetch request...');
        const response = await fetch('/api/v1/binaries/uploadBinary', {
            method: 'POST',
            headers: headers,
            body: formData
        });
        log(`Fetch complete, status: ${response.status} OK: ${response.ok}`);
        
        const responseText = await response.text();
        log(`Response body received (${responseText.length} chars)`);
        
        if (response.ok) {
            let data;
            try {
                data = JSON.parse(responseText);
            } catch (parseError) {
                console.error('[UPLOAD] Failed to parse response as JSON:', parseError);
                console.error('[UPLOAD] Raw response:', responseText.substring(0, 500));
                // If JSON parsing fails but response is ok, treat as success with generic message
                showUploadStatus('Binary uploaded successfully');
                return;
            }
            showUploadStatus(data.message || 'Binary uploaded successfully');
        } else {
            // Handle specific error responses
            const errorMessage = responseText.includes('CSRF')
                ? 'Security token expired. Please refresh the page and try again.'
                : (responseText.includes('detail') ? JSON.parse(responseText).detail : `Upload failed (${response.status})`);
            
            console.error('[UPLOAD] Server error:', response.status, errorMessage);
            Toast.error(errorMessage);
            showUploadStatus(errorMessage, false);
        }
    } catch (error) {
        console.error('Upload error:', error);
        Toast.error('Network error. Please try again.');
        showUploadStatus('Network error', false);
    } finally {
        setUploadLoading(false);
    }
}

/**
 * Initialize upload page event listeners
 */
function initUploadPage() {
    const generateModelBox = document.getElementById('generate-model-checkbox');
    if (generateModelBox) {
        generateModelBox.checked = true;
        changeMlType();
        
        // Add event listener for checkbox change (replaces inline onclick)
        generateModelBox.addEventListener('change', changeMlType);
    }
    
    // Add event listener for file input change (replaces inline onchange)
    const fileInput = document.getElementById('upload-binary');
    if (fileInput) {
        fileInput.addEventListener('change', () => {
            // Validate file type
            const file = fileInput.files[0];
            if (file) {
                // Check if file is a valid binary type
                const validTypes = ['application/x-executable', 'application/octet-stream', 'application/x-sharedlib'];
                const fileType = file.type || 'application/octet-stream';
                
                if (!validTypes.includes(fileType) && !file.name.match(/\.(exe|dll|so|bin|elf)$/i)) {
                    Toast.warning('File may not be a valid binary. Upload will continue but analysis may fail.');
                }
                // Trigger upload when file is selected
                uploadBinary();
            }
        });
    }
    
    // Drag and drop functionality
    const dropZone = document.getElementById('drop-zone');
    if (!dropZone || !fileInput) return;
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });
    
    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            uploadBinary();
        }
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initUploadPage);
} else {
    initUploadPage();
}
