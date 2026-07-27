/**
 * SendToSector - Reusable module for sending company research insights to sector notebooks.
 *
 * Usage:
 *   SendToSector.open({
 *       companyId: 123,
 *       companyName: 'Apple Inc.',
 *       sectorName: 'Technology',       // optional, pre-fills sector input
 *       content: 'Selected text...',     // optional, pre-fills content
 *       sourcePage: 'free_research',     // which page triggered this
 *       sourceDetail: 'Step 3 - Moat'   // extra context for the source
 *   });
 */
const SendToSector = (() => {
    let autocompleteTimeout = null;
    let modal = null;

    function getModal() {
        if (!modal) {
            const el = document.getElementById('sendToSectorModal');
            if (el) modal = new bootstrap.Modal(el);
        }
        return modal;
    }

    function open(options = {}) {
        const m = getModal();
        if (!m) return;

        // Reset to form state
        document.getElementById('sts-form-state').classList.remove('d-none');
        document.getElementById('sts-success-state').classList.add('d-none');
        document.getElementById('sts-error').classList.add('d-none');

        // Reset form fields
        document.getElementById('sts-sector-name').value = options.sectorName || '';
        document.getElementById('sts-title').value = '';
        document.getElementById('sts-content').value = options.content || '';
        document.getElementById('sts-context').value = '';
        document.getElementById('sts-company-id').value = options.companyId || '';
        document.getElementById('sts-source-page').value = options.sourcePage || '';
        document.getElementById('sts-source-detail').value = options.sourceDetail || '';

        // Reset section dropdown
        const sectionSelect = document.getElementById('sts-section');
        sectionSelect.innerHTML = '<option value="">Inbox (unsorted)</option>';

        // Reset submit button
        const btn = document.getElementById('sts-submit-btn');
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-arrow-up-right"></i> Send';

        // If sector is pre-filled, fetch its sections
        if (options.sectorName) {
            fetchSections(options.sectorName);
        }

        m.show();
    }

    function initAutocomplete() {
        const input = document.getElementById('sts-sector-name');
        if (!input) return;

        input.addEventListener('input', () => {
            clearTimeout(autocompleteTimeout);
            const query = input.value.trim();

            if (query.length < 1) {
                hideAutocomplete();
                return;
            }

            autocompleteTimeout = setTimeout(() => {
                fetchAutocomplete(query);
            }, 250);
        });

        // Close autocomplete on click outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#sts-sector-name') && !e.target.closest('#sts-autocomplete-list')) {
                hideAutocomplete();
            }
        });

        // Fetch sections when sector input loses focus (for typed new names)
        input.addEventListener('blur', () => {
            setTimeout(() => {
                const name = input.value.trim();
                if (name) fetchSections(name);
            }, 300);
        });
    }

    async function fetchAutocomplete(query) {
        try {
            const resp = await fetch(`/sectors/api/sectors/autocomplete?q=${encodeURIComponent(query)}&limit=6`);
            if (!resp.ok) return;
            const sectors = await resp.json();
            renderAutocomplete(sectors, query);
        } catch (e) {
            // Silently fail autocomplete
        }
    }

    function renderAutocomplete(sectors, query) {
        const list = document.getElementById('sts-autocomplete-list');

        if (sectors.length === 0) {
            list.innerHTML = `<div class="sts-autocomplete-item sts-autocomplete-new">
                <i class="bi bi-plus-circle me-2"></i> Create "<strong>${escapeHtml(query)}</strong>" notebook
            </div>`;
            list.style.display = 'block';

            list.querySelector('.sts-autocomplete-new').addEventListener('click', () => {
                document.getElementById('sts-sector-name').value = query;
                hideAutocomplete();
                // New sector — no sections to fetch
                const sectionSelect = document.getElementById('sts-section');
                sectionSelect.innerHTML = '<option value="">Inbox (unsorted)</option>';
            });
            return;
        }

        list.innerHTML = sectors.map(s => `
            <div class="sts-autocomplete-item" data-name="${escapeHtml(s.display_name)}">
                ${s.icon ? `<span class="me-2">${s.icon}</span>` : '<i class="bi bi-folder me-2"></i>'}
                ${escapeHtml(s.display_name)}
                ${s.total_companies ? `<small class="text-muted ms-auto">${s.total_companies} companies</small>` : ''}
            </div>
        `).join('');

        list.style.display = 'block';

        // Bind click handlers
        list.querySelectorAll('.sts-autocomplete-item').forEach(item => {
            item.addEventListener('click', () => {
                const name = item.dataset.name;
                document.getElementById('sts-sector-name').value = name;
                hideAutocomplete();
                fetchSections(name);
            });
        });
    }

    function hideAutocomplete() {
        const list = document.getElementById('sts-autocomplete-list');
        if (list) list.style.display = 'none';
    }

    async function fetchSections(sectorName) {
        const sectionSelect = document.getElementById('sts-section');

        try {
            const resp = await fetch(`/sectors/api/sector-sections?sector_name=${encodeURIComponent(sectorName)}`);
            if (!resp.ok) return;
            const sections = await resp.json();

            sectionSelect.innerHTML = '';
            if (sections.length === 0) {
                sectionSelect.innerHTML = '<option value="">Inbox (unsorted)</option>';
            } else {
                sections.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.id;
                    opt.textContent = `${s.icon || ''} ${s.title}`.trim();
                    sectionSelect.appendChild(opt);
                });
            }
        } catch (e) {
            // Keep default inbox option
        }
    }

    async function submit() {
        const btn = document.getElementById('sts-submit-btn');
        const errorEl = document.getElementById('sts-error');
        errorEl.classList.add('d-none');

        const sectorName = document.getElementById('sts-sector-name').value.trim();
        const title = document.getElementById('sts-title').value.trim();
        const content = document.getElementById('sts-content').value.trim();

        // Client-side validation
        if (!sectorName) return showError('Please enter a sector name.');
        if (!title) return showError('Please enter a title.');
        if (!content) return showError('Please enter content.');

        // Loading state
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Sending...';

        const payload = {
            sector_name: sectorName,
            title: title,
            content: content,
            company_id: parseInt(document.getElementById('sts-company-id').value),
            section_id: document.getElementById('sts-section').value || null,
            context_note: document.getElementById('sts-context').value.trim(),
            source_page: document.getElementById('sts-source-page').value,
            source_detail: document.getElementById('sts-source-detail').value
        };

        try {
            const resp = await fetch('/sectors/api/send-to-sector', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await resp.json();

            if (!resp.ok) {
                showError(data.error || 'Failed to send. Please try again.');
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-arrow-up-right"></i> Send';
                return;
            }

            // Show success state
            document.getElementById('sts-form-state').classList.add('d-none');
            document.getElementById('sts-success-state').classList.remove('d-none');
            document.getElementById('sts-success-sector-name').textContent = data.sector.display_name;
            document.getElementById('sts-success-link').href = data.sector.notebook_url;

        } catch (e) {
            showError('Network error. Please check your connection.');
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-arrow-up-right"></i> Send';
        }
    }

    function showError(message) {
        const el = document.getElementById('sts-error');
        el.textContent = message;
        el.classList.remove('d-none');
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Initialize autocomplete when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAutocomplete);
    } else {
        initAutocomplete();
    }

    return { open, submit };
})();
