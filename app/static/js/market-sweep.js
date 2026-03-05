/**
 * Market Sweep — "Start with A's" single-page experience.
 * Handles sweep selection, Tabulator table, inline decisions, and kill-checklist modal.
 */
(function () {
    'use strict';

    /* ── STATE ─────────────────────────────────── */
    let sweepTable = null;
    let currentSweepId = null;
    let killCriteria = [];          // cached from server
    let killTargetCompanyId = null;  // company being evaluated in the modal
    let companiesData = [];          // local copy for stat counting

    /* ── DOM REFS ──────────────────────────────── */
    const $picker         = document.getElementById('sweepPicker');
    const $pickerGrid     = document.getElementById('sweepPickerGrid');
    const $emptyState     = document.getElementById('sweepEmptyState');
    const $tableView      = document.getElementById('sweepTableView');
    const $backBtn        = document.getElementById('backToSweeps');
    const $metrics        = document.getElementById('sweepMetrics');
    const $progressFill   = document.getElementById('sweepProgressFill');
    const $searchInput    = document.getElementById('sweepSearch');
    const $decisionFilter = document.getElementById('sweepDecisionFilter');

    /* ── INIT ──────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', function () {
        loadSweeps();
        loadKillChecklist();

        $backBtn.addEventListener('click', showPicker);
        $searchInput.addEventListener('input', applyFilters);
        $decisionFilter.addEventListener('change', applyFilters);
        document.getElementById('killConfirmBtn').addEventListener('click', confirmKill);
        document.getElementById('inboxConfirmBtn').addEventListener('click', confirmInboxFromKill);
    });

    /* ── SWEEP PICKER ──────────────────────────── */
    function loadSweeps() {
        fetch('/research/workflow/api/sweeps')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) return;
                updatePickerMetrics(data.sweeps);
                if (data.sweeps.length === 0) {
                    $pickerGrid.style.display = 'none';
                    $emptyState.style.display = 'block';
                    return;
                }
                renderSweepCards(data.sweeps);
            });
    }

    function updatePickerMetrics(sweeps) {
        var countries = sweeps.length;
        var totalAll = 0, reviewedAll = 0, inboxAll = 0, killedAll = 0;
        sweeps.forEach(function (s) {
            totalAll += s.total_companies;
            reviewedAll += s.reviewed;
            inboxAll += s.inbox_count;
            killedAll += s.killed_count;
        });
        document.getElementById('metricCountries').textContent = countries;
        document.getElementById('metricTotalAll').textContent = totalAll;
        document.getElementById('metricReviewedAll').textContent = reviewedAll;
        document.getElementById('metricInboxAll').textContent = inboxAll;
        document.getElementById('metricKilledAll').textContent = killedAll;
    }

    function renderSweepCards(sweeps) {
        $pickerGrid.innerHTML = '';
        sweeps.forEach(function (s) {
            var pct = s.total_companies ? Math.round((s.reviewed / s.total_companies) * 100) : 0;
            var card = document.createElement('div');
            card.className = 'sweep-picker-card';
            card.innerHTML =
                '<div class="sweep-picker-card__country">' + escapeHtml(s.country) + '</div>' +
                '<div class="sweep-picker-card__name">' + escapeHtml(s.name) + '</div>' +
                '<div class="sweep-picker-card__stats">' +
                    '<span class="sweep-picker-card__stat"><i class="bi bi-buildings"></i> ' + s.total_companies + '</span>' +
                    '<span class="sweep-picker-card__stat"><i class="bi bi-check2"></i> ' + s.reviewed + ' reviewed</span>' +
                    '<span class="sweep-picker-card__stat"><i class="bi bi-inbox"></i> ' + s.inbox_count + ' inbox</span>' +
                '</div>' +
                '<div class="sweep-picker-card__progress"><div class="sweep-picker-card__progress-fill" style="width:' + pct + '%"></div></div>';
            card.addEventListener('click', function () { selectSweep(s.id); });
            $pickerGrid.appendChild(card);
        });
    }

    /* ── SWEEP SELECTION ───────────────────────── */
    function selectSweep(sweepId) {
        currentSweepId = sweepId;
        $picker.style.display = 'none';
        $tableView.style.display = 'block';
        $backBtn.style.display = 'inline-flex';
        document.getElementById('pickerMetrics').style.display = 'none';
        $metrics.style.display = '';

        fetch('/research/workflow/api/sweep/' + sweepId + '/companies')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) return;
                companiesData = data.companies;
                buildTable(data.companies);
                updateStats();
            });
    }

    function showPicker() {
        currentSweepId = null;
        $picker.style.display = '';
        $tableView.style.display = 'none';
        $backBtn.style.display = 'none';
        $metrics.style.display = 'none';
        document.getElementById('pickerMetrics').style.display = '';
        $searchInput.value = '';
        $decisionFilter.value = 'all';
        if (sweepTable) { sweepTable.destroy(); sweepTable = null; }
        loadSweeps();
    }

    /* ── TABULATOR TABLE ───────────────────────── */
    function buildTable(companies) {
        if (sweepTable) { sweepTable.destroy(); sweepTable = null; }

        sweepTable = createDataTable('#sweepTable', {
            data: companies,
            columns: [
                {
                    title: '#',
                    field: 'sort_order',
                    sorter: 'number',
                    hozAlign: 'center',
                    minWidth: 50,
                    formatter: function (cell) {
                        return '<span style="color:var(--text-secondary);font-size:0.8rem">' + cell.getValue() + '</span>';
                    }
                },
                {
                    title: 'Company',
                    field: 'company_name',
                    sorter: 'string',
                    minWidth: 180,
                    widthGrow: 2,
                    formatter: function (cell) {
                        var row = cell.getRow().getData();
                        var ticker = row.ticker ? '<br><span class="sweep-company-cell__ticker">' + escapeHtml(row.ticker) + '</span>' : '';
                        return '<div class="sweep-company-cell"><span class="sweep-company-cell__name">' + escapeHtml(cell.getValue()) + '</span>' + ticker + '</div>';
                    }
                },
                {
                    title: 'Sector',
                    field: 'sector_label',
                    sorter: 'string',
                    minWidth: 120,
                    formatter: function (cell) {
                        var row = cell.getRow().getData();
                        var decided = row.decision;
                        if (decided === 'inbox') {
                            // Show sector select for inbox decisions
                            return buildSectorSelect(row.id, row.decision_sector_id);
                        }
                        var val = cell.getValue();
                        return val ? '<span style="font-size:0.85rem">' + escapeHtml(val) + '</span>' : '<span class="table-cell-muted">&mdash;</span>';
                    }
                },
                {
                    title: 'Market Cap',
                    field: 'market_cap',
                    sorter: 'string',
                    hozAlign: 'center',
                    minWidth: 90,
                    formatter: function (cell) {
                        var val = cell.getValue();
                        return val ? '<span style="font-size:0.85rem">' + escapeHtml(val) + '</span>' : '<span class="table-cell-muted">&mdash;</span>';
                    }
                },
                {
                    title: 'Exchange',
                    field: 'exchange',
                    sorter: 'string',
                    hozAlign: 'center',
                    minWidth: 80,
                    formatter: function (cell) {
                        var val = cell.getValue();
                        return val ? '<span style="font-size:0.85rem">' + escapeHtml(val) + '</span>' : '<span class="table-cell-muted">&mdash;</span>';
                    }
                },
                {
                    title: 'Decision',
                    field: 'decision',
                    sorter: 'string',
                    hozAlign: 'center',
                    minWidth: 90,
                    formatter: function (cell) {
                        var val = cell.getValue();
                        if (!val) return '<span class="sweep-decision-badge sweep-decision-badge--pending">Pending</span>';
                        var map = {
                            'skip':  'sweep-decision-badge--skip',
                            'inbox': 'sweep-decision-badge--inbox',
                            'killed':'sweep-decision-badge--killed'
                        };
                        var labels = { 'skip': 'Skip', 'inbox': 'Inbox', 'killed': 'Killed' };
                        return '<span class="sweep-decision-badge ' + (map[val] || '') + '">' + (labels[val] || val) + '</span>';
                    }
                },
                {
                    title: '',
                    field: 'id',
                    headerSort: false,
                    hozAlign: 'right',
                    minWidth: 180,
                    formatter: function (cell) {
                        var row = cell.getRow().getData();
                        if (row.decision) {
                            var html = '<div class="sweep-actions">';
                            if (row.decision === 'inbox' && row.promoted_idea_id) {
                                html += '<a href="/ideas/' + row.promoted_idea_id + '/promote" class="sweep-action-btn sweep-action-btn--inbox">Start Research</a>';
                            } else {
                                html += '<button class="sweep-action-btn sweep-action-btn--done" disabled>Done</button>';
                            }
                            html += '<button class="sweep-action-btn" onclick="MarketSweep.undoDecision(' + row.id + ')" title="Undo"><i class="bi bi-arrow-counterclockwise"></i></button>';
                            html += '</div>';
                            return html;
                        }
                        return '<div class="sweep-actions">' +
                            '<button class="sweep-action-btn sweep-action-btn--skip" onclick="MarketSweep.decide(' + row.id + ',\'skip\')">Skip</button>' +
                            '<button class="sweep-action-btn sweep-action-btn--inbox" onclick="MarketSweep.decide(' + row.id + ',\'inbox\')">Inbox</button>' +
                            '<button class="sweep-action-btn sweep-action-btn--kill" onclick="MarketSweep.openKill(' + row.id + ',\'' + escapeHtml(row.company_name).replace(/'/g, "\\'") + '\')">Kill</button>' +
                            '</div>';
                    }
                }
            ],
            customConfig: {
                layout: 'fitColumns',
                pagination: true,
                paginationSize: 10,
            }
        });
    }

    /* ── SECTOR SELECT (inline in table) ───────── */
    function buildSectorSelect(companyId, currentSectorId) {
        var html = '<select class="sweep-sector-select" onchange="MarketSweep.updateSector(' + companyId + ', this.value)">';
        html += '<option value="">— Sector —</option>';
        SECTORS_JSON.forEach(function (s) {
            var selected = (currentSectorId && s.id === currentSectorId) ? ' selected' : '';
            html += '<option value="' + s.id + '"' + selected + '>' + escapeHtml(s.name) + '</option>';
        });
        html += '</select>';
        return html;
    }

    /* ── DECISIONS ─────────────────────────────── */
    function decide(companyId, decision, extras) {
        var payload = {
            sweep_company_id: companyId,
            decision: decision
        };
        if (extras) {
            if (extras.kill_reasons) payload.kill_reasons = extras.kill_reasons;
            if (extras.notes) payload.notes = extras.notes;
            if (extras.sector_id) payload.sector_id = extras.sector_id;
            if (extras.idea_status) payload.idea_status = extras.idea_status;
        }

        fetch('/research/workflow/api/sweep/decide', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
            body: JSON.stringify(payload)
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data.success) {
                showToast('Error: ' + (data.error || 'Unknown error'), 'danger');
                return;
            }
            // Update local data
            for (var i = 0; i < companiesData.length; i++) {
                if (companiesData[i].id === companyId) {
                    companiesData[i].decision = decision;
                    companiesData[i].promoted_idea_id = data.promoted_idea_id || null;
                    if (extras && extras.sector_id) companiesData[i].decision_sector_id = parseInt(extras.sector_id);
                    break;
                }
            }
            sweepTable.updateData([{ id: companyId, decision: decision, decision_sector_id: extras ? extras.sector_id : null, promoted_idea_id: data.promoted_idea_id || null }]);
            updateStats();

            var labels = { 'skip': 'Skipped', 'inbox': 'Sent to Inbox', 'killed': 'Killed' };
            showToast(labels[decision] || decision, decision === 'inbox' ? 'success' : 'info');
        });
    }

    function undoDecision(companyId) {
        // Re-decide as pending by sending skip, then clearing it
        // Actually, we'll re-POST with skip and then manually mark as null
        // Simpler: just re-decide — the user can pick a new decision
        for (var i = 0; i < companiesData.length; i++) {
            if (companiesData[i].id === companyId) {
                companiesData[i].decision = null;
                companiesData[i].decision_sector_id = null;
                break;
            }
        }
        sweepTable.updateData([{ id: companyId, decision: null, decision_sector_id: null }]);
        updateStats();
    }

    function updateSector(companyId, sectorId) {
        // Fire a sector update alongside the existing inbox decision
        var payload = {
            sweep_company_id: companyId,
            decision: 'inbox',
            sector_id: sectorId ? parseInt(sectorId) : null
        };

        fetch('/research/workflow/api/sweep/decide', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
            body: JSON.stringify(payload)
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.success) {
                for (var i = 0; i < companiesData.length; i++) {
                    if (companiesData[i].id === companyId) {
                        companiesData[i].decision_sector_id = sectorId ? parseInt(sectorId) : null;
                        break;
                    }
                }
                showToast('Sector updated', 'success');
            }
        });
    }

    /* ── KILL CHECKLIST MODAL ──────────────────── */
    function loadKillChecklist() {
        fetch('/research/workflow/api/sweep/kill-checklist')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    killCriteria = data.criteria || [];
                }
            });
    }

    function openKill(companyId, companyName) {
        killTargetCompanyId = companyId;
        document.getElementById('killCompanyName').textContent = companyName;
        document.getElementById('killConfirmBtn').style.display = 'none';
        document.getElementById('inboxConfirmBtn').style.display = 'none';
        document.getElementById('killResultBanner').style.display = 'none';

        var $list = document.getElementById('killCriteriaList');
        var $noChecklist = document.getElementById('killNoChecklist');

        if (killCriteria.length === 0) {
            $list.style.display = 'none';
            $noChecklist.style.display = 'block';
            return;
        }

        $list.style.display = 'block';
        $noChecklist.style.display = 'none';
        $list.innerHTML = '';

        killCriteria.forEach(function (c, idx) {
            var name = 'kill_' + c.id;
            var html =
                '<div class="sweep-kill-criterion" data-criterion-id="' + c.id + '">' +
                    '<div style="display:flex;align-items:flex-start;flex:1;gap:var(--space-sm)">' +
                        '<span class="sweep-kill-number">' + (idx + 1) + '</span>' +
                        '<span class="sweep-kill-question">' + escapeHtml(c.question) + '</span>' +
                    '</div>' +
                    '<div class="sweep-kill-options">' +
                        '<label class="sweep-kill-option sweep-kill-pass">' +
                            '<input type="radio" name="' + name + '" value="pass"> Pass' +
                        '</label>' +
                        '<label class="sweep-kill-option sweep-kill-fail">' +
                            '<input type="radio" name="' + name + '" value="fail"> Fail' +
                        '</label>' +
                    '</div>' +
                '</div>';
            $list.insertAdjacentHTML('beforeend', html);
        });

        // Listen for radio changes to show the right action button
        $list.querySelectorAll('input[type="radio"]').forEach(function (radio) {
            radio.addEventListener('change', checkKillReady);
        });

        var modal = new bootstrap.Modal(document.getElementById('killChecklistModal'));
        modal.show();
    }

    function checkKillReady() {
        var checked = document.querySelectorAll('#killCriteriaList input[type="radio"]:checked');
        var $killBtn = document.getElementById('killConfirmBtn');
        var $inboxBtn = document.getElementById('inboxConfirmBtn');
        var $banner = document.getElementById('killResultBanner');

        // Not all answered yet — hide both buttons
        if (checked.length < killCriteria.length) {
            $killBtn.style.display = 'none';
            $inboxBtn.style.display = 'none';
            $banner.style.display = 'none';
            return;
        }

        // Count failures
        var failCount = 0;
        checked.forEach(function (r) { if (r.value === 'fail') failCount++; });

        if (failCount > 0) {
            // Has failures → show Kill button
            $killBtn.style.display = '';
            $inboxBtn.style.display = 'none';
            $banner.innerHTML = '<div class="alert alert-danger mb-0 mx-3 mt-2" style="font-size:0.875rem;">' +
                '<i class="bi bi-x-circle"></i> ' + failCount + ' of ' + killCriteria.length + ' criteria failed — kill this company.' +
                '</div>';
            $banner.style.display = 'block';
        } else {
            // All passed → show Inbox button
            $killBtn.style.display = 'none';
            $inboxBtn.style.display = '';
            $banner.innerHTML = '<div class="alert alert-success mb-0 mx-3 mt-2" style="font-size:0.875rem;">' +
                '<i class="bi bi-check-circle"></i> All criteria passed — this company looks interesting!' +
                '</div>';
            $banner.style.display = 'block';
        }
    }

    function getKillReasons() {
        var killReasons = [];
        killCriteria.forEach(function (c) {
            var checked = document.querySelector('input[name="kill_' + c.id + '"]:checked');
            if (checked) {
                killReasons.push({
                    criterion_id: c.id,
                    question: c.question,
                    result: checked.value
                });
            }
        });
        return killReasons;
    }

    function confirmKill() {
        var killReasons = getKillReasons();
        var failCount = killReasons.filter(function (r) { return r.result === 'fail'; }).length;
        var notes = failCount + ' of ' + killCriteria.length + ' criteria failed';

        decide(killTargetCompanyId, 'killed', { kill_reasons: killReasons, notes: notes });

        var modal = bootstrap.Modal.getInstance(document.getElementById('killChecklistModal'));
        if (modal) modal.hide();
    }

    function confirmInboxFromKill() {
        var killReasons = getKillReasons();
        var notes = 'All ' + killCriteria.length + ' kill criteria passed';

        decide(killTargetCompanyId, 'inbox', { kill_reasons: killReasons, notes: notes, idea_status: 'survived' });

        var modal = bootstrap.Modal.getInstance(document.getElementById('killChecklistModal'));
        if (modal) modal.hide();
    }

    /* ── FILTERS ───────────────────────────────── */
    function applyFilters() {
        if (!sweepTable) return;
        var search = $searchInput.value.toLowerCase().trim();
        var decision = $decisionFilter.value;

        sweepTable.setFilter(function (data) {
            var decisionMatch = (decision === 'all') ||
                (decision === 'pending' && !data.decision) ||
                (data.decision === decision);
            var searchMatch = !search ||
                data.company_name.toLowerCase().indexOf(search) !== -1 ||
                (data.ticker && data.ticker.toLowerCase().indexOf(search) !== -1) ||
                (data.sector_label && data.sector_label.toLowerCase().indexOf(search) !== -1);
            return decisionMatch && searchMatch;
        });
    }

    /* ── STATS ─────────────────────────────────── */
    function updateStats() {
        var total = companiesData.length;
        var reviewed = 0, skipped = 0, inbox = 0, killed = 0;
        companiesData.forEach(function (c) {
            if (c.decision) reviewed++;
            if (c.decision === 'skip') skipped++;
            if (c.decision === 'inbox') inbox++;
            if (c.decision === 'killed') killed++;
        });

        document.getElementById('metricTotal').textContent = total;
        document.getElementById('metricReviewed').textContent = reviewed;
        document.getElementById('metricSkipped').textContent = skipped;
        document.getElementById('metricInbox').textContent = inbox;
        document.getElementById('metricKilled').textContent = killed;

        var pct = total ? Math.round((reviewed / total) * 100) : 0;
        $progressFill.style.width = pct + '%';
    }

    /* ── HELPERS ────────────────────────────────── */
    function escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    function showToast(message, type) {
        var existing = document.querySelector('.sweep-toast');
        if (existing) existing.remove();

        var toast = document.createElement('div');
        toast.className = 'sweep-toast';
        toast.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;padding:0.75rem 1.25rem;border-radius:8px;font-size:0.875rem;font-weight:600;z-index:9999;animation:fadeIn 0.2s;';
        if (type === 'success') {
            toast.style.background = 'var(--success-600, #059669)';
            toast.style.color = '#fff';
        } else if (type === 'danger') {
            toast.style.background = 'var(--danger-600, #dc2626)';
            toast.style.color = '#fff';
        } else {
            toast.style.background = 'var(--gray-700, #374151)';
            toast.style.color = '#fff';
        }
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(function () { toast.remove(); }, 2500);
    }

    /* ── PUBLIC API (for inline onclick handlers) ─ */
    window.MarketSweep = {
        decide: decide,
        undoDecision: undoDecision,
        updateSector: updateSector,
        openKill: openKill
    };

})();
