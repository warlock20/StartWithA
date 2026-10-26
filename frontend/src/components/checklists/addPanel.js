/**
 * Add panel for the checklist edit page.
 *
 * One block of markup (#inspector-overview) is a Bootstrap `offcanvas-lg`: inline in the
 * right-hand column on desktop, a bottom sheet on phones. Adds are posted in the background
 * so the sheet can stay open for "write another" and multi-pick from the Question Bank;
 * the tree is reloaded once the user is done (sheet closed, or "show in list" pressed).
 */

function bootstrapSheet(el) {
  var instance = window.bootstrap.Offcanvas.getOrCreateInstance(el);
  return {
    isShown: function () { return el.classList.contains('show'); },
    show: function () { instance.show(); },
    hide: function () { instance.hide(); },
  };
}

export function initAddPanel(root, deps) {
  if (!root) return function () {};
  deps = deps || {};
  var fetchImpl = deps.fetchImpl || window.fetch.bind(window);
  var reload = deps.reload || function () { window.location.reload(); };
  var getSheet = deps.getSheet || bootstrapSheet;

  var addUrl = root.dataset.addUrl;
  var parentSelect = root.querySelector('#addParent');
  var form = root.querySelector('#addItemForm');
  var status = root.querySelector('#addStatus');
  var refreshBtn = root.querySelector('#addRefresh');
  var search = root.querySelector('#bankSearch');
  var emptyMsg = root.querySelector('#bankEmpty');
  var activeSector = '';
  var added = 0;

  function setStatus(message, isError) {
    if (!status) return;
    status.textContent = message;
    status.classList.toggle('text-danger', !!isError);
    status.classList.toggle('text-success', !isError);
  }

  function noteAdded(text) {
    added += 1;
    setStatus('✓ Added “' + text + '”', false);
    if (refreshBtn) {
      refreshBtn.textContent = 'Show ' + added + ' new in list';
      refreshBtn.classList.remove('d-none');
    }
  }

  function post(fields) {
    var body = new FormData();
    Object.keys(fields).forEach(function (key) { body.append(key, fields[key] || ''); });
    body.set('parent_id', parentSelect ? parentSelect.value : '');
    return fetchImpl(addUrl, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: body,
    }).then(function (resp) {
      return resp.json().catch(function () { return {}; }).then(function (data) {
        if (!resp.ok || !data.success) throw new Error(data.message || 'Could not add the question.');
        return data.item;
      });
    });
  }

  // Desktop: the panel is inline, so reload now. Mobile: close the sheet; onHidden reloads.
  function finish() {
    var sheet = getSheet(root);
    if (sheet.isShown()) sheet.hide();
    else reload();
  }

  function onSubmit(event) {
    event.preventDefault();
    var mode = event.submitter && event.submitter.dataset.addMode;
    var buttons = form.querySelectorAll('button[type="submit"]');
    buttons.forEach(function (b) { b.disabled = true; });
    post({
      item_text: form.elements.item_text.value,
      description: form.elements.description.value,
      llm_prompt: form.elements.llm_prompt.value,
    }).then(function (item) {
      noteAdded(item.text);
      if (mode === 'another') {
        form.elements.item_text.value = '';
        form.elements.description.value = '';
        form.elements.llm_prompt.value = '';
        form.elements.item_text.focus();
      } else {
        finish();
      }
    }).catch(function (err) {
      setStatus(err.message, true);
    }).finally(function () {
      buttons.forEach(function (b) { b.disabled = false; });
    });
  }

  function onBankClick(event) {
    var btn = event.target.closest('.bank-add');
    if (!btn || !root.contains(btn)) return;
    var row = btn.closest('.bank-question');
    btn.disabled = true;
    post({
      item_text: row.dataset.text,
      llm_prompt: row.dataset.prompt,
      bank_item_id: row.dataset.bankId,
    }).then(function (item) {
      row.classList.add('is-added');
      noteAdded(item.text);
    }).catch(function (err) {
      btn.disabled = false;
      setStatus(err.message, true);
    });
  }

  function applyFilter() {
    var query = search ? search.value.trim().toLowerCase() : '';
    var visible = 0;
    root.querySelectorAll('.bank-question').forEach(function (row) {
      var match = (!activeSector || row.dataset.sector === activeSector) &&
        (!query || row.dataset.text.toLowerCase().indexOf(query) !== -1);
      row.hidden = !match;
      if (match) visible += 1;
    });
    if (emptyMsg) emptyMsg.classList.toggle('d-none', visible > 0);
  }

  function onChipClick(event) {
    var chip = event.target.closest('.bank-chip');
    if (!chip || !root.contains(chip)) return;
    root.querySelectorAll('.bank-chip').forEach(function (c) { c.classList.toggle('active', c === chip); });
    activeSector = chip.dataset.sector;
    applyFilter();
  }

  function onHidden(event) {
    if (event.target === root && added > 0) reload();
  }

  // "Add sub-question" in the item sheet: preset the parent, swap the item sheet for this one.
  function onAddUnder(event) {
    var btn = event.target.closest('[data-add-under]');
    if (!btn) return;
    if (parentSelect) parentSelect.value = btn.dataset.addUnder;
    // Focus once shown: Bootstrap's focus trap takes focus when the sheet finishes opening.
    var open = function () {
      if (form) {
        root.addEventListener('shown.bs.offcanvas', function () { form.elements.item_text.focus(); }, { once: true });
      }
      getSheet(root).show();
    };
    var from = btn.closest('.offcanvas-lg');
    if (from && getSheet(from).isShown()) {
      from.addEventListener('hidden.bs.offcanvas', open, { once: true });
      getSheet(from).hide();
    } else {
      open();
    }
  }

  if (form) form.addEventListener('submit', onSubmit);
  if (search) search.addEventListener('input', applyFilter);
  if (refreshBtn) refreshBtn.addEventListener('click', function () { reload(); });
  root.addEventListener('click', onBankClick);
  root.addEventListener('click', onChipClick);
  root.addEventListener('hidden.bs.offcanvas', onHidden);
  document.addEventListener('click', onAddUnder);

  return function () {
    if (form) form.removeEventListener('submit', onSubmit);
    if (search) search.removeEventListener('input', applyFilter);
    root.removeEventListener('click', onBankClick);
    root.removeEventListener('click', onChipClick);
    root.removeEventListener('hidden.bs.offcanvas', onHidden);
    document.removeEventListener('click', onAddUnder);
  };
}
