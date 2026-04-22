/**
 * GLYPH — PROFILE PAGE (profile.js)
 * Handles user profile updates, password changes, and API key management
 * Uses native fetch API and event listeners
 */

// ── API Keys Management ──────────────────────────────────────────

/**
 * Load API keys from the server and display them
 */
async function loadApiKeys() {
    try {
        const response = await fetch('/auth/api-keys', {
            headers: {
                'X-CSRF-Token': getCsrfToken() || ''
            }
        });

        if (response.ok) {
            const keys = await response.json();
            const container = document.getElementById('apiKeysList');
            if (!container) return;
            
            container.innerHTML = '';

            if (keys.length === 0) {
                container.innerHTML = '<p class="no-api-keys">No API keys created yet.</p>';
                return;
            }

            keys.forEach(key => {
                const div = document.createElement('div');
                div.className = 'api-key-item';
                div.innerHTML = `
                    <div class="api-key-info">
                        <strong>${escapeHtml(key.name)}</strong><br>
                        <span class="api-key-prefix">${escapeHtml(key.key_prefix)}...</span><br>
                        <small>Created: ${formatDate(key.created_at)}</small>
                        ${key.expires_at ? `<br><small>Expires: ${formatDate(key.expires_at)}</small>` : ''}
                    </div>
                    <div class="api-key-actions">
                        <button class="cyber-btn is-error is-small delete-api-key-btn" data-key-id="${key.id}">Delete</button>
                    </div>
                `;
                container.appendChild(div);
            });
        }
    } catch (err) {
        console.error('Error loading API keys:', err);
        Toast.error('Failed to load API keys');
    }
}

/**
 * Show the create API key modal
 */
function showCreateApiKeyModal() {
    const modal = document.getElementById('createApiKeyModal');
    const secretDiv = document.getElementById('apiKeySecret');
    const form = document.getElementById('createApiKeyForm');
    
    if (modal) modal.style.display = 'block';
    if (secretDiv) secretDiv.style.display = 'none';
    if (form) form.style.display = 'block';
}

/**
 * Close the create API key modal
 */
function closeCreateApiKeyModal() {
    const modal = document.getElementById('createApiKeyModal');
    if (modal) modal.style.display = 'none';
}

/**
 * Create a new API key
 */
async function createApiKey(formData) {
    const permissionsSelect = document.getElementById('key_permissions');
    const permissions = Array.from(permissionsSelect.selectedOptions).map(o => o.value);

    const data = {
        name: formData.get('name'),
        permissions: permissions,
        expires_days: formData.get('expires_days') ? parseInt(formData.get('expires_days')) : null
    };

    try {
        const response = await fetch('/auth/api-keys', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCsrfToken() || ''
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            const result = await response.json();
            // Show the secret
            document.getElementById('createApiKeyForm').style.display = 'none';
            const secretDiv = document.getElementById('apiKeySecret');
            secretDiv.style.display = 'block';
            secretDiv.innerHTML = `
                <p class="api-key-secret-alert">⚠️ Copy this key now - it won't be shown again!</p>
                <code class="api-key-secret-code">${escapeHtml(result.secret)}</code>
            `;
            Toast.success('API key created successfully!');
        } else {
            const error = await response.json();
            Toast.error(error.detail || 'Failed to create API key');
        }
    } catch (err) {
        console.error('Error creating API key:', err);
        Toast.error('Network error. Please try again.');
    }
}

/**
 * Delete an API key
 */
async function deleteApiKey(keyId) {
    if (!confirm('Are you sure you want to delete this API key?')) {
        return;
    }

    try {
        const response = await fetch(`/auth/api-keys/${keyId}`, {
            method: 'DELETE',
            headers: {
                'X-CSRF-Token': getCsrfToken() || ''
            }
        });

        if (response.ok) {
            Toast.success('API key deleted successfully');
            loadApiKeys();
        } else {
            const error = await response.json();
            Toast.error(error.detail || 'Failed to delete API key');
        }
    } catch (err) {
        console.error('Error deleting API key:', err);
        Toast.error('Network error. Please try again.');
    }
}

// ── Profile Management ──────────────────────────────────────────

/**
 * Update user profile
 */
async function updateProfile(formData) {
    const data = {
        full_name: formData.get('full_name') || null,
        email: formData.get('email')
    };

    try {
        const response = await fetch('/auth/update-profile', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': formData.get('csrf_token')
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            Toast.success('Profile updated successfully');
            location.reload();
        } else {
            const error = await response.json();
            showError('profile-error', error.detail || 'Failed to update profile');
            Toast.error(error.detail || 'Failed to update profile');
        }
    } catch (err) {
        console.error('Error updating profile:', err);
        showError('profile-error', 'Network error. Please try again.');
        Toast.error('Network error. Please try again.');
    }
}

