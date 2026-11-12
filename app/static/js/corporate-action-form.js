/* Corporate action form: per-type fields, ratio prefill, closing-price prefill.
   Plain script, no build step. */
(function () {
    'use strict';

    var form = document.getElementById('corporateActionForm');
    if (!form) { return; }

    function $(id) { return document.getElementById(id); }
    var typeSelect = $('action_type');
    var dateInput = $('effective_date');
    var sourceField = $('source_company_id');
    var targetSelect = $('target_company_id');
    var targetTicker = $('target_ticker');
    var cashOnly = $('cash_only');
    var targetFields = $('target_fields');
    var ratioInput = $('ratio');
    var sharesInput = $('shares_received');
    var priceInput = $('price_per_share');
    var pctInput = $('cost_allocation_pct');
    var zeroCostYes = $('zero_cost_yes');
    var sdPrice = $('sd_price_per_share');
    var sourceShares = parseInt(form.dataset.sourceShares || '0', 10) || 0;
    // The server rendered sourceShares for this company and date. If either
    // changes, the number is stale until the next preview, so the ratio prefill stops.
    var renderedDate = dateInput.value;
    var renderedSource = sourceField ? sourceField.value : '';

    // Values the script filled in itself may be overwritten later; values the
    // user typed are left alone.
    var autoFilled = {};
    function autoFill(input, value) {
        if (!input) { return; }
        if (input.value === '' || autoFilled[input.id]) {
            input.value = value;
            autoFilled[input.id] = true;
        }
    }
    [priceInput, pctInput, sharesInput].forEach(function (input) {
        if (input) {
            input.addEventListener('input', function () { autoFilled[input.id] = false; });
        }
    });

    function setInputsDisabled(root, disabled) {
        root.querySelectorAll('input, select, textarea').forEach(function (el) { el.disabled = disabled; });
    }

    function applyType() {
        var type = typeSelect.value;
        var sections = form.querySelectorAll('[data-types]');
        sections.forEach(function (el) { setInputsDisabled(el, false); });
        sections.forEach(function (el) {
            var show = el.dataset.types.split(' ').indexOf(type) !== -1;
            el.style.display = show ? '' : 'none';
            if (!show) { setInputsDisabled(el, true); }
        });
        var isCashOnly = type === 'MERGER' && cashOnly && cashOnly.checked;
        if (targetFields && type === 'MERGER') {
            targetFields.style.display = isCashOnly ? 'none' : '';
            if (isCashOnly) { setInputsDisabled(targetFields, true); }
        }
        if (sdPrice) { sdPrice.disabled = sdPrice.disabled || (zeroCostYes && zeroCostYes.checked); }
        updateCurrencyLabels();
    }

    function selectedOption(select) {
        return select && select.options ? select.options[select.selectedIndex] : null;
    }

    function sourceInfo() {
        var el = sourceField;
        if (el && el.tagName === 'SELECT') { el = selectedOption(el); }
        return { ticker: el ? el.dataset.ticker || '' : '', currency: el ? el.dataset.currency || '' : '' };
    }

    function targetTickerValue() {
        var opt = selectedOption(targetSelect);
        if (opt && opt.value) { return opt.dataset.ticker; }
        return targetTicker ? targetTicker.value.trim() : '';
    }

    function updateCurrencyLabels() {
        // Spin-off cash and fees are booked on the new company's leg, in its currency.
        var opt = selectedOption(targetSelect);
        var currency = (typeSelect.value === 'SPINOFF' && opt && opt.value && opt.dataset.currency) ||
            sourceInfo().currency || 'source currency';
        form.querySelectorAll('.cash-currency').forEach(function (el) { el.textContent = currency; });
    }

    function fetchPrice(ticker, onDate) {
        if (!ticker || !onDate) { return Promise.resolve(null); }
        var url = form.dataset.priceUrl + '?ticker=' + encodeURIComponent(ticker) +
            '&date=' + encodeURIComponent(onDate);
        return fetch(url, { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (body) { return body.price; })
            .catch(function () { return null; });
    }

    function prefillRatioShares() {
        var ratio = parseFloat(ratioInput && ratioInput.value);
        if (typeSelect.value !== 'MERGER' || !(ratio > 0) || !sourceShares) { return; }
        if (dateInput.value !== renderedDate || (sourceField && sourceField.value !== renderedSource)) { return; }
        autoFill(sharesInput, String(Math.floor(sourceShares * ratio)));
    }

    function prefillPrices() {
        var on = dateInput.value;
        var type = typeSelect.value;
        if (type !== 'MERGER' && type !== 'SPINOFF') { return; }
        var targetPromise = fetchPrice(targetTickerValue(), on);
        if (type === 'MERGER') {
            targetPromise.then(function (price) {
                if (price !== null) { autoFill(priceInput, String(price)); }
            });
        } else {
            Promise.all([targetPromise, fetchPrice(sourceInfo().ticker, on)]).then(function (prices) {
                var b = prices[0], a = prices[1];
                var shares = parseInt(sharesInput && sharesInput.value, 10);
                if (b === null || a === null || !sourceShares || !(shares > 0)) { return; }
                var bValue = b * shares, aValue = a * sourceShares;
                var pct = 100 * bValue / (aValue + bValue);
                autoFill(pctInput, (Math.round(pct * 100) / 100).toString());
            });
        }
    }

    typeSelect.addEventListener('change', applyType);
    if (cashOnly) { cashOnly.addEventListener('change', applyType); }
    if (zeroCostYes) {
        form.querySelectorAll('input[name="zero_cost"]').forEach(function (r) {
            r.addEventListener('change', function () { if (sdPrice) { sdPrice.disabled = zeroCostYes.checked; } });
        });
    }
    if (sourceField && sourceField.tagName === 'SELECT') { sourceField.addEventListener('change', updateCurrencyLabels); }
    if (ratioInput) { ratioInput.addEventListener('input', prefillRatioShares); }
    if (targetSelect) { targetSelect.addEventListener('change', updateCurrencyLabels); }
    [targetSelect, targetTicker, dateInput].forEach(function (el) {
        if (el) { el.addEventListener('change', prefillPrices); }
    });
    if (sharesInput) { sharesInput.addEventListener('change', prefillPrices); }

    applyType();
    if (sdPrice && zeroCostYes && zeroCostYes.checked) { sdPrice.disabled = true; }
    if (!form.querySelector('#preview-table')) { prefillPrices(); }
})();
