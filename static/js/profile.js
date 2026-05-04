/**
 * GLYPH — PROFILE PAGE (profile.js)
 * Handles user profile updates, password changes, API key management, and tab navigation
 * Uses native fetch API and event listeners
 */
'use strict';

// ── Tab Navigation ──────────────────────────────────────────

/**
 * Switch to a specific tab
 */
function switchTab(tabId, panelId) {
    // Deactivate all tabs
    document.querySelectorAll('.profile-tab').forEach(tab => {
        tab.setAttribute('aria-selected', 'false');
        tab.setAttribute('tabindex', '-1');
    });
    
    // Hide all panels
    document.querySelectorAll('.tab-content').forEach(panel => {
        panel.setAttribute('aria-hidden', 'true');
    });
    
    // Activate selected tab
    const selectedTab = document.getElementById(tabId);
    const selectedPanel = document.getElementById(panelId);
    
    if (selectedTab && selectedPanel) {
        selectedTab.setAttribute('aria-selected', 'true');
        selectedTab.setAttribute('tabindex', '0');
        selectedPanel.setAttribute('aria-hidden', 'false');
        
        // Load API keys if switching to API keys tab
        if (panelId === 'panel-apikeys') {
            loadApiKeys();
        }
    }
}

/**
 * Initialize tab navigation
 */
function initTabNavigation() {
    const tabs = document.querySelectorAll('.profile-tab');
    
    tabs.forEach(tab => {
        // Click handler
        tab.addEventListener('click', () => {
            const panelId = tab.getAttribute('aria-controls');
            const tabId = tab.id;
            switchTab(tabId, panelId);
        });
        
        // Keyboard handler
        tab.addEventListener('keydown', (e) => {
            const tabList = Array.from(document.querySelectorAll('.profile-tab'));
            const currentIndex = tabList.indexOf(tab);
            let newIndex;
            
            switch (e.key) {
                case 'ArrowDown':
                case 'ArrowRight':
                    e.preventDefault();
                    newIndex = (currentIndex + 1) % tabList.length;
                    tabList[newIndex].focus();
                    break;
                    
                case 'ArrowUp':
                case 'ArrowLeft':
                    e.preventDefault();
                    newIndex = (currentIndex - 1 + tabList.length) % tabList.length;
                    tabList[newIndex].focus();
                    break;
                    
                case 'Home':
                    e.preventDefault();
                    tabList[0].focus();
                    break;
                    
                case 'End':
                    e.preventDefault();
                    tabList[tabList.length - 1].focus();
                    break;
                    
                case 'Enter':
                case ' ':
                    e.preventDefault();
                    const panelId = tab.getAttribute('aria-controls');
                    const tabId = tab.id;
                    switchTab(tabId, panelId);
                    break;
            }
        });
    });
}

// ── API Keys Management ──────────────────────────────────────────

/**
 * Load API keys from the server and display them
 */
