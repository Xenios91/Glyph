/**
 * Glyph - Upload Page JavaScript
 * Handles binary upload and ML type switching
 */

/**
 * Change ML type between training and prediction modes
 */
function changeMlType() {
    const generate_model_box = document.getElementById('generate-model-checkbox');
    const prediction_div = document.getElementById('prediction-config');
    const training_div = document.getElementById('training-config');
    
    if (!prediction_div) {
        if (generate_model_box) generate_model_box.checked = true;
        if (training_div) training_div.style.display = 'block';
        if (training_div) training_div.classList.remove('hidden');
        return;
    }
    
    if (generate_model_box.checked) {
        // Fade out prediction, fade in training
        prediction_div.classList.add('hidden');
        setTimeout(() => {
            prediction_div.style.display = 'none';
            training_div.style.display = 'block';
            // Small delay to allow display:block to apply before removing hidden
            setTimeout(() => {
                training_div.classList.remove('hidden');
            }, 10);
        }, 300);
    } else {
        // Fade out training, fade in prediction
        training_div.classList.add('hidden');
        setTimeout(() => {
            training_div.style.display = 'none';
            prediction_div.style.display = 'block';
            // Small delay to allow display:block to apply before removing hidden
            setTimeout(() => {
                prediction_div.classList.remove('hidden');
            }, 10);
        }, 300);
    }
}

/**
 * Upload binary file
 */
function uploadBinary() {
    var formData = new FormData();
    const selectedFile = document.getElementById('upload-binary').files[0];
    const trainingData = document.getElementById('generate-model-checkbox').checked;
    var modelName;
    
    if (trainingData) {
        modelName = document.getElementById('model_name').value;
    } else {
        modelName = document.getElementById('prediction_model_selection').value;
    }
    
    const taskElement = document.getElementById('task_name');
    if (taskElement != null && taskElement.value.trim() !== '') {
        const taskName = taskElement.value;
        formData.append('task_name', taskName);
    }
    const mlClassType = document.getElementById('ml_class_type').value;
    
    const url = '/api/v1/binaries/uploadBinary';
    
    formData.append('binary_file', selectedFile);
    formData.append('training_data', trainingData);
    formData.append('model_name', modelName);
    formData.append('ml_class_type', mlClassType);
    
    const csrfToken = getCsrfToken();
    
    $.ajax({
        type: 'POST',
        url: url,
        data: formData,
        processData: false,
        contentType: false,
        headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {},
        success: function (data, status, xhr) {
            var uploadMessage = document.getElementById('upload-message');
            var uploadBox = document.getElementById('upload-box');
            uploadMessage.style.display = 'block';
            uploadBox.style.display = 'none';
            setTimeout(function () {
                uploadMessage.style.display = 'none';
                uploadBox.style.display = 'block';
                document.getElementById('generate-model-checkbox').checked = false;
                document.getElementById('model_name').value = '';
                document.getElementById('ml_class_type').value = '';
                changeMlType();
            }, 5000);
        },
        error: function (xhr, status, error) {
            if (xhr.status == 400) {
                window.location.href = '/error?type=uploadError';
            } else {
                window.location.href = '/error';
            }
        },
        complete: function (xhr, textStatus) {
            console.log('upload complete');
        }
    });
}

/**
 * Initialize upload page
 */
function initUploadPage() {
    const generate_model_box = document.getElementById('generate-model-checkbox');
    if (generate_model_box) {
        generate_model_box.checked = true;
        changeMlType();
    }
    
    // Drag and drop functionality
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('upload-binary');
    
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
