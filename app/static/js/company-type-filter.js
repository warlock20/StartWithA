// Company dropdown filtering for the add-transaction page.
// Only a company you have held can have paid you a dividend, and only one
// you currently own can be sold. Watchlist companies are hidden for those
// types so the list shows what is actually actionable.
(function () {
  'use strict';

  function allowed(option, transactionType) {
    if (!option.value) return true;  // keep the "Select a company..." placeholder
    if (transactionType === 'DIVIDEND') return option.dataset.everHeld === 'true';
    if (transactionType === 'SELL') return option.dataset.hasPosition === 'true';
    return true;
  }

  function create(select, opts) {
    const hint = opts.hint;
    const hintText = opts.hintText;
    const allOptions = Array.from(select.options);
    let remembered = select.value;   // what the user last chose
    let currentType = 'BUY';
    let lastSet = select.value;      // where the controller last left the select

    // A change to a value we did not set is the user's choice: remember it.
    // A change event that finds the value we left is just a resync.
    select.addEventListener('change', () => {
      if (select.value !== lastSet) {
        remembered = select.value;
        lastSet = select.value;
      }
    });

    function fireChange(restored) {
      // A restore is the page putting the user's own choice back, so
      // handlers must not treat it as a fresh pick (e.g. overwrite a price).
      select.dispatchEvent(restored
        ? new CustomEvent('change', { detail: { restored: true } })
        : new Event('change'));
    }

    function rebuild(transactionType, { dispatch }) {
      currentType = transactionType;
      const previousValue = select.value;
      const keep = allOptions.filter(o => allowed(o, transactionType));

      // Rebuild rather than hide: browsers disagree on whether a hidden
      // <option> remains selectable.
      select.replaceChildren(...keep);

      // Restore the user's choice if this type permits it, else clear
      const target = keep.some(o => o.value === remembered) ? remembered : '';
      select.value = target;
      lastSet = select.value;

      const hiddenCount = allOptions.length - keep.length;
      if (hiddenCount > 0) {
        const shown = keep.length - 1;  // exclude the placeholder
        hintText.textContent = (transactionType === 'DIVIDEND')
          ? `Showing ${shown} ${shown === 1 ? 'company' : 'companies'} you have held — only these can pay a dividend.`
          : `Showing ${shown} ${shown === 1 ? 'company' : 'companies'} you currently own — only these can be sold.`;
        hint.style.display = 'block';
      } else {
        hint.style.display = 'none';
      }

      // Let currency/position handlers react to a changed selection
      if (dispatch && select.value !== previousValue) fireChange(select.value !== '');
    }

    function apply(transactionType) {
      rebuild(transactionType, { dispatch: true });
    }

    function addCompany(company) {
      const id = String(company.id);
      let option = allOptions.find(o => o.value === id);
      if (!option) {
        option = document.createElement('option');
        option.value = id;
        option.text = `${company.ticker_symbol} - ${company.name}`;
        option.setAttribute('data-ticker', company.ticker_symbol);
        option.setAttribute('data-has-position', 'false');
        option.setAttribute('data-ever-held', 'false');
        option.setAttribute('data-needs-journal', 'true');
        allOptions.push(option);
      }
      remembered = id;
      // Own the single change event so page handlers resync even when the
      // company is hidden by the current type
      rebuild(currentType, { dispatch: false });
      fireChange();
      return option;
    }

    return { apply, addCompany };
  }

  window.CompanyTypeFilter = { create, allowed };
})();
