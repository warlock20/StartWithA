/* Expected return fields (components/expected_return_field.html).
 * A total over the timeframe is stored as the CAGR it works out to, so this shows
 * that CAGR as the user types and makes the timeframe required for a total.
 * ExpectedReturn.cagr(container) gives the CAGR for scripts that send the value. */
(function () {
    'use strict';

    function number(input) {
        var n = input && input.value !== '' ? parseFloat(input.value) : NaN;
        return isFinite(n) ? n : null;
    }

    function cagrFromTotal(totalPct, months) {
        var growth = Math.max(1 + totalPct / 100, 0);
        return (Math.pow(growth, 12 / months) - 1) * 100;
    }

    function parts(container) {
        return {
            value: container.querySelector('input[name="expected_return"]'),
            basis: container.querySelector('select[name="expected_return_basis"]'),
            timeframe: document.getElementById(container.dataset.timeframeId),
            preview: container.nextElementSibling
        };
    }

    function cagr(container) {
        var p = parts(container);
        var value = number(p.value);
        if (value === null) { return null; }
        if (p.basis.value !== 'total') { return value; }
        var months = number(p.timeframe);
        return months && months >= 1 ? Math.round(cagrFromTotal(value, months) * 100) / 100 : null;
    }

    function update(container) {
        var p = parts(container);
        var isTotal = p.basis.value === 'total';
        if (p.timeframe) {
            if (isTotal) { p.timeframe.setAttribute('required', 'required'); }
            else { p.timeframe.removeAttribute('required'); }
        }
        if (!p.preview) { return; }
        if (!isTotal || number(p.value) === null) {
            p.preview.textContent = isTotal ? 'Enter the total return you expect over the timeframe.' : '';
            return;
        }
        var months = number(p.timeframe);
        if (!months || months < 1) {
            p.preview.textContent = 'Enter the timeframe to work out the yearly rate (CAGR).';
            return;
        }
        var rate = cagrFromTotal(number(p.value), months);
        p.preview.textContent = '= ' + (rate >= 0 ? '+' : '') + rate.toFixed(1) +
            '% a year over ' + months + ' months, which is what gets saved.';
    }

    function init(container) {
        if (container.dataset.erReady) { return; }
        container.dataset.erReady = '1';
        var p = parts(container);
        var run = function () { update(container); };
        [p.value, p.basis, p.timeframe].forEach(function (el) {
            if (el) {
                el.addEventListener('input', run);
                el.addEventListener('change', run);
            }
        });
        run();
    }

    function initAll() {
        Array.prototype.forEach.call(document.querySelectorAll('[data-expected-return]'), init);
    }

    window.ExpectedReturn = { cagr: cagr, init: init };
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }
})();
