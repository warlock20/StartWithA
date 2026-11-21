/* Expected return fields (components/expected_return_field.html).
 * A total over the timeframe is stored as the CAGR it works out to. The "Saved as"
 * box shows the CAGR that will be saved, and the timeframe is required for a total.
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

    function signed(rate) {
        return (rate >= 0 ? '+' : '') + rate.toFixed(1) + '%';
    }

    function show(box, state, label, value, detail) {
        box.hidden = false;
        box.dataset.state = state;
        box.querySelector('.expected-return-saved-label').textContent = label;
        box.querySelector('.expected-return-saved-value').textContent = value;
        box.querySelector('.expected-return-saved-detail').textContent = detail;
    }

    function update(container) {
        var p = parts(container);
        var isTotal = p.basis.value === 'total';
        if (p.timeframe) {
            if (isTotal) { p.timeframe.setAttribute('required', 'required'); }
            else { p.timeframe.removeAttribute('required'); }
        }
        var box = p.preview;
        if (!box) { return; }
        var value = number(p.value);
        if (value === null) {
            box.hidden = true;
            return;
        }
        if (!isTotal) {
            show(box, 'ok', 'Saved as', signed(value) + ' a year', 'CAGR, compared with the position\'s CAGR');
            return;
        }
        var months = number(p.timeframe);
        if (!months || months < 1) {
            show(box, 'missing', 'Timeframe needed', 'Add the expected timeframe',
                 'to turn ' + signed(value) + ' total into a yearly rate (CAGR)');
            return;
        }
        show(box, 'ok', 'Saved as', signed(cagrFromTotal(value, months)) + ' a year',
             'CAGR of ' + signed(value) + ' total over ' + months + ' months');
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
