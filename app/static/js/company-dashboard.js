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
                loadJournalEntries(true);
                journalInitialized = true;
            }
            if (sectionId === 'annotations' && !annotationsInitialized) {
                loadCompanyAnnotations();
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

        // ---- Ticker Testing Tool (Settings tab) ----
        const testTickerBtn = document.getElementById('testTickerBtn');
        const testTickerInput = document.getElementById('testTicker');
        const testResult = document.getElementById('testResult');

        if (testTickerBtn && testTickerInput) {
            testTickerBtn.addEventListener('click', function () {
                const ticker = testTickerInput.value.trim().toUpperCase();
                if (!ticker) {
                    testResult.className = 'alert alert-warning mt-3';
                    testResult.innerHTML = '<i class="bi bi-exclamation-triangle me-2"></i>Please enter a ticker symbol to test.';
                    testResult.classList.remove('d-none');
                    return;
                }
                testTickerBtn.disabled = true;
                testTickerBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Testing...';
                testResult.className = 'alert alert-info mt-3';
                testResult.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Validating ticker symbol...';
                testResult.classList.remove('d-none');

                fetch('/companies/validate_ticker', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ticker: ticker })
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.valid) {
                            const isSameTicker = data.ticker === (document.getElementById('currentTickerDisplay') || {}).textContent?.trim();
                            testResult.className = 'alert alert-success mt-3';
                            testResult.innerHTML =
                                '<div class="d-flex justify-content-between align-items-start">' +
                                    '<div>' +
                                        '<strong><i class="bi bi-check-circle-fill me-2"></i>Ticker Found!</strong>' +
                                        '<div class="mt-2">' +
                                            '<strong>' + data.ticker + '</strong> - ' + (data.company_name || 'N/A') +
                                            (data.exchange ? '<br><small class="text-muted">Exchange: ' + data.exchange + '</small>' : '') +
                                        '</div>' +
                                    '</div>' +
                                    '<div class="text-end">' +
                                        (data.current_price ? '<div class="text-muted small">Current Price</div><div class="h5 mb-0 text-success">' + currencySymbol + data.current_price.toFixed(2) + '</div>' : '') +
                                    '</div>' +
                                '</div>' +
                                (isSameTicker
                                    ? '<div class="mt-2 text-muted"><small><i class="bi bi-info-circle me-1"></i>This is already the current ticker.</small></div>'
                                    : '<div class="mt-3 pt-3" style="border-top: 1px solid rgba(0,0,0,0.1);">' +
                                        '<button type="button" class="btn btn-primary btn-sm" id="applyTickerBtn" data-ticker="' + data.ticker + '">' +
                                            '<i class="bi bi-arrow-repeat me-1"></i>Use ' + data.ticker + ' as company ticker' +
                                        '</button>' +
                                    '</div>');
                        } else {
                            testResult.className = 'alert alert-danger mt-3';
                            testResult.innerHTML =
                                '<strong><i class="bi bi-x-circle-fill me-2"></i>Ticker Not Found</strong>' +
                                '<div class="mt-2">' + (data.error || 'Could not validate this ticker symbol.') + '</div>' +
                                '<div class="mt-2"><small>Make sure you\'re using the correct format (e.g., AAPL for US stocks, MBB.DE for German stocks).</small></div>';
                        }
                    })
                    .catch(() => {
                        testResult.className = 'alert alert-danger mt-3';
                        testResult.innerHTML =
                            '<strong><i class="bi bi-x-circle-fill me-2"></i>Error</strong>' +
                            '<div class="mt-2">Failed to validate ticker. Please try again.</div>';
                    })
                    .finally(() => {
                        testTickerBtn.disabled = false;
                        testTickerBtn.innerHTML = '<i class="bi bi-play-fill me-2"></i>Test Ticker';
                    });
            });

            testTickerInput.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') { e.preventDefault(); testTickerBtn.click(); }
            });

            // Handle "Use as company ticker" button (delegated since it's dynamically created)
            testResult.addEventListener('click', function (e) {
                const applyBtn = e.target.closest('#applyTickerBtn');
                if (!applyBtn) return;

                const newTicker = applyBtn.dataset.ticker;
                if (!newTicker) return;

                applyBtn.disabled = true;
                applyBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Updating...';

                const form = document.getElementById('editCompanyForm');
                if (form) {
                    const tickerInput = form.querySelector('input[name="ticker_symbol"]');
                    if (tickerInput) {
                        tickerInput.value = newTicker;
                        form.requestSubmit();
                    }
                }
            });
        }

        // ---- Settings Form — AJAX Save ----
        var editForm = document.getElementById('editCompanyForm');
        if (editForm) {
            editForm.addEventListener('submit', function (e) {
                e.preventDefault();

                var saveBtn = document.getElementById('saveChangesBtn');
                saveBtn.disabled = true;
                saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving\u2026';

                // Handle "Add new sector" before building FormData
                var sectorSel = document.getElementById('sectorSelect');
                var newSectorInp = document.getElementById('newSectorInput');
                var formData = new FormData(editForm);

                if (sectorSel && sectorSel.value === '__new__' && newSectorInp && newSectorInp.value.trim()) {
                    formData.set('sector', newSectorInp.value.trim());
                }

                fetch(editForm.action, {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        showToast(data.message, 'success');
                        // Update header with new values
                        if (data.name) {
                            var titleEl = document.querySelector('.dashboard-title');
                            if (titleEl) titleEl.textContent = data.name;
                            var logoEl = document.querySelector('.dashboard-header-logo');
                            if (logoEl) logoEl.textContent = data.name.substring(0, 2).toUpperCase();
                            document.title = data.name + ' \u2014 Company Hub';
                        }
                        if (data.ticker_symbol) {
                            var tickerEl = document.querySelector('.journey-ticker');
                            if (tickerEl) tickerEl.textContent = data.ticker_symbol;
                            var tickerDisplay = document.getElementById('currentTickerDisplay');
                            if (tickerDisplay) tickerDisplay.textContent = data.ticker_symbol;
                        }
                        var subtitleEl = document.querySelector('.dashboard-subtitle');
                        if (subtitleEl) {
                            var tickerSpan = '<span class="journey-ticker">' + escapeHtml(data.ticker_symbol || '') + '</span>';
                            subtitleEl.innerHTML = tickerSpan + (data.sector_name ? ' &middot; ' + escapeHtml(data.sector_name) : '');
                        }
                        // If new sector was created, add it to the dropdown
                        if (sectorSel && data.sector_name) {
                            var existing = sectorSel.querySelector('option[value="' + CSS.escape(data.sector_name) + '"]');
                            if (!existing) {
                                var opt = document.createElement('option');
                                opt.value = data.sector_name;
                                opt.textContent = data.sector_name;
                                sectorSel.insertBefore(opt, sectorSel.querySelector('option[value="__new__"]'));
                            }
                            sectorSel.value = data.sector_name;
                            if (newSectorInp) {
                                newSectorInp.classList.add('d-none');
                                newSectorInp.value = '';
                                newSectorInp.required = false;
                            }
                        }
                    } else {
                        showToast(data.error || 'Failed to save changes', 'danger');
                    }
                })
                .catch(function () {
                    showToast('Network error saving changes', 'danger');
                })
                .finally(function () {
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Save Changes';
                    // Reset apply-ticker button if it was used
                    var applyBtn = document.getElementById('applyTickerBtn');
                    if (applyBtn) {
                        applyBtn.disabled = false;
                        applyBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i>Use ' + applyBtn.dataset.ticker + ' as company ticker';
                    }
                });
            });
        }

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
    //  Journal Entries (AJAX, paginated)
    // ===================================================================

    var journalOffset = 0;
    var journalTotal = 0;
    var journalSearchQuery = '';
    var journalSearchTimeout = null;

    window.debouncedJournalSearch = function () {
        clearTimeout(journalSearchTimeout);
        journalSearchTimeout = setTimeout(function () {
            journalSearchQuery = document.getElementById('journalSearchInput').value.trim();
            loadJournalEntries(true);
        }, 300);
    };

    function loadJournalEntries(reset) {
        if (reset) {
            journalOffset = 0;
            document.getElementById('journalCards').innerHTML = '';
        }
        var loadMoreBtn = document.getElementById('journalLoadMore');
        var emptyState = document.getElementById('journalEmptyState');
        loadMoreBtn.style.display = 'none';
        emptyState.style.display = 'none';

        var url = '/portfolio/api/notes/' + companyId + '?offset=' + journalOffset + '&limit=10';
        if (journalSearchQuery) url += '&q=' + encodeURIComponent(journalSearchQuery);

        fetch(url)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) return;
                journalTotal = data.total;
                var container = document.getElementById('journalCards');

                if (data.entries.length === 0 && journalOffset === 0) {
                    emptyState.style.display = 'block';
                    return;
                }
                data.entries.forEach(function (entry) {
                    container.insertAdjacentHTML('beforeend', renderJournalCard(entry));
                });
                journalOffset += data.entries.length;
                if (data.has_more) {
                    loadMoreBtn.style.display = 'block';
                    loadMoreBtn.innerHTML = 'Load more (' + journalOffset + ' of ' + journalTotal + ') <i class="bi bi-chevron-down"></i>';
                }
            });
    }
    window.loadJournalEntries = loadJournalEntries;

    function renderJournalCard(entry) {
        var contentHtml = entry.content_html || escapeHtml(entry.content);
        var sentimentHtml = '';
        if (entry.sentiment) {
            sentimentHtml = '<span class="journey-note-sentiment ' + entry.sentiment + '">' + entry.sentiment + '</span>';
        }
        var tagsHtml = '';
        if (entry.tags && entry.tags.length) {
            tagsHtml = '<div class="journey-note-tags">' +
                entry.tags.slice(0, 6).map(function (t) { return '<span class="journey-note-tag">#' + escapeHtml(t) + '</span>'; }).join('') +
                '</div>';
        }
        var viewUrl = '/journal/entry/' + entry.id;
        return '<div class="journey-note-card">' +
            '<div class="journey-note-card-header">' +
                '<span class="journey-note-card-date"><i class="bi bi-calendar3"></i> ' + entry.created_at + '</span>' +
                '<div class="journey-note-card-actions">' +
                    sentimentHtml +
                    '<a href="' + viewUrl + '" class="journey-note-view-btn" title="View full entry"><i class="bi bi-box-arrow-up-right"></i></a>' +
                '</div>' +
            '</div>' +
            '<div class="journey-note-card-content blocknote-content">' + contentHtml + '</div>' +
            tagsHtml +
        '</div>';
    }

    // ===================================================================
    //  Inline Resources (Documents tab) — handled by React island
    //  (CompanyResourcesManager) which self-fetches, renders, and
    //  listens for 'resources-changed' events autonomously.
    // ===================================================================

    // ===================================================================
    //  Company Annotations (Library > Annotations tab)
    // ===================================================================

    function loadCompanyAnnotations() {
        var container = document.getElementById('company-annotations-list');
        if (!container) return;

        fetch('/companies/api/' + companyId + '/annotations')
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (!result.success) {
                    container.innerHTML = '<div class="text-danger small">Failed to load annotations.</div>';
                    return;
                }

                var annotations = result.data.annotations;
                var countBadge = document.getElementById('company-annotations-count');
                if (countBadge) {
                    if (annotations.length > 0) {
                        countBadge.textContent = annotations.length;
                        countBadge.style.display = 'inline';
                    } else {
                        countBadge.style.display = 'none';
                    }
                }

                if (annotations.length === 0) {
                    container.innerHTML =
                        '<div class="text-center text-muted py-4">' +
                            '<i class="bi bi-pin-angle" style="font-size:1.5rem;"></i>' +
                            '<p class="mt-2 mb-0 small">No annotations yet. Open a PDF document and add pins or highlights to get started.</p>' +
                        '</div>';
                    return;
                }

                // Group annotations by resource
                var groups = {};
                var groupOrder = [];
                annotations.forEach(function (a) {
                    var key = a.resource_id;
                    if (!groups[key]) {
                        groups[key] = { title: a.resource_title, resourceId: a.resource_id, items: [] };
                        groupOrder.push(key);
                    }
                    groups[key].items.push(a);
                });

                var html = '';
                groupOrder.forEach(function (key) {
                    var group = groups[key];
                    html += '<div class="company-section-card mb-3">' +
                        '<div class="company-section-card-header d-flex justify-content-between align-items-center" style="padding:0.625rem 1rem;">' +
                            '<h6 class="mb-0" style="font-size:0.85rem;">' +
                                '<i class="bi bi-file-earmark-pdf-fill text-danger me-1"></i>' +
                                escapeHtml(group.title) +
                                ' <span class="badge bg-light text-dark border ms-1" style="font-size:0.65rem;">' + group.items.length + '</span>' +
                            '</h6>' +
                            '<a href="/companies/resources/' + group.resourceId + '/viewer" target="_blank" class="btn btn-sm btn-outline-secondary border-0" title="Open document">' +
                                '<i class="bi bi-box-arrow-up-right"></i>' +
                            '</a>' +
                        '</div>' +
                        '<div style="max-height:300px;overflow-y:auto;">';

                    group.items.forEach(function (a) {
                        var icon = a.annotation_type === 'highlight'
                            ? '<i class="bi bi-highlighter text-warning me-1"></i>'
                            : '<i class="bi bi-pin-angle text-danger me-1"></i>';
                        var date = a.created_at ? new Date(a.created_at).toLocaleDateString() : '';
                        var quote = a.annotation_type === 'highlight' && a.anchor_text
                            ? '<div style="font-size:0.75rem;color:#777;border-left:2px solid #fbc02d;padding:0.125rem 0.375rem;margin-bottom:0.25rem;background:#fffde7;border-radius:0 2px 2px 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' +
                                escapeHtml(a.anchor_text.length > 80 ? a.anchor_text.substring(0, 80) + '...' : a.anchor_text) +
                              '</div>'
                            : '';

                        html += '<div class="d-flex align-items-start py-2 px-3 border-bottom annotation-dashboard-item" ' +
                            'style="cursor:pointer;transition:background 0.15s;" ' +
                            'data-resource-id="' + a.resource_id + '" data-page="' + a.page_number + '">' +
                            '<div class="flex-grow-1" style="min-width:0;">' +
                                quote +
                                '<div class="small">' + icon +
                                    '<span style="color:var(--gray-500);font-size:0.75rem;">p.' + a.page_number + '</span> ' +
                                    escapeHtml(a.content.length > 100 ? a.content.substring(0, 100) + '...' : a.content) +
                                '</div>' +
                                '<div style="font-size:0.7rem;color:#6c757d;margin-top:0.125rem;">' +
                                    date +
                                    ' <span class="badge bg-light text-dark border" style="font-size:0.6rem;">' + escapeHtml(a.scope) + '</span>' +
                                '</div>' +
                            '</div>' +
                        '</div>';
                    });

                    html += '</div></div>';
                });

                container.innerHTML = html;

                // Click handlers: open viewer
                container.querySelectorAll('.annotation-dashboard-item').forEach(function (item) {
                    item.addEventListener('click', function () {
                        var rid = this.dataset.resourceId;
                        var page = this.dataset.page;
                        window.open('/companies/resources/' + rid + '/viewer#page=' + page, '_blank');
                    });
                    item.addEventListener('mouseenter', function () { this.style.background = '#f8f9fa'; });
                    item.addEventListener('mouseleave', function () { this.style.background = ''; });
                });
            })
            .catch(function (err) {
                console.error('Failed to load company annotations:', err);
                container.innerHTML = '<div class="text-danger small">Failed to load annotations.</div>';
            });
    }

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
