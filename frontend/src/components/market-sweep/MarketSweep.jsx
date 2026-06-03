import { useState, useEffect, useRef } from 'react';
import { apiGet, apiPost } from '../../lib/api';
import { createDataTable } from '../../lib/dataTable';
import { SweepPicker } from './SweepPicker';
import { KillChecklistModal } from './KillChecklistModal';

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

function setDomText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

/**
 * MarketSweep — "Start with A's" single-page React island.
 *
 * Renders sweep picker (card grid), Tabulator company table with inline
 * decision buttons, and kill-checklist modal. Header metrics in the
 * Jinja2 template are updated via bridge pattern (DOM id lookups).
 *
 * Props (via config):
 *   sectors: Array<{ id, name }> — available sectors for inbox assignment
 */
export function MarketSweep({ sectors }) {
  const [view, setView] = useState('picker');
  const [sweeps, setSweeps] = useState([]);
  const [search, setSearch] = useState('');
  const [decisionFilter, setDecisionFilter] = useState('all');
  const [killTarget, setKillTarget] = useState(null);
  const [killCriteria, setKillCriteria] = useState([]);
  const [stats, setStats] = useState({ total: 0, reviewed: 0, inbox: 0, killed: 0 });

  const tableRef = useRef(null);
  const companiesRef = useRef([]);
  const handlersRef = useRef({});

  // ------------------------------------------------------------------
  // Keep handler refs current so the global API always calls latest fns
  // ------------------------------------------------------------------
  handlersRef.current = {
    decide: handleDecide,
    undoDecision: handleUndoDecision,
    updateSector: handleUpdateSector,
    openKill: handleOpenKill,
    showPicker: handleShowPicker,
  };

  // ------------------------------------------------------------------
  // Expose global API for Tabulator inline onclick handlers
  // ------------------------------------------------------------------
  useEffect(() => {
    window.MarketSweep = {
      decide: (...args) => handlersRef.current.decide(...args),
      undoDecision: (...args) => handlersRef.current.undoDecision(...args),
      updateSector: (...args) => handlersRef.current.updateSector(...args),
      openKill: (...args) => handlersRef.current.openKill(...args),
      showPicker: () => handlersRef.current.showPicker(),
    };
    return () => {
      delete window.MarketSweep;
    };
  }, []);

  // ------------------------------------------------------------------
  // Load data on mount
  // ------------------------------------------------------------------
  useEffect(() => {
    loadSweeps();
    loadKillChecklist();
  }, []);

  // ------------------------------------------------------------------
  // Back button listener (bridge to header)
  // ------------------------------------------------------------------
  useEffect(() => {
    const backBtn = document.getElementById('backToSweeps');
    if (!backBtn) return;
    const handler = () => handlersRef.current.showPicker();
    backBtn.addEventListener('click', handler);
    return () => backBtn.removeEventListener('click', handler);
  }, []);

  // ------------------------------------------------------------------
  // Toggle header metric strips (bridge)
  // ------------------------------------------------------------------
  useEffect(() => {
    const pickerMetrics = document.getElementById('pickerMetrics');
    const sweepMetrics = document.getElementById('sweepMetrics');
    const backBtn = document.getElementById('backToSweeps');
    if (view === 'picker') {
      if (pickerMetrics) pickerMetrics.style.display = '';
      if (sweepMetrics) sweepMetrics.style.display = 'none';
      if (backBtn) backBtn.style.display = 'none';
    } else {
      if (pickerMetrics) pickerMetrics.style.display = 'none';
      if (sweepMetrics) sweepMetrics.style.display = '';
      if (backBtn) backBtn.style.display = 'inline-flex';
    }
  }, [view]);

  // ------------------------------------------------------------------
  // Apply filters when search / decisionFilter change
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!tableRef.current) return;
    const s = search.toLowerCase().trim();
    const d = decisionFilter;
    tableRef.current.setFilter(function (data) {
      const decisionMatch =
        d === 'all' || (d === 'pending' && !data.decision) || data.decision === d;
      const searchMatch =
        !s ||
        data.company_name.toLowerCase().includes(s) ||
        (data.ticker && data.ticker.toLowerCase().includes(s)) ||
        (data.sector_label && data.sector_label.toLowerCase().includes(s));
      return decisionMatch && searchMatch;
    });
  }, [search, decisionFilter]);

  // ------------------------------------------------------------------
  // Cleanup table on unmount
  // ------------------------------------------------------------------
  useEffect(() => {
    return () => {
      if (tableRef.current) {
        tableRef.current.destroy();
        tableRef.current = null;
      }
    };
  }, []);

  // ------------------------------------------------------------------
  // Data loading
  // ------------------------------------------------------------------

  async function loadSweeps() {
    try {
      const data = await apiGet('/research/workflow/api/sweeps');
      if (!data.success) return;
      const list = data.sweeps || [];
      setSweeps(list);
      updatePickerMetrics(list);
    } catch (err) {
      console.error('Load sweeps error:', err);
    }
  }

  async function loadKillChecklist() {
    try {
      const data = await apiGet('/research/workflow/api/sweep/kill-checklist');
      if (data.success) setKillCriteria(data.criteria || []);
    } catch (err) {
      console.error('Load kill checklist error:', err);
    }
  }

  // ------------------------------------------------------------------
  // Picker metrics (bridge to header)
  // ------------------------------------------------------------------

  function updatePickerMetrics(sweepsList) {
    let totalAll = 0,
      reviewedAll = 0,
      inboxAll = 0,
      killedAll = 0;
    sweepsList.forEach((s) => {
      totalAll += s.total_companies;
      reviewedAll += s.reviewed;
      inboxAll += s.inbox_count;
      killedAll += s.killed_count;
    });
    setDomText('metricCountries', sweepsList.length);
    setDomText('metricTotalAll', totalAll);
    setDomText('metricReviewedAll', reviewedAll);
    setDomText('metricInboxAll', inboxAll);
    setDomText('metricKilledAll', killedAll);
  }

  // ------------------------------------------------------------------
  // Sweep stats (bridge to header)
  // ------------------------------------------------------------------

  function updateStats() {
    const companies = companiesRef.current;
    const total = companies.length;
    let reviewed = 0,
      inbox = 0,
      killed = 0;
    companies.forEach((c) => {
      if (c.decision) reviewed++;
      if (c.decision === 'inbox') inbox++;
      if (c.decision === 'killed') killed++;
    });
    setDomText('metricTotal', total);
    setDomText('metricReviewed', reviewed);
    setDomText('metricInbox', inbox);
    setDomText('metricKilled', killed);
    setStats({ total, reviewed, inbox, killed });
  }

  // ------------------------------------------------------------------
  // Sweep selection
  // ------------------------------------------------------------------

  async function handleSelectSweep(sweepId) {
    setView('table');
    setSearch('');
    setDecisionFilter('all');

    try {
      const data = await apiGet('/research/workflow/api/sweep/' + sweepId + '/companies');
      if (!data.success) return;
      companiesRef.current = data.companies;
      requestAnimationFrame(() => {
        buildTable(data.companies);
        updateStats();
      });
    } catch (err) {
      console.error('Load companies error:', err);
    }
  }

  function handleShowPicker() {
    if (tableRef.current) {
      tableRef.current.destroy();
      tableRef.current = null;
    }
    setView('picker');
    setSearch('');
    setDecisionFilter('all');
    loadSweeps();
  }

  // ------------------------------------------------------------------
  // Tabulator table
  // ------------------------------------------------------------------

  function buildSectorSelect(companyId, currentSectorId) {
    let html =
      '<select class="sweep-sector-select" onchange="MarketSweep.updateSector(' +
      companyId +
      ', this.value)">';
    html += '<option value="">\u2014 Sector \u2014</option>';
    (sectors || []).forEach((s) => {
      const selected = currentSectorId && s.id === currentSectorId ? ' selected' : '';
      html += '<option value="' + s.id + '"' + selected + '>' + escapeHtml(s.name) + '</option>';
    });
    html += '</select>';
    return html;
  }

  function buildTable(companies) {
    if (tableRef.current) {
      tableRef.current.destroy();
      tableRef.current = null;
    }

    tableRef.current = createDataTable('#sweepTable', {
      data: companies,
      columns: [
        {
          title: '#',
          field: 'sort_order',
          sorter: 'number',
          hozAlign: 'center',
          minWidth: 50,
          formatter: function (cell) {
            return (
              '<span style="color:var(--text-secondary);font-size:0.8rem">' +
              cell.getValue() +
              '</span>'
            );
          },
        },
        {
          title: 'Company',
          field: 'company_name',
          sorter: 'string',
          minWidth: 180,
          widthGrow: 2,
          formatter: function (cell) {
            var row = cell.getRow().getData();
            var ticker = row.ticker
              ? '<br><span class="sweep-company-cell__ticker">' +
                escapeHtml(row.ticker) +
                '</span>'
              : '';
            return (
              '<div class="sweep-company-cell"><span class="sweep-company-cell__name">' +
              escapeHtml(cell.getValue()) +
              '</span>' +
              ticker +
              '</div>'
            );
          },
        },
        {
          title: 'Sector',
          field: 'sector_label',
          sorter: 'string',
          minWidth: 120,
          formatter: function (cell) {
            var row = cell.getRow().getData();
            if (row.decision === 'inbox') {
              return buildSectorSelect(row.id, row.decision_sector_id);
            }
            var val = cell.getValue();
            return val
              ? '<span style="font-size:0.85rem">' + escapeHtml(val) + '</span>'
              : '<span class="table-cell-muted">&mdash;</span>';
          },
        },
        {
          title: 'Market Cap',
          field: 'market_cap',
          sorter: 'string',
          hozAlign: 'center',
          minWidth: 90,
          formatter: function (cell) {
            var val = cell.getValue();
            return val
              ? '<span style="font-size:0.85rem">' + escapeHtml(val) + '</span>'
              : '<span class="table-cell-muted">&mdash;</span>';
          },
        },
        {
          title: 'Exchange',
          field: 'exchange',
          sorter: 'string',
          hozAlign: 'center',
          minWidth: 80,
          formatter: function (cell) {
            var val = cell.getValue();
            return val
              ? '<span style="font-size:0.85rem">' + escapeHtml(val) + '</span>'
              : '<span class="table-cell-muted">&mdash;</span>';
          },
        },
        {
          title: 'Decision',
          field: 'decision',
          sorter: 'string',
          hozAlign: 'center',
          minWidth: 90,
          formatter: function (cell) {
            var val = cell.getValue();
            if (!val)
              return '<span class="sweep-decision-badge sweep-decision-badge--pending">Pending</span>';
            var map = {
              inbox: 'sweep-decision-badge--inbox',
              killed: 'sweep-decision-badge--killed',
            };
            var labels = { inbox: 'Inbox', killed: 'Killed' };
            return (
              '<span class="sweep-decision-badge ' +
              (map[val] || '') +
              '">' +
              (labels[val] || val) +
              '</span>'
            );
          },
        },
        {
          title: '',
          field: 'decision',
          headerSort: false,
          hozAlign: 'right',
          minWidth: 180,
          formatter: function (cell) {
            var row = cell.getRow().getData();
            if (row.decision) {
              var html = '<div class="sweep-actions">';
              if (row.decision === 'inbox' && row.promoted_idea_id) {
                html +=
                  '<a href="/ideas/' +
                  row.promoted_idea_id +
                  '/promote" class="sweep-action-btn sweep-action-btn--inbox">Start Research</a>';
              } else {
                html +=
                  '<button class="sweep-action-btn sweep-action-btn--done" disabled>Done</button>';
              }
              html +=
                '<button class="sweep-action-btn" onclick="MarketSweep.undoDecision(' +
                row.id +
                ')" title="Undo"><i class="bi bi-arrow-counterclockwise"></i></button>';
              html += '</div>';
              return html;
            }
            var safeName = escapeHtml(row.company_name).replace(/'/g, "\\'");
            return (
              '<div class="sweep-actions">' +
              '<button class="sweep-action-btn sweep-action-btn--inbox" onclick="MarketSweep.decide(' + row.id + ',\'inbox\')">Inbox</button>' +
              '<button class="sweep-action-btn sweep-action-btn--kill" onclick="MarketSweep.openKill(' + row.id + ',\'' + safeName + '\')" title="Kill">Kill</button>' +
              '</div>'
            );
          },
        },
      ],
      customConfig: {
        index: 'id',
        layout: 'fitColumns',
        pagination: true,
        paginationSize: 10,
      },
    });
  }

  // ------------------------------------------------------------------
  // Decisions
  // ------------------------------------------------------------------

  async function handleDecide(companyId, decision, extras) {
    var payload = { sweep_company_id: companyId, decision: decision };
    if (extras) {
      if (extras.kill_reasons) payload.kill_reasons = extras.kill_reasons;
      if (extras.notes) payload.notes = extras.notes;
      if (extras.sector_id) payload.sector_id = extras.sector_id;
      if (extras.idea_status) payload.idea_status = extras.idea_status;
      if (extras.kill_mode) payload.kill_mode = extras.kill_mode;
      if (extras.kill_reason_text) payload.kill_reason_text = extras.kill_reason_text;
    }

    if (window.showToast) window.showToast('Processing\u2026', 'loading');

    try {
      var data = await apiPost('/research/workflow/api/sweep/decide', payload);
      if (!data.success) {
        if (window.showToast) window.showToast('Error: ' + (data.error || 'Unknown error'), 'danger');
        return;
      }
      for (var i = 0; i < companiesRef.current.length; i++) {
        if (companiesRef.current[i].id === companyId) {
          companiesRef.current[i].decision = decision;
          companiesRef.current[i].promoted_idea_id = data.promoted_idea_id || null;
          if (extras && extras.sector_id)
            companiesRef.current[i].decision_sector_id = parseInt(extras.sector_id);
          break;
        }
      }
      if (tableRef.current) {
        await tableRef.current.updateData([
          {
            id: companyId,
            decision: decision,
            decision_sector_id: extras ? extras.sector_id || null : null,
            promoted_idea_id: data.promoted_idea_id || null,
          },
        ]);
        tableRef.current.redraw(true);
      }
      updateStats();

      var labels = { inbox: 'Sent to Inbox', killed: 'Killed' };
      if (window.showToast)
        window.showToast(labels[decision] || decision, decision === 'inbox' ? 'success' : 'info');
    } catch (err) {
      if (window.showToast) window.showToast('Network error \u2014 please try again', 'danger');
      console.error('Decide error:', err);
    }
  }

  async function handleUndoDecision(companyId) {
    try {
      var data = await apiPost('/research/workflow/api/sweep/undo', {
        sweep_company_id: companyId,
      });
      if (!data.success) {
        if (window.showToast) window.showToast('Error: ' + (data.error || 'Unknown error'), 'danger');
        return;
      }
      for (var i = 0; i < companiesRef.current.length; i++) {
        if (companiesRef.current[i].id === companyId) {
          companiesRef.current[i].decision = null;
          companiesRef.current[i].decision_sector_id = null;
          companiesRef.current[i].promoted_idea_id = null;
          break;
        }
      }
      if (tableRef.current) {
        await tableRef.current.updateData([
          { id: companyId, decision: null, decision_sector_id: null, promoted_idea_id: null },
        ]);
        tableRef.current.redraw(true);
      }
      updateStats();
      if (window.showToast) window.showToast('Decision undone', 'info');
    } catch (err) {
      if (window.showToast) window.showToast('Network error \u2014 please try again', 'danger');
      console.error('Undo error:', err);
    }
  }

  async function handleUpdateSector(companyId, sectorId) {
    try {
      var data = await apiPost('/research/workflow/api/sweep/decide', {
        sweep_company_id: companyId,
        decision: 'inbox',
        sector_id: sectorId ? parseInt(sectorId) : null,
      });
      if (data.success) {
        for (var i = 0; i < companiesRef.current.length; i++) {
          if (companiesRef.current[i].id === companyId) {
            companiesRef.current[i].decision_sector_id = sectorId ? parseInt(sectorId) : null;
            break;
          }
        }
        if (window.showToast) window.showToast('Sector updated', 'success');
      }
    } catch (err) {
      console.error('Update sector error:', err);
    }
  }

  function handleOpenKill(companyId, companyName) {
    setKillTarget({ id: companyId, name: companyName });
  }

  // ------------------------------------------------------------------
  // Kill modal callbacks
  // ------------------------------------------------------------------

  function handleConfirmKill(extras) {
    if (killTarget) handleDecide(killTarget.id, 'killed', extras);
    setKillTarget(null);
  }

  function handleConfirmInbox(extras) {
    if (killTarget) handleDecide(killTarget.id, 'inbox', extras);
    setKillTarget(null);
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  var pct = stats.total ? Math.round((stats.reviewed / stats.total) * 100) : 0;

  return (
    <>
      {view === 'picker' && <SweepPicker sweeps={sweeps} onSelect={handleSelectSweep} />}

      {view === 'table' && (
        <div>
          <div className="sweep-progress-bar-container">
            <div className="sweep-progress-bar">
              <div className="sweep-progress-fill" style={{ width: pct + '%' }} />
            </div>
          </div>
          <div className="rcl-panel">
            <div className="rcl-panel-controls">
              <div className="rcl-search">
                <i className="bi bi-search" />
                <input
                  type="text"
                  placeholder="Search company or ticker..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <select
                className="rcl-filter-select"
                value={decisionFilter}
                onChange={(e) => setDecisionFilter(e.target.value)}
              >
                <option value="all">All Companies</option>
                <option value="pending">Pending</option>
                <option value="inbox">Inbox</option>
                <option value="killed">Killed</option>
              </select>
            </div>
            <div id="sweepTable" />
          </div>
        </div>
      )}

      {killTarget && (
        <KillChecklistModal
          target={killTarget}
          criteria={killCriteria}
          onConfirmKill={handleConfirmKill}
          onConfirmInbox={handleConfirmInbox}
          onClose={() => setKillTarget(null)}
        />
      )}
    </>
  );
}
