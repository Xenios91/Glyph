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
 * Show upload status message
 * @param {string} message - The message to display
 * @param {boolean} isSuccess - Whether the upload was successful
 */
function showUploadStatus(message, isSuccess = true) {
    const uploadMessage = document.getElementById('upload-message');
    const uploadBox = document.getElementById('upload-box');
    
    if (!uploadMessage) return;
    
    const statusText = uploadMessage.querySelector('p:last-child');
    if (statusText) {
        statusText.textContent = isSuccess 
            ? `[ SUCCESS: ${message} ]`
            : `[ ERROR: ${message} ]`;
        statusText.style.color = isSuccess ? 'var(--green)' : 'var(--red)';
    }
    
    uploadMessage.style.display = 'block';
    uploadBox.style.display = 'none';
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        uploadMessage.style.display = 'none';
        uploadBox.style.display = 'block';
        resetUploadForm();
    }, 5000);
}

/**
 * Reset the upload form to initial state
 */
function resetUploadForm() {
    const generateModelCheckbox = document.getElementById('generate-model-checkbox');
    const modelNameInput = document.getElementById('model_name');
    const mlClassTypeSelect = document.getElementById('ml_class_type');
    const fileInput = document.getElementById('upload-binary');
    
    if (generateModelCheckbox) generateModelCheckbox.checked = false;
    if (modelNameInput) modelNameInput.value = '';
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
    const modelNameInput = document.getElementById('model_name');
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
    
    // Validate model name for training
    if (generateModelCheckbox.checked) {
        if (!modelNameInput || !modelNameInput.value.trim()) {
            Toast.error('Please enter a model name');
            modelNameInput?.focus();
            return false;
        }
    } else {
        // Validate model selection for prediction
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
    // Validate form before upload
    if (!validateUploadForm()) {
        return;
    }
    
    const formData = new FormData();
    const selectedFile = document.getElementById('upload-binary').files[0];
    const trainingData = document.getElementById('generate-model-checkbox').checked;
    let modelName;
    
    if (trainingData) {
        modelName = document.getElementById('model_name').value;
    } else {
        modelName = document.getElementById('prediction_model_selection').value;
    }
    
    const taskElement = document.getElementById('task_name');
    const taskNameValue = taskElement ? taskElement.value.trim() : '';
    if (taskNameValue !== '') {
        formData.append('task_name', taskNameValue);
    }
    
    const mlClassType = document.getElementById('ml_class_type').value;
    
    formData.append('binary_file', selectedFile);
    formData.append('training_data', trainingData);
    formData.append('model_name', modelName);
    formData.append('ml_class_type', mlClassType);
    
    // Set loading state
    setUploadLoading(true);
    
    try {
        const response = await fetch('/api/v1/binaries/uploadBinary', {
            method: 'POST',
            headers: getFetchOptionsWithCsrf({}).headers,
            body: formData
        });
        
        const responseText = await response.text();
        
        if (response.ok) {
            let data;
            try {
                data = JSON.parse(responseText);
            } catch (parseError) {
                console.error('[UPLOAD] Failed to parse response as JSON:', parseError);
                // If JSON parsing fails but response is ok, treat as success with generic message
                showUploadStatus('Binary uploaded successfully');
                return;
            }
            showUploadStatus(data.message || 'Binary uploaded successfully');
        } else {
            // Handle specific error responses
            const errorData = await response.json().catch(() => ({}));
            const errorMessage = errorData.detail || errorData.message || 'Upload failed';
            
            if (response.status === 400) {
                Toast.error(errorMessage);
                showUploadStatus(errorMessage, false);
            } else {
                Toast.error(`Server error: ${response.status}`);
                showUploadStatus(errorMessage, false);
            }
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
