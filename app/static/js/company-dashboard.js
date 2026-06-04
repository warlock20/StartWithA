/**
 * Company Dashboard — Main JS logic for the company detail page.
 *
 * Reads configuration from window.companyConfig (set by the template):
 *   - companyId, currencySymbol, priceStale, isPortfolio
 *   - notesGetUrl, notesSaveUrl
 *   - transactions (array of {id, date, type, shares, price, total, notes})
 */
(function () {
    'use strict';

    const cfg = window.companyConfig || {};
    const companyId = cfg.companyId;
    const companyName = cfg.companyName || '';
    const currencySymbol = cfg.currencySymbol || '$';

    // ---- Lazy-init flags ----
    let notesInitialized = false;
    let journalInitialized = false;
    let transactionsInitialized = false;
    let qaInitialized = false;
    let annotationsInitialized = false;

    // ===================================================================
    //  Lazy Initialization (listens to React TabRouter events)
    // ===================================================================

    document.addEventListener('DOMContentLoaded', function () {
        // ---- Lazy-init via React TabRouter custom events ----
        // Tab switching, hash routing, sub-section toggling, and collapsible
        // section detection are now handled by the TabRouter React island.
        // This file listens for its custom events to trigger lazy initialization.

        document.addEventListener('tab-changed', function (e) {
            var tabId = e.detail.tabId;
            if (tabId === 'transactions' && !transactionsInitialized) {
                initTransactionsTable();
                transactionsInitialized = true;
            }
        });

        document.addEventListener('library-section-changed', function (e) {
            var sectionId = e.detail.sectionId;
            if (sectionId === 'notes' && !notesInitialized) {
                initNotesEditor();
                notesInitialized = true;
            }
            if (sectionId === 'journal' && !journalInitialized) {
                var mount = document.getElementById('journal-entries-mount');
                if (mount && window.initJournalEntries) {
                    window.initJournalEntries('journal-entries-mount', {
                        companyId: companyId,
                        newEntryUrl: mount.dataset.newEntryUrl
                    });
                }
                journalInitialized = true;
            }
            if (sectionId === 'annotations' && !annotationsInitialized) {
                if (window.initCompanyAnnotationsPanel) {
                    window.initCompanyAnnotationsPanel('company-annotations-mount', {
                        companyId: companyId
                    });
                }
                annotationsInitialized = true;
            }
        });

        document.addEventListener('research-section-changed', function (e) {
            var sectionId = e.detail.sectionId;
            if (sectionId === 'qa' && !qaInitialized) {
                if (window.initStandaloneQA) {
                    window.initStandaloneQA('standalone-qa-mount', {
                        companyId: companyId,
                        companyName: companyName
                    });
                }
                qaInitialized = true;
            }
        });

        // ---- Async Price Refresh (portfolio companies) ----
        if (cfg.priceStale) {
            fetch('/portfolio/api/refresh-position/' + companyId, { method: 'POST' })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        var p = data.position;
                        var displayPrice = p.current_price_base !== null ? p.current_price_base : p.current_price;
                        document.getElementById('posPrice').textContent = currencySymbol + (displayPrice !== null ? displayPrice.toFixed(2) : '--');
                        document.getElementById('posPriceSub').textContent = 'Updated just now';
                        if (p.current_value !== null) {
                            document.getElementById('posValue').textContent = currencySymbol + Math.round(p.current_value).toLocaleString();
                        }
                        if (p.gain_loss !== null) {
                            var sign = p.gain_loss >= 0 ? '+' : '';
                            document.getElementById('posPLValue').textContent = sign + currencySymbol + Math.round(Math.abs(p.gain_loss)).toLocaleString();
                            document.getElementById('posPLValue').className = 'position-metric-value ' + (p.gain_loss >= 0 ? 'gain' : 'loss');
                            document.getElementById('posPLCard').className = 'position-metric highlight ' + (p.gain_loss >= 0 ? 'gain' : 'loss');
                        }
                        if (p.gain_loss_pct !== null) {
                            var pctSign = p.gain_loss_pct >= 0 ? '+' : '';
                            document.getElementById('posPLPct').textContent = pctSign + p.gain_loss_pct.toFixed(1) + '%';
                        }
                    }
                })
                .catch(function () { /* silent — stale price stays */ });
        }

        // ---- Timeline Filter Sub-Tabs ----
        const timelineFilterTabs = document.querySelectorAll('#timelineFilterTabs .journey-tab');
        const timelineItems = document.querySelectorAll('.journey-item');

        timelineFilterTabs.forEach(filterTab => {
            filterTab.addEventListener('click', function () {
                const filter = this.dataset.filter;
                if (!filter) return;

                timelineFilterTabs.forEach(t => t.classList.remove('active'));
                this.classList.add('active');

                timelineItems.forEach(item => {
                    const itemType = item.getAttribute('data-type');
                    item.style.display = (filter === 'all' || itemType === filter) ? 'block' : 'none';
                });
            });
        });

        // ---- Settings Form + Ticker Testing ----
        // Now handled by React island (settings-form.bundle.js).
        // Mounts eagerly via DOMContentLoaded in the template.

        // ---- SEC Filings Fetch + Polling (Documents tab) ----
        var secBtn = document.getElementById('fetch-sec-btn');
        var secStatus = document.getElementById('sec-fetch-status');

        if (secBtn) {
            secBtn.addEventListener('click', function () {
                var cid = this.getAttribute('data-company-id');
                var filingType = document.getElementById('sec-filing-type');
                var yearsEl = document.getElementById('sec-filing-years');
                var type = filingType ? filingType.value : '10-K';
                var years = yearsEl ? parseInt(yearsEl.value, 10) : 5;

                secBtn.disabled = true;
                secBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Starting...';
                secStatus.classList.remove('d-none');
                secStatus.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Submitting request...';

                fetch('/companies/' + cid + '/fetch_sec_filings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filing_type: type, years: years })
                })
                    .then(function (response) {
                        if (!response.ok) throw new Error('HTTP ' + response.status);
                        return response.json();
                    })
                    .then(function (data) {
                        if (data.success) {
                            secStatus.innerHTML =
                                '<span class="spinner-border spinner-border-sm me-2"></span>' +
                                '<span>Fetching ' + type + ' filings (' + years + ' yrs)&hellip; This may take a moment.</span>';
                            secBtn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Fetching...';
                            pollTaskStatus(data.task_id, secStatus, secBtn, {
                                label: 'SEC filings fetch',
                                btnResetHtml: '<i class="bi bi-cloud-download me-1"></i>Fetch',
                                onSuccess: function () {
                                    document.dispatchEvent(new CustomEvent('resources-changed'));
                                }
                            });
                        } else {
                            secStatus.innerHTML = '<i class="bi bi-exclamation-circle text-danger me-1"></i>' +
                                '<span class="text-danger">' + (data.error || 'Failed to start fetch') + '</span>';
                            secBtn.disabled = false;
                            secBtn.innerHTML = '<i class="bi bi-cloud-download me-1"></i>Fetch';
                        }
                    })
                    .catch(function () {
                        secStatus.innerHTML = '<i class="bi bi-exclamation-circle text-danger me-1"></i>' +
                            '<span class="text-danger">Failed to start SEC fetch. Please try again.</span>';
                        secBtn.disabled = false;
                        secBtn.innerHTML = '<i class="bi bi-cloud-download me-1"></i>Fetch';
                    });
            });
        }

        // ---- Generic task polling ----
        function pollTaskStatus(taskId, statusDiv, btn, opts) {
            opts = opts || {};
            var label = opts.label || 'Task';
            var btnResetHtml = opts.btnResetHtml || btn.innerHTML;
            var onSuccess = opts.onSuccess || null;
            var failCount = 0;
            var maxFails = 5;

            var pollInterval = setInterval(function () {
                fetch('/research/workflow/task_status/' + taskId)
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        failCount = 0;
                        if (data.state === 'SUCCESS') {
                            statusDiv.innerHTML = '<i class="bi bi-check-circle text-success me-1"></i>' +
                                '<span class="text-success">' + label + ' completed!</span>';
                            btn.disabled = false;
                            btn.innerHTML = btnResetHtml;
                            clearInterval(pollInterval);
                            if (onSuccess) onSuccess();
                            setTimeout(function () { statusDiv.classList.add('d-none'); }, 5000);
                        } else if (data.state === 'FAILURE') {
                            statusDiv.innerHTML = '<i class="bi bi-x-circle text-danger me-1"></i>' +
                                '<span class="text-danger">' + label + ' failed: ' +
                                (data.status_message || 'Unknown error') + '</span>';
                            btn.disabled = false;
                            btn.innerHTML = btnResetHtml;
                            clearInterval(pollInterval);
                        } else {
                            statusDiv.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>' +
                                '<span>' + (data.status_message || label + ' in progress...') + '</span>';
                        }
                    })
                    .catch(function () {
                        failCount++;
                        if (failCount >= maxFails) {
                            statusDiv.innerHTML = '<i class="bi bi-exclamation-triangle text-warning me-1"></i>' +
                                '<span>Cannot check status. Task continues in background.</span>';
                            btn.disabled = false;
                            btn.innerHTML = btnResetHtml;
                            clearInterval(pollInterval);
                        }
                    });
            }, 2000);
        }
    }); // end DOMContentLoaded

    // ===================================================================
    //  Collapsible Toggle (global — used by onclick in templates)
    // ===================================================================

    window.toggleCollapsible = function (id, btn) {
        var el = document.getElementById(id);
        var isExpanded = el.classList.toggle('expanded');
        btn.classList.toggle('expanded', isExpanded);
        btn.querySelector('.unified-expand-label').textContent = isExpanded ? 'Show less' : 'Show more';
    };

    // ===================================================================
    //  Transactions Table (lazy-loaded, portfolio only)
    // ===================================================================

    function initTransactionsTable() {
        if (typeof Tabulator === 'undefined') return;
        if (!cfg.isPortfolio) return;

        var transactionsData = cfg.transactions || [];

        new Tabulator("#position-transactions-table", {
            data: transactionsData,
            layout: "fitColumns",
            responsiveLayout: "collapse",
            pagination: false,
            layoutColumnsOnNewData: true,
            columns: [
                {
                    title: "Date",
                    field: "date",
                    sorter: "date",
                    sorterParams: { format: "yyyy-MM-dd" },
                    hozAlign: "left",
                    minWidth: 100,
                    widthGrow: 1
                },
                {
                    title: "Type",
                    field: "type",
                    sorter: "string",
                    hozAlign: "left",
                    formatter: function (cell) {
                        var type = cell.getValue();
                        var typeClass = '';
                        if (type === 'BUY') typeClass = 'buy';
                        else if (type === 'SELL') typeClass = 'sell';
                        else if (type === 'DIVIDEND') typeClass = 'dividend';
                        else if (type === 'SPLIT') typeClass = 'split';
                        return '<span class="position-txn-type ' + typeClass + '">' + type + '</span>';
                    },
                    minWidth: 90,
                    widthGrow: 1
                },
                {
                    title: "Shares",
                    field: "shares",
                    sorter: "number",
                    hozAlign: "right",
                    formatter: function (cell) {
                        var val = cell.getValue();
                        return val ? val.toLocaleString() : '\u2014';
                    },
                    minWidth: 80,
                    widthGrow: 1
                },
                {
                    title: "Price",
                    field: "price",
                    sorter: "number",
                    hozAlign: "right",
                    formatter: function (cell) {
                        return currencySymbol + cell.getValue().toFixed(2);
                    },
                    minWidth: 90,
                    widthGrow: 1
                },
                {
                    title: "Total",
                    field: "total",
                    sorter: "number",
                    hozAlign: "right",
                    formatter: function (cell) {
                        return '<strong>' + currencySymbol + cell.getValue().toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '</strong>';
                    },
                    minWidth: 100,
                    widthGrow: 1.5
                },
                {
                    title: "Notes",
                    field: "notes",
                    sorter: "string",
                    hozAlign: "left",
                    formatter: function (cell) {
                        var notes = cell.getValue();
                        if (!notes) return '<span class="position-text-muted">\u2014</span>';
                        if (notes.length > 25) {
                            return '<span title="' + notes + '">' + notes.substring(0, 25) + '...</span>';
                        }
                        return notes;
                    },
                    minWidth: 100,
                    widthGrow: 2
                },
                {
                    title: "",
                    field: "id",
                    headerSort: false,
                    hozAlign: "center",
                    formatter: function (cell) {
                        var id = cell.getValue();
                        return '<a href="/portfolio/transaction/' + id + '/edit" class="position-link-btn" title="Edit"><i class="bi bi-pencil"></i></a>';
                    },
                    minWidth: 50,
                    widthGrow: 0.5
                }
            ],
            initialSort: [
                { column: "date", dir: "desc" }
            ]
        });
    }

    // ===================================================================
    //  BlockNote Notes Editor (lazy-loaded)
    // ===================================================================

    function initNotesEditor() {
        var getUrl = cfg.notesGetUrl;
        var saveUrl = cfg.notesSaveUrl;

        var tryInit = setInterval(function () {
            if (window.initBlockNoteEditor) {
                clearInterval(tryInit);
                window.initBlockNoteEditor('journeyNotesEditor', {
                    getResearchNotesUrl: getUrl,
                    saveResearchNotesUrl: saveUrl,
                    placeholder: 'Start writing your company notes here...',
                    onSave: function () {
                        var status = document.getElementById('notesSaveStatus');
                        status.style.display = 'flex';
                        setTimeout(function () { status.style.display = 'none'; }, 2000);
                    }
                });
            }
        }, 100);
    }

    // ===================================================================
    //  Journal Entries — now a React island (journal-entries.bundle.js)
    //  Mounted lazily via library-section-changed event above.
    // ===================================================================

    // ===================================================================
    //  Inline Resources (Documents tab) — handled by React island
    //  (CompanyResourcesManager) which self-fetches, renders, and
    //  listens for 'resources-changed' events autonomously.
    // ===================================================================

    // ===================================================================
    //  Company Annotations — now a React island (company-annotations-panel.bundle.js)
    //  Mounted lazily via library-section-changed event above.
    // ===================================================================

    // ===================================================================
    //  Standalone Q&A — now a React island (standalone-qa.bundle.js)
    //  Mounted lazily via research-section-changed event above.
    // ===================================================================

    // ===================================================================
    //  Utility
    // ===================================================================

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function escapeH(t) {
        if (!t) return '';
        var d = document.createElement('div');
        d.textContent = t;
        return d.innerHTML;
    }

    function extractDom(u) {
        try { return new URL(u).hostname.replace('www.', ''); }
        catch (e) { return u; }
    }

    // ===================================================================
    //  Modal Helpers (global — used by onclick in templates)
    // ===================================================================

    window.hideExportModal = function (event) {
        if (!event || event.target.id === 'exportModal' ||
            event.target.closest('.thesis-modal-close') ||
            event.target.closest('.thesis-modal-footer button[type="button"]')) {
            document.getElementById('exportModal').classList.remove('show');
            document.body.style.overflow = '';
        }
    };

    window.hideValuationModal = function (event) {
        if (!event || event.target.id === 'valuationEditModal' ||
            event.target.closest('.thesis-modal-close') ||
            event.target.closest('.thesis-modal-footer button[type="button"]')) {
            document.getElementById('valuationEditModal').classList.remove('show');
            document.body.style.overflow = '';
        }
    };

})();
