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
    let documentsInitialized = false;
    let transactionsInitialized = false;
    let qaInitialized = false;

    // ===================================================================
    //  Tab, Sub-Section, and Hash Routing
    // ===================================================================

    document.addEventListener('DOMContentLoaded', function () {
        const tabBar = document.getElementById('unifiedTabBar');
        const tabs = tabBar.querySelectorAll('.unified-pill-tab');
        const panels = document.querySelectorAll('.unified-tab-panel');

        function switchToTab(tabId) {
            // Map legacy tab IDs to library sub-sections
            let librarySection = null;
            if (tabId === 'documents' || tabId === 'notes' || tabId === 'journal') {
                librarySection = tabId;
                tabId = 'library';
            }

            // Deactivate all tabs
            tabs.forEach(t => t.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));

            // Activate target tab + panel
            const targetTab = tabBar.querySelector('[data-tab="' + tabId + '"]');
            const targetPanel = document.getElementById('panel-' + tabId);
            if (targetTab) targetTab.classList.add('active');
            if (targetPanel) targetPanel.classList.add('active');

            // Update URL hash
            if (tabId === 'library' && librarySection) {
                history.replaceState(null, '', '#library/' + librarySection);
            } else {
                history.replaceState(null, '', '#' + tabId);
            }

            // Library sub-section activation
            if (tabId === 'library') {
                switchLibrarySection(librarySection || 'documents');
            }

            // Research sub-section activation (default to summary)
            if (tabId === 'research') {
                switchResearchSection('summary');
            }

            // Lazy init (non-library tabs)
            if (tabId === 'transactions' && !transactionsInitialized) {
                initTransactionsTable();
                transactionsInitialized = true;
            }
        }

        // ---- Library Sub-Section Switching ----
        function switchLibrarySection(sectionId) {
            const libraryNav = document.querySelectorAll('.library-nav-item');
            const librarySections = document.querySelectorAll('.library-section');

            libraryNav.forEach(n => n.classList.remove('active'));
            librarySections.forEach(s => s.classList.remove('active'));

            const targetNav = document.querySelector('[data-library-section="' + sectionId + '"]');
            const targetSection = document.getElementById('library-' + sectionId);
            if (targetNav) targetNav.classList.add('active');
            if (targetSection) targetSection.classList.add('active');

            // Lazy init per sub-section
            if (sectionId === 'documents' && !documentsInitialized) {
                loadInlineResources();
                documentsInitialized = true;
            }
            if (sectionId === 'notes' && !notesInitialized) {
                initNotesEditor();
                notesInitialized = true;
            }
            if (sectionId === 'journal' && !journalInitialized) {
                loadJournalEntries(true);
                journalInitialized = true;
            }

            // Update hash
            history.replaceState(null, '', '#library/' + sectionId);
        }

        // ---- Research Sub-Section Switching ----
        function switchResearchSection(sectionId) {
            const researchNav = document.querySelectorAll('.research-nav-item');
            const researchSections = document.querySelectorAll('.research-section');

            researchNav.forEach(n => n.classList.remove('active'));
            researchSections.forEach(s => s.classList.remove('active'));

            const targetNav = document.querySelector('[data-research-section="' + sectionId + '"]');
            const targetSection = document.getElementById('research-' + sectionId);
            if (targetNav) targetNav.classList.add('active');
            if (targetSection) targetSection.classList.add('active');

            // Lazy init standalone Q&A
            if (sectionId === 'qa' && !qaInitialized) {
                StandaloneQA.init();
                qaInitialized = true;
            }

            // Update hash
            history.replaceState(null, '', '#research/' + sectionId);
        }

        // Expose globally so partials can use it
        window.switchToTab = switchToTab;
        window.switchLibrarySection = switchLibrarySection;
        window.switchResearchSection = switchResearchSection;

        // Click handler for tab buttons
        tabs.forEach(tab => {
            tab.addEventListener('click', function () {
                switchToTab(this.dataset.tab);
            });
        });

        // Hash-based routing on page load
        const hash = window.location.hash.substring(1);
        if (hash) {
            if (hash.startsWith('library/')) {
                const libSection = hash.split('/')[1];
                switchToTab('library');
                switchLibrarySection(libSection);
            } else if (hash.startsWith('research/')) {
                const resSection = hash.split('/')[1];
                switchToTab('research');
                switchResearchSection(resSection);
            } else if (['documents', 'notes', 'journal'].includes(hash)) {
                switchToTab(hash);
            } else if (document.getElementById('panel-' + hash)) {
                switchToTab(hash);
            }
        }

        // ---- Collapsible sections: show expand button only if content overflows ----
        requestAnimationFrame(function () {
            document.querySelectorAll('.unified-collapsible').forEach(function (el) {
                var content = el.querySelector('.unified-collapsible-content');
                var btn = el.nextElementSibling;
                if (!content || !btn || !btn.classList.contains('unified-expand-btn')) return;
                if (content.scrollHeight > el.clientHeight + 4) {
                    btn.style.display = '';
                } else {
                    el.style.maxHeight = 'none';
                    el.querySelector('.unified-collapsible-fade').style.display = 'none';
                    btn.style.display = 'none';
                }
            });
        });

        // ---- Async Price Refresh (portfolio companies) ----
        if (cfg.priceStale) {
            fetch('/portfolio/api/refresh-position/' + companyId, { method: 'POST' })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        var p = data.position;
                        document.getElementById('posPrice').textContent = currencySymbol + (p.current_price !== null ? p.current_price.toFixed(2) : '--');
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

        // ---- Financial Fetch + Polling (Documents tab) ----
        const fetchBtn = document.getElementById('fetch-financials-btn');
        const statusDiv = document.getElementById('financial-fetch-status');

        if (fetchBtn) {
            fetchBtn.addEventListener('click', function () {
                const cid = this.getAttribute('data-company-id');
                fetchBtn.disabled = true;
                fetchBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Starting...';
                statusDiv.classList.remove('d-none');

                fetch('/companies/' + cid + '/fetch_financials', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                })
                    .then(response => {
                        if (!response.ok) throw new Error('HTTP ' + response.status + ': ' + response.statusText);
                        return response.json();
                    })
                    .then(data => {
                        if (data.success) {
                            statusDiv.innerHTML =
                                '<div class="status-indicator">' +
                                    '<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div>' +
                                    '<div><strong>Financial data fetch in progress...</strong>' +
                                    '<div class="small">Task ID: ' + data.task_id + '. Monitoring progress...</div></div>' +
                                '</div>';
                            fetchBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>Fetch Started';
                            fetchBtn.disabled = true;
                            pollTaskStatus(data.task_id, statusDiv, fetchBtn);
                        } else {
                            statusDiv.innerHTML =
                                '<div class="status-indicator error"><i class="bi bi-exclamation-circle"></i>' +
                                '<div><strong>Error:</strong> ' + (data.error || 'Failed to start financial data fetch') + '</div></div>';
                            fetchBtn.disabled = false;
                            fetchBtn.innerHTML = '<i class="bi bi-download me-2"></i>Fetch Financial History';
                        }
                    })
                    .catch(() => {
                        statusDiv.innerHTML =
                            '<div class="status-indicator error"><i class="bi bi-exclamation-circle"></i>' +
                            '<div><strong>Error:</strong> Failed to start financial data fetch. Please try again.</div></div>';
                        fetchBtn.disabled = false;
                        fetchBtn.innerHTML = '<i class="bi bi-download me-2"></i>Fetch Financial History';
                    });
            });
        }

        function pollTaskStatus(taskId, statusDiv, fetchBtn) {
            const pollInterval = setInterval(() => {
                fetch('/research/task_status/' + taskId)
                    .then(response => response.json())
                    .then(data => {
                        if (data.state === 'SUCCESS') {
                            statusDiv.innerHTML =
                                '<div class="status-indicator success"><i class="bi bi-check-circle"></i>' +
                                '<div><strong>Financial data fetch completed!</strong>' +
                                '<div class="small">Financial data has been updated. You can now view the financials page.</div></div></div>';
                            fetchBtn.disabled = false;
                            fetchBtn.innerHTML = '<i class="bi bi-download me-2"></i>Fetch Financial History';
                            clearInterval(pollInterval);
                            setTimeout(() => { statusDiv.classList.add('d-none'); }, 5000);
                        } else if (data.state === 'FAILURE') {
                            statusDiv.innerHTML =
                                '<div class="status-indicator error"><i class="bi bi-x-circle"></i>' +
                                '<div><strong>Financial data fetch failed!</strong>' +
                                '<div class="small">' + (data.status_message || 'Unknown error occurred') + '</div></div></div>';
                            fetchBtn.disabled = false;
                            fetchBtn.innerHTML = '<i class="bi bi-download me-2"></i>Fetch Financial History';
                            clearInterval(pollInterval);
                        } else if (data.state === 'PENDING') {
                            statusDiv.innerHTML =
                                '<div class="status-indicator"><div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div>' +
                                '<div><strong>Financial data fetch in progress...</strong>' +
                                '<div class="small">' + (data.status_message || 'Task is running in background...') + '</div></div></div>';
                        }
                    })
                    .catch(() => {
                        statusDiv.innerHTML =
                            '<div class="status-indicator warning"><i class="bi bi-exclamation-triangle"></i>' +
                            '<div><strong>Cannot check task status</strong>' +
                            '<div class="small">Will continue running in background</div></div></div>';
                        clearInterval(pollInterval);
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
    //  Inline Resources (Documents tab)
    // ===================================================================

    function loadInlineResources() {
        var container = document.getElementById('docs-tab-resource-list');
        if (!container) return;

        fetch('/companies/api/' + companyId + '/resources')
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (!result.success || !result.data.resources.length) {
                    container.innerHTML =
                        '<div class="text-center text-muted py-3">' +
                            '<i class="bi bi-inbox" style="font-size: 1.5rem;"></i>' +
                            '<p class="mt-2 mb-0 small">No resources yet. Upload a file or save a link to get started.</p>' +
                        '</div>';
                    return;
                }
                var resources = result.data.resources;
                container.innerHTML = resources.map(function (r) {
                    var icon = r.resource_type === 'file'
                        ? (r.file_type === 'pdf' ? 'bi-file-earmark-pdf-fill text-danger' : 'bi-file-earmark-text-fill text-primary')
                        : 'bi-link-45deg text-info';
                    var meta = r.resource_type === 'file'
                        ? escapeH(r.original_filename)
                        : (r.source_name || extractDom(r.url));
                    var catBadge = r.category
                        ? '<span class="badge bg-light text-dark border ms-1">' + escapeH(r.category) + '</span>'
                        : '';
                    var titleHtml = r.resource_type === 'link'
                        ? '<a href="' + escapeH(r.url) + '" target="_blank" rel="noopener" class="text-decoration-none">' + escapeH(r.title) + ' <i class="bi bi-box-arrow-up-right" style="font-size: 0.7em;"></i></a>'
                        : escapeH(r.title);
                    var viewBtn = r.resource_type === 'file'
                        ? '<a href="/companies/resources/' + r.id + '/viewer" target="_blank" class="btn btn-sm btn-outline-secondary border-0" title="View"><i class="bi bi-eye"></i></a>'
                        : '';
                    var downloadBtn = r.resource_type === 'file'
                        ? '<a href="/companies/api/resources/' + r.id + '/download" class="btn btn-sm btn-outline-primary border-0" title="Download"><i class="bi bi-download"></i></a>'
                        : '';
                    return '<div class="d-flex justify-content-between align-items-start py-2 border-bottom cr-resource-item">' +
                        '<div class="flex-grow-1" style="min-width:0">' +
                            '<div class="fw-semibold small"><i class="bi ' + icon + ' me-1"></i>' + titleHtml + catBadge + '</div>' +
                            '<div class="text-muted" style="font-size:0.78rem">' + meta + '</div>' +
                        '</div>' +
                        '<div class="d-flex gap-1 ms-2 flex-shrink-0">' +
                            viewBtn +
                            downloadBtn +
                            '<button class="btn btn-sm btn-outline-danger border-0" title="Delete" onclick="deleteInlineResource(' + r.id + ')">' +
                                '<i class="bi bi-trash"></i>' +
                            '</button>' +
                        '</div>' +
                    '</div>';
                }).join('');
            })
            .catch(function () {
                container.innerHTML = '<div class="text-danger small">Failed to load resources.</div>';
            });
    }

    window.deleteInlineResource = function (id) {
        if (!confirm('Delete this resource?')) return;
        fetch('/companies/api/resources/' + id, { method: 'DELETE' })
            .then(function (r) { return r.json(); })
            .then(function (result) { if (result.success) loadInlineResources(); })
            .catch(function () { alert('Failed to delete.'); });
    };

    // ===================================================================
    //  Standalone Q&A (Research Tab)
    //  List + Create use /companies/api/<id>/research-questions
    //  Update + Delete reuse /research/workflow/api/questions/<id>
    // ===================================================================

    var StandaloneQA = {
        questions: [],
        editors: {},
        listUrl: '/companies/api/' + companyId + '/research-questions',
        questionUrl: '/research/workflow/api/questions/',

        init: function () {
            this.loadQuestions();

            // Enter-key handler for add-question input
            var input = document.getElementById('newQuestionText');
            if (input) {
                input.addEventListener('keypress', function (e) {
                    if (e.key === 'Enter') { e.preventDefault(); StandaloneQA.createQuestion(); }
                });
            }
        },

        loadQuestions: function () {
            var self = this;
            fetch(this.listUrl)
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        self.questions = data.questions;
                        self.renderAll();
                    }
                })
                .catch(function (err) { console.error('Error loading research questions:', err); });
        },

        renderAll: function () {
            var container = document.getElementById('standaloneQuestionsList');
            var emptyState = document.getElementById('standaloneQaEmptyState');

            if (this.questions.length === 0) {
                container.innerHTML = '';
                if (emptyState) emptyState.style.display = '';
                return;
            }

            if (emptyState) emptyState.style.display = 'none';
            var self = this;
            container.innerHTML = this.questions.map(function (q) { return self.renderCard(q); }).join('');
        },

        renderCard: function (q) {
            var isAnswered = q.status === 'answered';
            var statusLabel = isAnswered ? 'Answered' : 'Exploring';
            var statusIcon = isAnswered ? 'check-circle-fill' : 'search';

            return '<div class="research-summary-card" data-question-id="' + q.id + '" style="margin-bottom: 0.75rem;">' +
                '<div class="research-summary-header" onclick="StandaloneQA.toggleExpand(' + q.id + ')">' +
                    '<div class="research-summary-header-left">' +
                        '<i class="bi bi-question-circle-fill" style="color: var(--accent-color);"></i>' +
                        '<span class="research-step-name">' + escapeHtml(q.question_text) + '</span>' +
                        '<span class="research-qa-status ' + q.status + '">' + statusLabel + '</span>' +
                    '</div>' +
                    '<div style="display: flex; align-items: center; gap: 0.5rem;">' +
                        '<button class="position-btn" style="padding: 2px 8px; font-size: 0.75rem;" ' +
                            'onclick="event.stopPropagation(); StandaloneQA.toggleStatus(' + q.id + ')" title="Toggle status">' +
                            '<i class="bi bi-' + statusIcon + '"></i>' +
                        '</button>' +
                        '<button class="position-btn" style="padding: 2px 8px; font-size: 0.75rem; color: var(--danger-500);" ' +
                            'onclick="event.stopPropagation(); StandaloneQA.deleteQuestion(' + q.id + ')" title="Delete">' +
                            '<i class="bi bi-trash"></i>' +
                        '</button>' +
                        '<i class="bi bi-chevron-down" style="color: var(--gray-400);"></i>' +
                    '</div>' +
                '</div>' +
                '<div class="research-summary-body collapsed">' +
                    '<div id="standalone-editor-' + q.id + '" style="min-height: 120px;"></div>' +
                    AIResearchAssistant.renderToolbar(q.id, 'StandaloneQA') +
                '</div>' +
            '</div>';
        },

        toggleExpand: function (questionId) {
            var card = document.querySelector('[data-question-id="' + questionId + '"]');
            if (!card) return;

            var body = card.querySelector('.research-summary-body');
            var wasCollapsed = body.classList.contains('collapsed');

            // Collapse all other standalone cards
            var allBodies = document.querySelectorAll('#standaloneQuestionsList .research-summary-body');
            allBodies.forEach(function (b) { b.classList.add('collapsed'); });

            if (wasCollapsed) {
                body.classList.remove('collapsed');
                this.initEditor(questionId);
            }
        },

        initEditor: function (questionId) {
            if (this.editors[questionId]) return;

            var containerId = 'standalone-editor-' + questionId;
            var container = document.getElementById(containerId);
            if (!container || !window.initBlockNoteEditor) return;

            var question = this.questions.find(function (q) { return q.id === questionId; });
            var self = this;

            this.editors[questionId] = window.initBlockNoteEditor(containerId, {
                initialContent: question ? question.answer_content || '' : '',
                placeholder: 'Write your research findings here...',
                onChange: function (json) {
                    self.saveAnswer(questionId, json);
                }
            });
        },

        saveAnswer: function (questionId, content) {
            var question = this.questions.find(function (q) { return q.id === questionId; });
            if (question) question.answer_content = content;

            fetch(this.questionUrl + questionId, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ answer_content: content })
            }).catch(function (err) { console.error('Error saving answer:', err); });
        },

        toggleStatus: function (questionId) {
            var question = this.questions.find(function (q) { return q.id === questionId; });
            if (!question) return;

            var newStatus = question.status === 'exploring' ? 'answered' : 'exploring';
            var self = this;

            fetch(this.questionUrl + questionId, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    question.status = newStatus;
                    self.renderAll();
                    showToast(newStatus === 'answered' ? 'Marked as answered' : 'Marked as exploring');
                }
            })
            .catch(function (err) { console.error('Error toggling status:', err); });
        },

        showAddForm: function () {
            document.getElementById('addQuestionForm').style.display = '';
            document.getElementById('newQuestionText').focus();
        },

        hideAddForm: function () {
            document.getElementById('addQuestionForm').style.display = 'none';
            document.getElementById('newQuestionText').value = '';
        },

        createQuestion: function () {
            var input = document.getElementById('newQuestionText');
            var text = input.value.trim();
            if (!text) return;

            var self = this;
            fetch(this.listUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question_text: text })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    self.questions.push(data.question);
                    self.renderAll();
                    self.hideAddForm();
                    showToast('Question added');
                } else {
                    showToast(data.message || 'Error adding question', 'danger');
                }
            })
            .catch(function () { showToast('Network error', 'danger'); });
        },

        deleteQuestion: function (questionId) {
            if (!confirm('Delete this research question?')) return;
            var self = this;

            fetch(this.questionUrl + questionId, { method: 'DELETE' })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        self.questions = self.questions.filter(function (q) { return q.id !== questionId; });
                        delete self.editors[questionId];
                        self.renderAll();
                        showToast('Question deleted');
                    }
                })
                .catch(function (err) { console.error('Error deleting question:', err); });
        },

        // ---- AI Research Tools (delegates to AIResearchAssistant) ----

        getEditorText: function (questionId) {
            var container = document.getElementById('standalone-editor-' + questionId);
            if (container) {
                return container.textContent || container.innerText || '';
            }
            return '';
        },

        triggerAI: function (questionId, mode) {
            var question = this.questions.find(function (q) { return q.id === questionId; });
            if (!question) return;
            AIResearchAssistant.triggerForQuestion(questionId, mode, {
                answerText: this.getEditorText(questionId),
                questionText: question.question_text,
                companyName: companyName,
                showToast: showToast
            });
        }
    };

    // Expose to global scope for onclick handlers in dynamically rendered HTML
    window.StandaloneQA = StandaloneQA;

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
