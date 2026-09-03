import { useState, useEffect, useRef } from 'react';
import { apiGet, apiPost } from '../../lib/api';
import { createDataTable } from '../../lib/dataTable';
import { SweepPicker } from './SweepPicker';
import { KillChecklistModal } from './KillChecklistModal';
import { AlphabetProgress } from './AlphabetProgress';
import { SessionTracker } from './SessionTracker';
import { FocusMode } from './FocusMode';
import { displayState, isHeld, statusLabel } from './rowState';

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

// escapeHtml covers &, < and > (it round-trips through a text node), which is
// enough for element content but NOT for a value landing inside a double-quoted
// attribute: an unescaped " closes the attribute early and everything after it
// is parsed as further markup. Every attribute interpolation goes through this
// one helper so the rule lives in a single place rather than being re-derived,
// slightly differently, at each call site.
function escapeAttr(value) {
  return escapeHtml(value).replace(/"/g, '&quot;');
}

function setDomText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

// The Status column sorts by the label the badge actually shows, not by the
// stored decision behind it: the stored value can contradict the derived state
// (a row marked "inbox" whose company was later killed), and sorting by it
// would group rows by something the user cannot see.
export function statusSorter(a, b, aRow, bRow) {
  return statusLabel(aRow.getData()).localeCompare(statusLabel(bRow.getData()));
}

// The stored decision records one moment. The state is derived on read from the
// company the row is linked to, so it cannot go stale -- that staleness is the
// defect this replaces. A row with no link has no state to show: a name match is
// offered as a suggestion and never styled as though it were decided.
export function statusBadge(row) {
  var state = displayState(row);
  if (state) {
    var cls = 'sweep-state-badge sweep-state-badge--' + escapeAttr(state.stage) +
      (state.is_dead ? ' sweep-state-badge--dead' : '');
    var title = state.reason
      ? ' title="' + escapeAttr(state.reason) + '"'
      : '';
    return '<span class="' + cls + '"' + title + '>' +
      escapeHtml(state.label) + '</span>';
  }

  if (row.suggestion) {
    var hint = missingDataHint(row);
    var hintHtml = hint ? '<span class="sweep-suggestion">' + escapeHtml(hint) + '</span>' : '';
    return '<span class="sweep-decision-badge sweep-decision-badge--pending">' +
      'Pending</span><span class="sweep-suggestion">Maybe ' +
      escapeHtml(row.suggestion.name) + '</span>' + hintHtml;
  }

  return '<span class="sweep-decision-badge sweep-decision-badge--pending">' +
    'Pending</span>';
}

// One mechanism, not one badge per column: it answers "what is missing HERE, and
// would it change anything?" Almost no row carries an ISIN, so flagging every row
// that lacks one would be noise. It is worth saying only where the value would
// have resolved the row outright -- i.e. where a name is currently the only
// evidence there is.
export function missingDataHint(row) {
  if (row.link || row.state) return null;
  if (!row.suggestion) return null;
  if (row.suggestion.basis === 'isin') return null;
  if (row.isin) return null;
  return 'No ISIN — matched by name only';
}

// What a typed ISIN cell should do, decided before any request is made.
//
// The value is normalised the way the server normalises it, so re-typing the
// same identifier in a different case never becomes a write.
//
// Clearing is refused rather than saved. No other path in this feature erases a
// stored ISIN -- a blank cell in an uploaded file means "unknown", never "delete
// what is stored" -- and an ISIN that has already been used to link rows would
// leave those links behind with nothing left to justify them.
export function isinEditOutcome(oldValue, newValue) {
  var next = String(newValue == null ? '' : newValue).trim().toUpperCase();
  var prev = String(oldValue == null ? '' : oldValue).trim().toUpperCase();
  if (next === prev) return { action: 'none', value: prev };
  if (!next) return { action: 'refused', value: prev };
  return { action: 'save', value: next };
}

// The server decides why confirmation is needed -- a normalised-name match,
// or since #330 step 4a, an ISIN match -- and sends a basis-specific reason
// in the decide response's `error`. Prefer that; fall back to the generic
// phrasing below only when the server didn't send one. Either way the server
// refuses to pick silently, so the user is asked before an existing company
// is reused or a new one is created.
export function confirmationMessage(row, candidate, serverMessage) {
  var label = candidate.ticker
    ? candidate.name + ' (' + candidate.ticker + ')'
    : candidate.name;
  // row lookup can fail (e.g. the sweep changed underneath an in-flight
  // decide) — fall back to a neutral phrase instead of printing "undefined".
  var rowLabel = row && row.company_name ? '"' + row.company_name + '"' : 'this row';
  var reason = serverMessage || ('You already have ' + label + '.');
  return reason + '\n\n' +
    'Is the sweep row ' + rowLabel + ' the same company?\n\n' +
    'OK reuses it. Cancel creates a new company. Which is it?';
}

// The actions column mirrors the row's linking state alongside its decision
// state: a suggestion offers Confirm/Dismiss, an existing link offers Unlink
// (labelled with where it came from, so the user isn't left guessing), and
// the decide/undo controls are unchanged. A dead row keeps every action --
// hiding them would leave a user who disagrees with the derived state no
// recourse. The one exception is `held`: the user already owns that
// company, so Kill is withheld.
export function actionsCell(row) {
  var html = '<div class="sweep-actions">';

  if (row.suggestion && !row.link) {
    html +=
      '<button class="sweep-action-btn sweep-action-btn--inbox" onclick="MarketSweep.confirmLink(' +
      row.id + ',' + row.suggestion.company_id + ')">Confirm</button>';
    html +=
      '<button class="sweep-action-btn sweep-action-btn--skip" onclick="MarketSweep.dismissSuggestion(' +
      row.id + ')">Dismiss</button>';
  }

  if (row.link) {
    var origin = escapeHtml(row.link.origin);
    var originAttr = escapeAttr(row.link.origin);
    html +=
      '<button class="sweep-action-btn" onclick="MarketSweep.unlinkRow(' + row.id +
      ')" title="Linked via ' + originAttr + '">Unlink (' + origin + ')</button>';
  }

  if (row.decision) {
    if (row.decision === 'inbox' && row.promoted_idea_id) {
      html +=
        '<a href="/ideas/' + row.promoted_idea_id +
        '/promote" class="sweep-action-btn sweep-action-btn--inbox">Start Research</a>';
    } else {
      html += '<button class="sweep-action-btn sweep-action-btn--done" disabled>Done</button>';
    }
    html +=
      '<button class="sweep-action-btn" onclick="MarketSweep.undoDecision(' + row.id +
      ')" title="Undo"><i class="bi bi-arrow-counterclockwise"></i></button>';
  } else {
    // safeName lands inside a double-quoted HTML attribute AND inside a
    // single-quoted JS string literal within it -- escapeHtml alone only
    // covers &/</>, so \, " and ' each need explicit handling, IN THIS
    // ORDER (order matters -- each later replacement must not touch a
    // backslash a prior step just inserted):
    //   1. \  -> \\   doubles every literal backslash FIRST. Skipping this
    //      step lets an attacker-supplied backslash immediately before a
    //      quote consume the *next* step's escaping backslash instead of
    //      the quote -- e.g. name `x\' ); alert(1); //` would otherwise
    //      produce `'x\\' ); alert(1); //'`: the JS parser reads that as
    //      one literal backslash, then an unescaped `'` that closes the
    //      string early, letting `alert(1);` run as a real statement.
    //   2. "  -> &quot;  stops the HTML parser from treating a raw quote as
    //      the attribute's closing delimiter (it decodes back to a literal
    //      " inside the JS string, inert there since that string is
    //      single-quoted).
    //   3. '  -> \'   escapes the quote that actually delimits the JS
    //      string literal -- safe now because step 1 already doubled any
    //      backslash that could otherwise have swallowed this one.
    var safeName = escapeHtml(row.company_name)
      .replace(/\\/g, '\\\\')
      .replace(/"/g, '&quot;')
      .replace(/'/g, "\\'");
    html +=
      '<button class="sweep-action-btn sweep-action-btn--inbox" onclick="MarketSweep.decide(' +
      row.id + ',\'inbox\')">Inbox</button>';
    if (!isHeld(row)) {
      html +=
        '<button class="sweep-action-btn sweep-action-btn--kill" onclick="MarketSweep.openKill(' +
        row.id + ',\'' + safeName + '\')" title="Kill">Kill</button>';
    }
  }

  html += '</div>';
  return html;
}

/**
 * MarketSweep — "Start with A's" React island.
 *
 * When sweepId is provided (sweep view page), renders alphabet progress,
 * session tracker, view toggle (Focus Mode / Table View), and the
 * active view (focus card or Tabulator table) plus kill-checklist modal.
 *
 * Props (via config):
 *   sectors: Array<{ id, name }> — available sectors for inbox assignment
 *   sweepId: number — sweep to load (always provided from sweep view route)
 *   isAdmin: boolean — whether the current user may edit sweep-row ISINs
 */
export function MarketSweep({ sectors, sweepId, isAdmin }) {
  const [view, setView] = useState(sweepId ? 'sweep' : 'picker');
  const [viewMode, setViewMode] = useState('focus');
  const [sweeps, setSweeps] = useState([]);
  const [search, setSearch] = useState('');
  const [decisionFilter, setDecisionFilter] = useState('all');
  const [killTarget, setKillTarget] = useState(null);
  const [killCriteria, setKillCriteria] = useState([]);
  const [stats, setStats] = useState({ total: 0, reviewed: 0, inbox: 0, killed: 0 });
  const [loading, setLoading] = useState(true);
  const [tableLoading, setTableLoading] = useState(false);
  const [newChecklistBanner, setNewChecklistBanner] = useState(null);

  const tableRef = useRef(null);
  const companiesRef = useRef([]);
  const handlersRef = useRef({});
  const sessionStatsRef = useRef({ reviewed: 0, inbox: 0, killed: 0 });
  // Tracks which sweep is currently loaded so reloadCompanies() can refetch
  // it without an id argument (decide/undo handlers only know a company id).
  const currentSweepIdRef = useRef(null);
  // Sequences overlapping reloads — see reloadCompanies().
  const reloadGenRef = useRef(0);

  // ------------------------------------------------------------------
  // Keep handler refs current so the global API always calls latest fns
  // ------------------------------------------------------------------
  handlersRef.current = {
    decide: handleDecide,
    undoDecision: handleUndoDecision,
    updateSector: handleUpdateSector,
    openKill: handleOpenKill,
    showPicker: handleShowPicker,
    confirmLink: handleConfirmLink,
    unlinkRow: handleUnlinkRow,
    dismissSuggestion: handleDismissSuggestion,
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
      confirmLink: (...args) => handlersRef.current.confirmLink(...args),
      unlinkRow: (...args) => handlersRef.current.unlinkRow(...args),
      dismissSuggestion: (...args) => handlersRef.current.dismissSuggestion(...args),
    };
    return () => {
      delete window.MarketSweep;
    };
  }, []);

  // ------------------------------------------------------------------
  // Load data on mount
  // ------------------------------------------------------------------
  useEffect(() => {
    if (sweepId) {
      handleSelectSweep(sweepId);
    } else {
      loadSweeps();
    }
    loadKillChecklist();
  }, []);

  // ------------------------------------------------------------------
  // Apply filters when search / decisionFilter change (table view only)
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
        (data.sector_label && data.sector_label.toLowerCase().includes(s)) ||
        (data.decision_notes && data.decision_notes.toLowerCase().includes(s));
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
  // Build / destroy table when viewMode changes
  // ------------------------------------------------------------------
  useEffect(() => {
    if (viewMode === 'table' && !tableLoading && companiesRef.current.length > 0) {
      requestAnimationFrame(() => {
        buildTable(companiesRef.current);
      });
    }
    return () => {
      if (tableRef.current) {
        tableRef.current.destroy();
        tableRef.current = null;
      }
    };
  }, [viewMode, tableLoading]);

  // ------------------------------------------------------------------
  // Data loading
  // ------------------------------------------------------------------

  async function loadSweeps() {
    setLoading(true);
    try {
      const data = await apiGet('/research/workflow/api/sweeps');
      if (!data.success) return;
      const list = data.sweeps || [];
      setSweeps(list);
      updatePickerMetrics(list);
    } catch (err) {
      console.error('Load sweeps error:', err);
    } finally {
      setLoading(false);
    }
  }

  async function loadKillChecklist() {
    try {
      const data = await apiGet('/research/workflow/api/sweep/kill-checklist');
      if (data.success) {
        setKillCriteria(data.criteria || []);
        if (data.is_new) {
          setNewChecklistBanner(
            'A default kill checklist has been created for you. You can customize it from the Ideas page.',
          );
        }
      }
    } catch (err) {
      console.error('Load kill checklist error:', err);
    }
  }

  // ------------------------------------------------------------------
  // Picker metrics (bridge to header — legacy fallback)
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

    var pct = total > 0 ? Math.round((reviewed / total) * 100) : 0;
    var findRate = reviewed > 0 ? ((inbox / reviewed) * 100).toFixed(1) : '0.0';

    // Update header DOM bridge
    setDomText('metricReviewedSlash', reviewed + '/' + total);
    setDomText('metricPctComplete', pct + '%');
    setDomText('metricInbox', inbox);
    setDomText('metricKilled', killed);
    setDomText('metricFindRate', findRate + '%');

    setStats({ total, reviewed, inbox, killed });
  }

  // ------------------------------------------------------------------
  // Sweep selection
  // ------------------------------------------------------------------

  // Single loader for a sweep's companies. Used both on initial sweep
  // selection and to refresh companiesRef (and the table) after a decide/
  // undo, so the row's derived `state` never lags behind the action that
  // just changed it -- /decide and /undo don't return `state` themselves.
  async function reloadCompanies() {
    const id = currentSweepIdRef.current;
    if (!id) return;
    // Two quick decisions put two GETs in flight at once, and responses can
    // land in any order. Without this, whichever LANDS last wins rather than
    // whichever was ISSUED last: an older reload's payload -- taken before the
    // newer decision existed -- overwrites the newer one, so progress falls
    // back and an already-decided row returns to the queue as pending. Stamp
    // each request and let only the newest one write.
    const gen = ++reloadGenRef.current;
    const data = await apiGet('/research/workflow/api/sweep/' + id + '/companies');
    if (gen !== reloadGenRef.current) return;
    if (!data.success) return;
    companiesRef.current = data.companies;
    updateStats();
    if (tableRef.current) {
      await tableRef.current.replaceData(companiesRef.current);
    }
  }

  async function handleSelectSweep(id) {
    setView('sweep');
    setSearch('');
    setDecisionFilter('all');
    setTableLoading(true);
    currentSweepIdRef.current = id;

    try {
      await reloadCompanies();
    } catch (err) {
      console.error('Load companies error:', err);
    } finally {
      setTableLoading(false);
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
          // Sweep rows are global, so the value is visible to everyone and
          // editable only by an admin. A non-admin gets the column read-only
          // rather than not at all: the table already tells them when an ISIN
          // is missing, so hiding the ones that exist made the gap look larger
          // than it is.
          title: 'ISIN',
          field: 'isin',
          sorter: 'string',
          hozAlign: 'center',
          minWidth: 130,
          cssClass: 'sweep-isin-col',
          editor: isAdmin ? 'input' : false,
          cellEdited: function (cell) {
            handleIsinCellEdit(cell);
          },
          formatter: function (cell) {
            var val = cell.getValue();
            if (val) return '<span class="sweep-isin-cell">' + escapeHtml(val) + '</span>';
            return isAdmin
              ? '<span class="table-cell-muted sweep-isin-cell--add">add ISIN</span>'
              : '<span class="table-cell-muted">&mdash;</span>';
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
          title: 'Notes',
          field: 'decision_notes',
          sorter: 'string',
          minWidth: 140,
          widthGrow: 2,
          formatter: function (cell) {
            var val = cell.getValue();
            if (!val) return '<span class="table-cell-muted">&mdash;</span>';
            var escaped = escapeHtml(val);
            var truncated = val.length > 50 ? escapeHtml(val.substring(0, 50)) + '&hellip;' : escaped;
            return '<span class="sweep-notes-cell" title="' + escapeAttr(val) + '">' + truncated + '</span>';
          },
        },
        {
          title: 'Status',
          field: 'decision',
          sorter: statusSorter,
          hozAlign: 'center',
          minWidth: 90,
          formatter: function (cell) {
            return statusBadge(cell.getRow().getData());
          },
        },
        {
          title: '',
          field: 'decision',
          headerSort: false,
          hozAlign: 'right',
          minWidth: 180,
          formatter: function (cell) {
            return actionsCell(cell.getRow().getData());
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
      if (data.needs_confirmation) {
        var row = null;
        for (var r = 0; r < companiesRef.current.length; r++) {
          if (companiesRef.current[r].id === companyId) row = companiesRef.current[r];
        }
        var reuse = window.confirm(confirmationMessage(row || {}, data.candidate, data.error));
        var followUp = Object.assign({}, payload);
        if (reuse) {
          followUp.confirm_company_id = data.candidate.id;
        } else {
          followUp.create_new = true;
        }
        data = await apiPost('/research/workflow/api/sweep/decide', followUp);
      }
      if (!data.success) {
        if (window.showToast) window.showToast('Error: ' + (data.error || 'Unknown error'), 'danger');
        return;
      }
      var updatedNotes = extras ? extras.notes || null : null;
      for (var i = 0; i < companiesRef.current.length; i++) {
        if (companiesRef.current[i].id === companyId) {
          companiesRef.current[i].decision = decision;
          companiesRef.current[i].promoted_idea_id = data.promoted_idea_id || null;
          companiesRef.current[i].decision_notes = updatedNotes;
          if (extras && extras.sector_id)
            companiesRef.current[i].decision_sector_id = parseInt(extras.sector_id);
          break;
        }
      }

      // Update session tracking
      sessionStatsRef.current.reviewed++;
      if (decision === 'inbox') sessionStatsRef.current.inbox++;
      if (decision === 'killed') sessionStatsRef.current.killed++;

      if (tableRef.current) {
        await tableRef.current.updateData([
          {
            id: companyId,
            decision: decision,
            decision_sector_id: extras ? extras.sector_id || null : null,
            promoted_idea_id: data.promoted_idea_id || null,
            decision_notes: updatedNotes,
          },
        ]);
        tableRef.current.redraw(true);
      }
      updateStats();

      // The optimistic patch above only carries the fields /decide returns.
      // The row's resolved `state` is derived server-side from the linked
      // company and is not part of that response, so refetch to keep the
      // badge from reading stale (e.g. still "Pending" right after a kill).
      await reloadCompanies();

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
          companiesRef.current[i].decision_notes = null;
          break;
        }
      }
      if (tableRef.current) {
        await tableRef.current.updateData([
          { id: companyId, decision: null, decision_sector_id: null, promoted_idea_id: null, decision_notes: null },
        ]);
        tableRef.current.redraw(true);
      }
      updateStats();

      // Same reasoning as in handleDecide: /undo doesn't return `state`,
      // so refetch to pick up the row's resolved state after the undo.
      await reloadCompanies();

      if (window.showToast) window.showToast('Decision undone', 'info');
    } catch (err) {
      if (window.showToast) window.showToast('Network error \u2014 please try again', 'danger');
      console.error('Undo error:', err);
    }
  }

  // ------------------------------------------------------------------
  // Linking (confirm a suggestion, dismiss it, or unlink a confirmed row)
  // ------------------------------------------------------------------

  // /link answers with 400 (or 404) on every refusal, and apiFetch turns any
  // non-2xx into a thrown ApiError carrying the server's message -- so a
  // resolved response here is always a success, and the refusal path is the
  // catch below, not a `success: false` body.
  async function handleConfirmLink(companyId, candidateId) {
    try {
      await apiPost('/research/workflow/api/sweep/link', {
        sweep_company_id: companyId, company_id: candidateId,
      });
      // The badge and the actions column both depend on the row's resolved
      // state/link, which /link doesn't return -- refetch, same reasoning as
      // the post-decide reload above.
      await reloadCompanies();
      if (window.showToast) window.showToast('Linked', 'success');
    } catch (e) {
      if (window.showToast) window.showToast('Error: ' + e.message, 'danger');
    }
  }

  async function handleUnlinkRow(companyId) {
    try {
      var data = await apiPost('/research/workflow/api/sweep/unlink', {
        sweep_company_id: companyId,
      });
      if (window.showToast) {
        window.showToast(data.removed ? 'Link removed' : 'Nothing to unlink',
                         data.removed ? 'success' : 'info');
      }
      if (data.removed) await reloadCompanies();
    } catch (e) {
      if (window.showToast) window.showToast('Error: ' + e.message, 'danger');
    }
  }

  // Dismissing a suggestion is a local-only "not now" -- nothing is posted,
  // so the server's name-match logic is untouched and the same suggestion
  // can resurface (e.g. after a reload). Only hide it from this session's
  // table/companiesRef.
  async function handleDismissSuggestion(companyId) {
    for (var i = 0; i < companiesRef.current.length; i++) {
      if (companiesRef.current[i].id === companyId) {
        companiesRef.current[i].suggestion = null;
        break;
      }
    }
    if (tableRef.current) {
      await tableRef.current.updateData([{ id: companyId, suggestion: null }]);
      tableRef.current.redraw(true);
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
      } else if (data.needs_confirmation) {
        if (window.showToast)
          window.showToast(
            'Set this row\u2019s decision first \u2014 the company needs to be confirmed before the sector can be applied.',
            'warning'
          );
      } else {
        if (window.showToast) window.showToast('Error: ' + (data.error || 'Unknown error'), 'danger');
      }
    } catch (err) {
      console.error('Update sector error:', err);
    }
  }

  function handleOpenKill(companyId, companyName) {
    setKillTarget({ id: companyId, name: companyName });
  }

  // Returns the stored ISIN on success, or null if the server refused it, so a
  // table cell can put back the value the edit tried to replace.
  async function handleSaveIsin(companyId, rawIsin) {
    var data;
    try {
      data = await apiPost(
        '/research/workflow/api/sweep/company/' + companyId + '/isin',
        { isin: rawIsin }
      );
    } catch (err) {
      if (window.showToast) window.showToast(err.message || 'Could not save ISIN', 'danger');
      console.error('Save ISIN error:', err);
      return null;
    }
    // The ISIN is not the only thing that can change here. Sweep rows are
    // global, so a saved identifier links the row for every user who owns a
    // company carrying it -- possibly including this one, whose state and link
    // then appear alongside it. Patching the single field would leave those
    // stale, so refetch, as every other write in this component does.
    await reloadCompanies();
    if (window.showToast) window.showToast('ISIN saved', 'success');
    return data.isin;
  }

  async function handleIsinCellEdit(cell) {
    var outcome = isinEditOutcome(cell.getOldValue(), cell.getValue());

    if (outcome.action === 'none') {
      cell.restoreOldValue();
      return;
    }
    if (outcome.action === 'refused') {
      cell.restoreOldValue();
      if (window.showToast) {
        window.showToast(
          'An ISIN can be corrected but not removed. Edit it to the right value instead.',
          'warning'
        );
      }
      return;
    }

    var companyId = cell.getRow().getData().id;
    // Show the typed value while the request is in flight; reloadCompanies()
    // replaces it with what was actually stored, and a refusal restores the old
    // one. Either way the cell never keeps a value the server did not accept.
    var saved = await handleSaveIsin(companyId, outcome.value);
    if (saved === null) cell.restoreOldValue();
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

  // Picker fallback (legacy — landing page is now server-rendered)
  if (view === 'picker') {
    return (
      <>
        <SweepPicker sweeps={sweeps} loading={loading} onSelect={handleSelectSweep} />
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

  // Sweep view
  return (
    <>
      {newChecklistBanner && (
        <div className="alert alert-info d-flex align-items-center justify-content-between py-2 mb-3" role="alert">
          <span><i className="bi bi-info-circle me-2" />{newChecklistBanner}</span>
          <button
            type="button"
            className="btn btn-sm btn-outline-primary ms-3"
            onClick={() => setNewChecklistBanner(null)}
          >
            OK
          </button>
        </div>
      )}

      {tableLoading ? (
        <div className="sweep-loading">
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
          <p>Loading companies...</p>
        </div>
      ) : (
        <>
          {/* Alphabetical Progress */}
          <AlphabetProgress companies={companiesRef.current} />

          {/* Today's Session */}
          <SessionTracker
            sessionStats={sessionStatsRef.current}
            totalCompanies={stats.total}
            totalReviewed={stats.reviewed}
          />

          {/* View Toggle */}
          <div className="sweep-view-toggle">
            <button
              className={'sweep-view-toggle__btn' + (viewMode === 'focus' ? ' active' : '')}
              onClick={() => setViewMode('focus')}
            >
              <i className="bi bi-lightning-charge-fill" /> Focus Mode
            </button>
            <button
              className={'sweep-view-toggle__btn' + (viewMode === 'table' ? ' active' : '')}
              onClick={() => setViewMode('table')}
            >
              <i className="bi bi-list" /> Table View
            </button>
          </div>

          {/* Focus Mode */}
          {viewMode === 'focus' && (
            <FocusMode
              companies={companiesRef.current}
              onDecide={handleDecide}
              onOpenKill={handleOpenKill}
              disabled={!!killTarget}
              isAdmin={isAdmin}
              onSaveIsin={handleSaveIsin}
            />
          )}

          {/* Table View */}
          {viewMode === 'table' && (
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
          )}
        </>
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