async function loadApiKeys() {
    const container = document.getElementById('apiKeysList');
    if (!container) return;
    
    container.setAttribute('aria-busy', 'true');
    
    try {
        const response = await fetch('/auth/api-keys', {});

        if (response.ok) {
            const keys = await response.json();
            container.innerHTML = '';

            if (keys.length === 0) {
                const p = document.createElement('p');
                p.className = 'no-api-keys';
                p.textContent = 'No API keys created yet.';
                container.appendChild(p);
            } else {
                keys.forEach(key => {
                    const item = document.createElement('div');
                    item.className = 'api-key-item';

                    // Info section
                    const infoDiv = document.createElement('div');
                    infoDiv.className = 'api-key-info';

                    const nameStrong = document.createElement('strong');
                    nameStrong.textContent = key.name;
                    infoDiv.appendChild(nameStrong);

                    const prefixSpan = document.createElement('span');
                    prefixSpan.className = 'api-key-prefix';
                    prefixSpan.textContent = key.key_prefix + '...';
                    infoDiv.appendChild(prefixSpan);

                    const createdSmall = document.createElement('small');
                    createdSmall.textContent = 'Created: ' + formatDate(key.created_at);
                    infoDiv.appendChild(createdSmall);

                    if (key.expires_at) {
                        const br = document.createElement('br');
                        infoDiv.appendChild(br);

                        const expiresSmall = document.createElement('small');
                        expiresSmall.textContent = 'Expires: ' + formatDate(key.expires_at);
                        infoDiv.appendChild(expiresSmall);
                    }

                    item.appendChild(infoDiv);

                    // Actions section
                    const actionsDiv = document.createElement('div');
                    actionsDiv.className = 'api-key-actions';

                    const deleteBtn = document.createElement('button');
                    deleteBtn.className = 'cyber-btn is-error is-small delete-api-key-btn';
                    deleteBtn.dataset.keyId = key.id;
                    deleteBtn.setAttribute('aria-label', 'Delete API key: ' + key.name);
                    deleteBtn.textContent = 'Delete';
                    actionsDiv.appendChild(deleteBtn);

                    item.appendChild(actionsDiv);
                    container.appendChild(item);
                });
            }
        }
    } catch (err) {
        console.error('Error loading API keys:', err);
        Toast.error('Failed to load API keys');
    } finally {
        container.setAttribute('aria-busy', 'false');
    }
}

/**
 * Show the create API key modal
 */
function showCreateApiKeyModal() {
    const modal = document.getElementById('createApiKeyModal');
    const secretDiv = document.getElementById('apiKeySecret');
    const form = document.getElementById('createApiKeyForm');
    
    if (modal) {
        modal.style.display = 'flex';
    }
    if (secretDiv) {
        secretDiv.style.display = 'none';
        secretDiv.innerHTML = '';
    }
    if (form) {
        form.style.display = 'block';
        form.reset();
    }
}

/**
 * Close the create API key modal
 */
function closeCreateApiKeyModal() {
    const modal = document.getElementById('createApiKeyModal');
    if (modal) {
        modal.style.display = 'none';
    }
    // Check if we're on the API keys tab and refresh the list
    const apiKeysPanel = document.getElementById('panel-apikeys');
    if (apiKeysPanel && apiKeysPanel.getAttribute('aria-hidden') === 'false') {
        loadApiKeys();
    }
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
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            const result = await response.json();
            // Hide form and show the secret
            document.getElementById('createApiKeyForm').style.display = 'none';
            const secretDiv = document.getElementById('apiKeySecret');
            secretDiv.style.display = 'block';
            secretDiv.innerHTML = '';
            const alertP = document.createElement('p');
            alertP.className = 'api-key-secret-alert';
            alertP.textContent = '\u26A0\uFE0F Copy this key now - it won\'t be shown again!';
            secretDiv.appendChild(alertP);
            const codeEl = document.createElement('code');
            codeEl.className = 'api-key-secret-code';
            codeEl.textContent = result.secret;
            secretDiv.appendChild(codeEl);
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
            method: 'DELETE'
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
                'Content-Type': 'application/json'
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
                'Content-Type': 'application/json'
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
    // Initialize tab navigation
    initTabNavigation();

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
                    submitBtn.textContent = 'Create Key';
                }
            }
        });
    }

    // Delete API key buttons (event delegation)
    const apiKeysList = document.getElementById('apiKeysList');
    if (apiKeysList) {
        apiKeysList.addEventListener('click', (e) => {
            if (e.target.classList.contains('delete-api-key-btn')) {
                const keyId = parseInt(e.target.dataset.keyId);
                deleteApiKey(keyId);
            }
        });
    }

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
            showToast(enabled ? 'Dyslexia-friendly font enabled' : 'Dyslexia-friendly font disabled', 'info');
        });
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initProfilePage);
} else {
    initProfilePage();
}
