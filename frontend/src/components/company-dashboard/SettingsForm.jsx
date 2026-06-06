import { useEffect, useRef } from 'react';

/**
 * SettingsForm — behaviour-only React island for the company settings AJAX save.
 *
 * The form HTML is Jinja2-rendered; this island attaches:
 *   - Form submit interception → AJAX POST with FormData
 *   - Live header updates on save (title, ticker, subtitle)
 *   - Sector dropdown "Add new sector" toggle
 *
 * Returns null — renders no visible UI.
 *
 * Props (via config):
 *   currencySymbol — e.g. "$"
 */
export function SettingsForm({ currencySymbol }) {
  var mountedRef = useRef(false);

  // ---- AJAX Form Save ----
  useEffect(function () {
    if (mountedRef.current) return;
    mountedRef.current = true;

    var editForm = document.getElementById('editCompanyForm');
    if (!editForm) return;

    function handleSubmit(e) {
      e.preventDefault();

      var saveBtn = document.getElementById('saveChangesBtn');
      saveBtn.disabled = true;
      saveBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-1"></span>Saving\u2026';

      // Handle "Add new sector" before building FormData
      var sectorSel = document.getElementById('sectorSelect');
      var newSectorInp = document.getElementById('newSectorInput');
      var formData = new FormData(editForm);

      if (
        sectorSel &&
        sectorSel.value === '__new__' &&
        newSectorInp &&
        newSectorInp.value.trim()
      ) {
        formData.set('sector', newSectorInp.value.trim());
      }

      fetch(editForm.action, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (data.success) {
            if (window.showToast) window.showToast(data.message, 'success');
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
              var tickerSpan =
                '<span class="journey-ticker">' + escapeHtml(data.ticker_symbol || '') + '</span>';
              subtitleEl.innerHTML =
                tickerSpan + (data.sector_name ? ' &middot; ' + escapeHtml(data.sector_name) : '');
            }
            // If new sector was created, add it to the dropdown
            if (sectorSel && data.sector_name) {
              var existing = sectorSel.querySelector(
                'option[value="' + CSS.escape(data.sector_name) + '"]',
              );
              if (!existing) {
                var opt = document.createElement('option');
                opt.value = data.sector_name;
                opt.textContent = data.sector_name;
                sectorSel.insertBefore(
                  opt,
                  sectorSel.querySelector('option[value="__new__"]'),
                );
              }
              sectorSel.value = data.sector_name;
              if (newSectorInp) {
                newSectorInp.classList.add('d-none');
                newSectorInp.value = '';
                newSectorInp.required = false;
              }
            }
          } else {
            if (window.showToast)
              window.showToast(data.error || 'Failed to save changes', 'danger');
          }
        })
        .catch(function () {
          if (window.showToast) window.showToast('Network error saving changes', 'danger');
        })
        .finally(function () {
          saveBtn.disabled = false;
          saveBtn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Save Changes';
          // Reset apply-ticker button if it was used
          var applyBtn = document.getElementById('applyTickerBtn');
          if (applyBtn) {
            applyBtn.disabled = false;
            applyBtn.innerHTML =
              '<i class="bi bi-arrow-repeat me-1"></i>Use ' +
              applyBtn.dataset.ticker +
              ' as company ticker';
          }
        });
    }

    editForm.addEventListener('submit', handleSubmit);
    return function () {
      editForm.removeEventListener('submit', handleSubmit);
    };
  }, []);

  // ---- Sector Dropdown "Add new" Toggle ----
  useEffect(function () {
    var sectorSel = document.getElementById('sectorSelect');
    var newSectorInp = document.getElementById('newSectorInput');
    if (!sectorSel || !newSectorInp) return;

    function handleChange() {
      if (sectorSel.value === '__new__') {
        newSectorInp.classList.remove('d-none');
        newSectorInp.required = true;
        newSectorInp.focus();
      } else {
        newSectorInp.classList.add('d-none');
        newSectorInp.required = false;
      }
    }

    sectorSel.addEventListener('change', handleChange);
    return function () {
      sectorSel.removeEventListener('change', handleChange);
    };
  }, []);

  // ---- Ticker Testing Tool ----
  useEffect(function () {
    var testTickerBtn = document.getElementById('testTickerBtn');
    var testTickerInput = document.getElementById('testTicker');
    var testResult = document.getElementById('testResult');
    if (!testTickerBtn || !testTickerInput) return;

    function handleTest() {
      var ticker = testTickerInput.value.trim().toUpperCase();
      if (!ticker) {
        testResult.className = 'alert alert-warning mt-3';
        testResult.innerHTML =
          '<i class="bi bi-exclamation-triangle me-2"></i>Please enter a ticker symbol to test.';
        testResult.classList.remove('d-none');
        return;
      }
      testTickerBtn.disabled = true;
      testTickerBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-2"></span>Testing...';
      testResult.className = 'alert alert-info mt-3';
      testResult.innerHTML =
        '<i class="bi bi-hourglass-split me-2"></i>Validating ticker symbol...';
      testResult.classList.remove('d-none');

      var cs = currencySymbol || '$';

      fetch('/companies/validate_ticker', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: ticker }),
      })
        .then(function (response) {
          return response.json();
        })
        .then(function (data) {
          if (data.valid) {
            var currentTickerEl = document.getElementById('currentTickerDisplay');
            var isSameTicker =
              data.ticker === (currentTickerEl ? currentTickerEl.textContent.trim() : '');
            var stockCurrency = data.currency || '';
            var priceLabel = data.current_price
              ? '<div class="text-muted small">Current Price</div><div class="h5 mb-0 text-success">' +
                (stockCurrency ? stockCurrency + ' ' : cs) + data.current_price.toFixed(2) + '</div>'
              : '';
            testResult.className = 'alert alert-success mt-3';
            testResult.innerHTML =
              '<div class="d-flex justify-content-between align-items-start">' +
              '<div>' +
              '<strong><i class="bi bi-check-circle-fill me-2"></i>Ticker Found!</strong>' +
              '<div class="mt-2">' +
              '<strong>' +
              data.ticker +
              '</strong> - ' +
              (data.company_name || 'N/A') +
              (data.exchange
                ? '<br><small class="text-muted">Exchange: ' + data.exchange + '</small>'
                : '') +
              (stockCurrency
                ? '<br><small class="text-muted">Currency: ' + stockCurrency + '</small>'
                : '') +
              '</div>' +
              '</div>' +
              '<div class="text-end">' +
              priceLabel +
              '</div>' +
              '</div>' +
              (isSameTicker
                ? '<div class="mt-2 text-muted"><small><i class="bi bi-info-circle me-1"></i>This is already the current ticker.</small></div>'
                : '<div class="mt-3 pt-3" style="border-top: 1px solid rgba(0,0,0,0.1);">' +
                  '<button type="button" class="btn btn-primary btn-sm" id="applyTickerBtn" data-ticker="' +
                  data.ticker +
                  '">' +
                  '<i class="bi bi-arrow-repeat me-1"></i>Use ' +
                  data.ticker +
                  ' as company ticker' +
                  '</button>' +
                  '</div>');
          } else {
            testResult.className = 'alert alert-danger mt-3';
            testResult.innerHTML =
              '<strong><i class="bi bi-x-circle-fill me-2"></i>Ticker Not Found</strong>' +
              '<div class="mt-2">' +
              (data.error || 'Could not validate this ticker symbol.') +
              '</div>' +
              "<div class=\"mt-2\"><small>Make sure you're using the correct format (e.g., AAPL for US stocks, MBB.DE for German stocks).</small></div>";
          }
        })
        .catch(function () {
          testResult.className = 'alert alert-danger mt-3';
          testResult.innerHTML =
            '<strong><i class="bi bi-x-circle-fill me-2"></i>Error</strong>' +
            '<div class="mt-2">Failed to validate ticker. Please try again.</div>';
        })
        .finally(function () {
          testTickerBtn.disabled = false;
          testTickerBtn.innerHTML = '<i class="bi bi-play-fill me-2"></i>Test Ticker';
        });
    }

    function handleKeypress(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        testTickerBtn.click();
      }
    }

    function handleApplyClick(e) {
      var applyBtn = e.target.closest('#applyTickerBtn');
      if (!applyBtn) return;
      var newTicker = applyBtn.dataset.ticker;
      if (!newTicker) return;
      applyBtn.disabled = true;
      applyBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-2"></span>Updating...';
      var form = document.getElementById('editCompanyForm');
      if (form) {
        var tickerInput = form.querySelector('input[name="ticker_symbol"]');
        if (tickerInput) {
          tickerInput.value = newTicker;
          form.requestSubmit();
        }
      }
    }

    testTickerBtn.addEventListener('click', handleTest);
    testTickerInput.addEventListener('keypress', handleKeypress);
    if (testResult) testResult.addEventListener('click', handleApplyClick);

    return function () {
      testTickerBtn.removeEventListener('click', handleTest);
      testTickerInput.removeEventListener('keypress', handleKeypress);
      if (testResult) testResult.removeEventListener('click', handleApplyClick);
    };
  }, [currencySymbol]);

  return null;
}

function escapeHtml(text) {
  if (!text) return '';
  var div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
