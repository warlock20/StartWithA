/**
 * CompanyResources - Reusable AJAX module for managing company files and links.
 * All operations are done via fetch() with no page refreshes.
 *
 * Usage:
 *   CompanyResources.open({
 *       companyId: 123,
 *       companyName: 'Apple Inc.',
 *       projectId: 456,        // optional - research project context
 *       stepIndex: 2,          // optional - research step context
 *       defaultTab: 'upload',  // optional - 'list', 'upload', or 'link'
 *   });
 */
const CompanyResources = (() => {
    let modal = null;
    let currentConfig = {};

    function getModal() {
        if (!modal) {
            const el = document.getElementById('companyResourcesModal');
            if (el) modal = new bootstrap.Modal(el);
        }
        return modal;
    }

    function open(options = {}) {
        const m = getModal();
        if (!m) return;

        currentConfig = {
            companyId: options.companyId,
            companyName: options.companyName || '',
            projectId: options.projectId || null,
            stepIndex: options.stepIndex !== undefined ? options.stepIndex : null,
            defaultTab: options.defaultTab || 'list',
        };

        // Update modal title
        document.getElementById('cr-modal-title').textContent =
            currentConfig.companyName ? `${currentConfig.companyName} — Resources` : 'Company Resources';

        // Reset forms and alerts
        resetForms();

        // Load resources list
        loadResources();

        // Activate the requested tab
        if (currentConfig.defaultTab !== 'list') {
            const tabId = currentConfig.defaultTab === 'upload' ? 'cr-tab-upload' : 'cr-tab-link';
            const tabEl = document.getElementById(tabId);
            if (tabEl) {
                const tab = new bootstrap.Tab(tabEl);
                tab.show();
            }
        }

        m.show();
    }

    function resetForms() {
        // Upload form
        const fileInput = document.getElementById('cr-upload-file');
        if (fileInput) fileInput.value = '';
        ['cr-upload-title', 'cr-upload-category', 'cr-upload-date', 'cr-upload-description'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });

        // Link form
        ['cr-link-title', 'cr-link-url', 'cr-link-source', 'cr-link-category', 'cr-link-description'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });

        // Hide all alerts
        ['cr-upload-error', 'cr-upload-success', 'cr-link-error', 'cr-link-success'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('d-none');
        });

        // Reset buttons
        resetButton('cr-upload-btn', '<i class="bi bi-upload me-1"></i>Upload');
        resetButton('cr-link-btn', '<i class="bi bi-link-45deg me-1"></i>Save Link');
    }

    function resetButton(id, html) {
        const btn = document.getElementById(id);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = html;
        }
    }

    async function loadResources() {
        const listEl = document.getElementById('cr-resource-list');
        const loadingEl = document.getElementById('cr-loading');
        const emptyEl = document.getElementById('cr-empty-state');

        listEl.innerHTML = '';
        loadingEl.classList.remove('d-none');
        emptyEl.classList.add('d-none');

        try {
            const params = new URLSearchParams();
            const typeFilter = document.getElementById('cr-filter-type').value;
            if (typeFilter) params.append('type', typeFilter);
            const catFilter = document.getElementById('cr-filter-category').value;
            if (catFilter) params.append('category', catFilter);

            const resp = await fetch(`/companies/api/${currentConfig.companyId}/resources?${params}`);
            const result = await resp.json();

            loadingEl.classList.add('d-none');

            if (result.success) {
                const resources = result.data.resources;
                const categories = result.data.categories;

                document.getElementById('cr-count').textContent = resources.length;
                updateCategoryOptions(categories);

                if (resources.length === 0) {
                    emptyEl.classList.remove('d-none');
                } else {
                    renderResourceList(resources);
                }
            }
        } catch (e) {
            loadingEl.classList.add('d-none');
            listEl.innerHTML = '<div class="text-danger small">Failed to load resources.</div>';
        }
    }

    function updateCategoryOptions(categories) {
        // Update filter dropdown
        const filterSelect = document.getElementById('cr-filter-category');
        const currentValue = filterSelect.value;
        filterSelect.innerHTML = '<option value="">All categories</option>';
        categories.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat;
            opt.textContent = cat;
            if (cat === currentValue) opt.selected = true;
            filterSelect.appendChild(opt);
        });

        // Update datalist for category autocomplete on forms
        const datalist = document.getElementById('cr-category-datalist');
        datalist.innerHTML = '';
        categories.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat;
            datalist.appendChild(opt);
        });
    }

    function renderResourceList(resources) {
        const container = document.getElementById('cr-resource-list');
        container.innerHTML = resources.map(r => {
            const icon = r.resource_type === 'file'
                ? (r.file_type === 'pdf' ? 'bi-file-earmark-pdf-fill text-danger' : 'bi-file-earmark-text-fill text-primary')
                : 'bi-link-45deg text-info';

            const meta = r.resource_type === 'file'
                ? `${r.original_filename} &middot; ${formatFileSize(r.file_size)}`
                : (r.source_name || extractDomain(r.url));

            const categoryBadge = r.category
                ? `<span class="badge bg-light text-dark border ms-1">${escapeHtml(r.category)}</span>`
                : '';

            const dateStr = r.resource_date
                ? `<span class="text-muted ms-1">&middot; ${r.resource_date}</span>`
                : '';

            const titleHtml = r.resource_type === 'link'
                ? `<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener" class="text-decoration-none">${escapeHtml(r.title)} <i class="bi bi-box-arrow-up-right" style="font-size: 0.7em;"></i></a>`
                : escapeHtml(r.title);

            const viewBtn = r.resource_type === 'file'
                ? `<a href="/companies/resources/${r.id}/viewer" target="_blank" class="btn btn-sm btn-outline-secondary border-0" title="View"><i class="bi bi-eye"></i></a>`
                : '';
            const downloadBtn = r.resource_type === 'file'
                ? `<a href="/companies/api/resources/${r.id}/download" class="btn btn-sm btn-outline-primary border-0" title="Download"><i class="bi bi-download"></i></a>`
                : '';
            const actions = viewBtn + downloadBtn;

            return `
                <div class="cr-resource-item d-flex justify-content-between align-items-start py-2 border-bottom">
                    <div class="flex-grow-1 min-width-0">
                        <div class="fw-semibold small">
                            <i class="bi ${icon} me-1"></i>${titleHtml}${categoryBadge}
                        </div>
                        <div class="text-muted" style="font-size: 0.78rem;">
                            ${meta}${dateStr}
                        </div>
                        ${r.description ? `<div class="text-muted small mt-1">${escapeHtml(r.description)}</div>` : ''}
                    </div>
                    <div class="d-flex gap-1 ms-2 flex-shrink-0">
                        ${actions}
                        <button class="btn btn-sm btn-outline-danger border-0" title="Delete"
                                onclick="CompanyResources.deleteResource(${r.id})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    async function uploadFile() {
        const btn = document.getElementById('cr-upload-btn');
        const errorEl = document.getElementById('cr-upload-error');
        const successEl = document.getElementById('cr-upload-success');
        errorEl.classList.add('d-none');
        successEl.classList.add('d-none');

        const fileInput = document.getElementById('cr-upload-file');
        const file = fileInput.files[0];
        if (!file) { showError('cr-upload-error', 'Please select a file.'); return; }

        const title = document.getElementById('cr-upload-title').value.trim();
        if (!title) { showError('cr-upload-error', 'Title is required.'); return; }

        // Loading state
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Uploading...';

        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', title);
        formData.append('category', document.getElementById('cr-upload-category').value.trim());
        formData.append('description', document.getElementById('cr-upload-description').value.trim());
        formData.append('resource_date', document.getElementById('cr-upload-date').value);
        if (currentConfig.projectId) formData.append('project_id', currentConfig.projectId);
        if (currentConfig.stepIndex !== null) formData.append('step_index', currentConfig.stepIndex);

        try {
            const resp = await fetch(`/companies/api/${currentConfig.companyId}/resources/upload`, {
                method: 'POST',
                body: formData,
            });
            const result = await resp.json();

            if (result.success) {
                showSuccess('cr-upload-success', `"${title}" uploaded successfully.`);
                // Reset form fields but keep success message visible
                fileInput.value = '';
                document.getElementById('cr-upload-title').value = '';
                document.getElementById('cr-upload-description').value = '';
                document.getElementById('cr-upload-date').value = '';
                // Refresh the resource list and count
                loadResources();
                // Auto-hide success after 3s
                setTimeout(() => successEl.classList.add('d-none'), 3000);
            } else {
                showError('cr-upload-error', result.message || 'Upload failed.');
            }
        } catch (e) {
            showError('cr-upload-error', 'Network error. Please try again.');
        }

        resetButton('cr-upload-btn', '<i class="bi bi-upload me-1"></i>Upload');
    }

    async function saveLink() {
        const btn = document.getElementById('cr-link-btn');
        const errorEl = document.getElementById('cr-link-error');
        const successEl = document.getElementById('cr-link-success');
        errorEl.classList.add('d-none');
        successEl.classList.add('d-none');

        const title = document.getElementById('cr-link-title').value.trim();
        const url = document.getElementById('cr-link-url').value.trim();
        if (!title) { showError('cr-link-error', 'Title is required.'); return; }
        if (!url) { showError('cr-link-error', 'URL is required.'); return; }

        // Loading state
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving...';

        const payload = {
            title: title,
            url: url,
            source_name: document.getElementById('cr-link-source').value.trim(),
            category: document.getElementById('cr-link-category').value.trim(),
            description: document.getElementById('cr-link-description').value.trim(),
        };
        if (currentConfig.projectId) payload.project_id = currentConfig.projectId;
        if (currentConfig.stepIndex !== null) payload.step_index = currentConfig.stepIndex;

        try {
            const resp = await fetch(`/companies/api/${currentConfig.companyId}/resources/link`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const result = await resp.json();

            if (result.success) {
                showSuccess('cr-link-success', `"${title}" saved successfully.`);
                // Reset form fields
                document.getElementById('cr-link-title').value = '';
                document.getElementById('cr-link-url').value = '';
                document.getElementById('cr-link-source').value = '';
                document.getElementById('cr-link-description').value = '';
                // Refresh the resource list and count
                loadResources();
                // Auto-hide success after 3s
                setTimeout(() => successEl.classList.add('d-none'), 3000);
            } else {
                showError('cr-link-error', result.message || 'Failed to save link.');
            }
        } catch (e) {
            showError('cr-link-error', 'Network error. Please try again.');
        }

        resetButton('cr-link-btn', '<i class="bi bi-link-45deg me-1"></i>Save Link');
    }

    async function deleteResource(resourceId) {
        if (!confirm('Delete this resource?')) return;

        showToast('Deleting…', 'loading');
        try {
            const resp = await fetch(`/companies/api/resources/${resourceId}`, {
                method: 'DELETE',
            });
            const result = await resp.json();

            if (result.success) {
                showToast('Deleted', 'success');
                loadResources();
            } else {
                showToast(result.message || 'Failed to delete resource.', 'danger');
            }
        } catch (e) {
            showToast('Network error. Please try again.', 'danger');
        }
    }

    function showError(elementId, message) {
        const el = document.getElementById(elementId);
        el.textContent = message;
        el.classList.remove('d-none');
    }

    function showSuccess(elementId, message) {
        const el = document.getElementById(elementId);
        el.textContent = message;
        el.classList.remove('d-none');
    }

    function formatFileSize(bytes) {
        if (!bytes) return '';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(1) + ' MB';
    }

    function extractDomain(url) {
        try {
            return new URL(url).hostname.replace('www.', '');
        } catch {
            return url;
        }
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Initialize event listeners when DOM is ready
    function init() {
        const modal = document.getElementById('companyResourcesModal');
        if (!modal) return;

        document.getElementById('cr-filter-type').addEventListener('change', loadResources);
        document.getElementById('cr-filter-category').addEventListener('change', loadResources);
        document.getElementById('cr-upload-btn').addEventListener('click', uploadFile);
        document.getElementById('cr-link-btn').addEventListener('click', saveLink);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return { open, deleteResource };
})();