// ── Password Management ──────────────────────────────────────────

/**
 * Change user password
 */
async function changePassword(formData) {
    const newPassword = formData.get('new_password');
    const confirmPassword = formData.get('confirm_password');

    if (newPassword !== confirmPassword) {
        showError('password-error', 'Passwords do not match');
        Toast.error('Passwords do not match');
        return;
    }

    const data = {
        current_password: formData.get('current_password'),
        new_password: newPassword
    };

    try {
        const response = await fetch('/auth/change-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': formData.get('csrf_token')
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            Toast.success('Password changed successfully');
            formData.reset();
            hideError('password-error');
        } else {
            const error = await response.json();
            showError('password-error', error.detail || 'Failed to change password');
            Toast.error(error.detail || 'Failed to change password');
        }
    } catch (err) {
        console.error('Error changing password:', err);
        showError('password-error', 'Network error. Please try again.');
        Toast.error('Network error. Please try again.');
    }
}

// ── Utility Functions ──────────────────────────────────────────

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format a date string
 */
function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString();
}

/**
 * Show error message
 */
function showError(elementId, message) {
    const errorDiv = document.getElementById(elementId);
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    }
}

/**
 * Hide error message
 */
function hideError(elementId) {
    const errorDiv = document.getElementById(elementId);
    if (errorDiv) {
        errorDiv.style.display = 'none';
    }
}

// ── Event Listeners ──────────────────────────────────────────

/**
 * Initialize profile page event listeners
 */
function initProfilePage() {
    // Load API keys on page load
    loadApiKeys();

    // Profile form submission
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        profileForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const submitBtn = document.getElementById('profile-submit-btn');
            
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Updating...';
            }
            
            try {
                await updateProfile(formData);
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Update Profile';
                }
            }
        });
    }

    // Password form submission
    const passwordForm = document.getElementById('passwordForm');
    if (passwordForm) {
        passwordForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const submitBtn = document.getElementById('password-submit-btn');
            
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Changing...';
            }
            
            try {
                await changePassword(formData);
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Change Password';
                }
            }
        });
    }

    // Create API key button
    const createApiKeyBtn = document.getElementById('create-api-key-btn');
    if (createApiKeyBtn) {
        createApiKeyBtn.addEventListener('click', showCreateApiKeyModal);
    }

    // Cancel create API key button
    const cancelCreateKeyBtn = document.getElementById('cancel-create-key-btn');
    if (cancelCreateKeyBtn) {
        cancelCreateKeyBtn.addEventListener('click', closeCreateApiKeyModal);
    }

    // Create API key form submission
    const createApiKeyForm = document.getElementById('createApiKeyForm');
    if (createApiKeyForm) {
        createApiKeyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const submitBtn = document.getElementById('create-key-submit-btn');
            
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Creating...';
            }
            
            try {
                await createApiKey(formData);
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Create';
                }
            }
        });
    }

    // Delete API key buttons (event delegation)
    document.getElementById('apiKeysList').addEventListener('click', (e) => {
        if (e.target.classList.contains('delete-api-key-btn')) {
            const keyId = parseInt(e.target.dataset.keyId);
            deleteApiKey(keyId);
        }
    });

    // Close modal when clicking outside
    const modal = document.getElementById('createApiKeyModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeCreateApiKeyModal();
            }
        });
    }

    // Close modal with Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeCreateApiKeyModal();
        }
    });

    // ── Accessibility: Dyslexia Font Toggle ──────────────────────────────────────────

    /**
     * Toggle dyslexia-friendly font mode
     */
    const dyslexiaToggle = document.getElementById('dyslexia-font-toggle');
    if (dyslexiaToggle) {
        // Check localStorage on load
        const savedPreference = localStorage.getItem('dyslexia_font');
        if (savedPreference === 'true') {
            dyslexiaToggle.checked = true;
            document.body.classList.add('font-dyslexia');
        }

        // Handle toggle change
        dyslexiaToggle.addEventListener('change', function() {
            const enabled = this.checked;
            
            // Apply font class to body
            if (enabled) {
                document.body.classList.add('font-dyslexia');
            } else {
                document.body.classList.remove('font-dyslexia');
            }
            
            // Save preference to localStorage
            localStorage.setItem('dyslexia_font', enabled);
            
            // Show toast notification
            Toast.info(enabled ? 'Dyslexia-friendly font enabled' : 'Dyslexia-friendly font disabled');
        });
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initProfilePage);
} else {
    initProfilePage();
}
