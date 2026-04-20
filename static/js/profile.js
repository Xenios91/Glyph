/**
 * GLYPH — PROFILE PAGE (profile.js)
 * Handles user profile updates, password changes, and API key management
 */

// ── API Keys Management ──────────────────────────────────────────

/**
 * Load API keys from the server and display them
 */
async function loadApiKeys() {
    try {
        const response = await fetch('/auth/api-keys', {
            headers: {
                'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content || ''
            }
        });

        if (response.ok) {
            const keys = await response.json();
            const container = document.getElementById('apiKeysList');
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
                        <button class="nes-btn is-error is-small" onclick="deleteApiKey(${key.id})">Delete</button>
                    </div>
                `;
                container.appendChild(div);
            });
        }
    } catch (err) {
        console.error('Error loading API keys:', err);
    }
}

/**
 * Show the create API key modal
 */
function showCreateApiKeyModal() {
    document.getElementById('createApiKeyModal').style.display = 'block';
    document.getElementById('apiKeySecret').style.display = 'none';
    document.getElementById('createApiKeyForm').style.display = 'block';
}

/**
 * Close the create API key modal
 */
function closeCreateApiKeyModal() {
    document.getElementById('createApiKeyModal').style.display = 'none';
}

/**
 * Create a new API key
 */
async function createApiKey(formData) {
    const permissions = Array.from(document.getElementById('key_permissions').selectedOptions).map(o => o.value);

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
                'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content || ''
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
        } else {
            const error = await response.json();
            alert(error.detail || 'Failed to create API key');
        }
    } catch (err) {
        console.error('Error creating API key:', err);
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
                'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content || ''
            }
        });

        if (response.ok) {
            loadApiKeys();
        } else {
            const error = await response.json();
            alert(error.detail || 'Failed to delete API key');
        }
    } catch (err) {
        console.error('Error deleting API key:', err);
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
            location.reload();
        } else {
            const error = await response.json();
            alert(error.detail || 'Failed to update profile');
        }
    } catch (err) {
        console.error('Error updating profile:', err);
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
        alert('Passwords do not match');
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
            alert('Password changed successfully');
            formData.reset();
        } else {
            const error = await response.json();
            alert(error.detail || 'Failed to change password');
        }
    } catch (err) {
        console.error('Error changing password:', err);
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

// ── Event Listeners ──────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
    // Load API keys on page load
    loadApiKeys();

    // Profile form submission
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        profileForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            await updateProfile(formData);
        });
    }

    // Password form submission
    const passwordForm = document.getElementById('passwordForm');
    if (passwordForm) {
        passwordForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            await changePassword(formData);
        });
    }

    // Create API key form submission
    const createApiKeyForm = document.getElementById('createApiKeyForm');
    if (createApiKeyForm) {
        createApiKeyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            await createApiKey(formData);
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
});
