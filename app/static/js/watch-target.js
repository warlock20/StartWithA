/* Watchlist valuation target fields (Move to Watchlist modal).
 * WatchTarget.init(container, metricsUrl) fetches current values once, then drives
 * the metric switch, the -10/-15/-20/-30% chips and the live "needs to fall". */
(function () {
    'use strict';

    var DEFS = {
        price: { label: 'Buy-below price', short: 'price', unit: false, dec: 2 },
        market_cap: { label: 'Market cap at or below', short: 'market cap', unit: true, dec: 1 },
        enterprise_value: { label: 'Enterprise value at or below', short: 'EV', unit: true, dec: 1 }
    };
    var SYMBOLS = { EUR: '€', USD: '$', GBP: '£', JPY: '¥', CHF: 'CHF ', CAD: 'C$', AUD: 'A$' };

    function parseTarget(raw) {
        var text = String(raw || '').trim();
        if (!text) { return null; }
        text = text.indexOf('.') !== -1 ? text.replace(/,/g, '') : text.replace(',', '.');
        var n = parseFloat(text);
        return isFinite(n) && n > 0 ? n : null;
    }

    function init(container, metricsUrl, initial) {
        if (!container || container.dataset.wtReady) { return; }
        container.dataset.wtReady = '1';

        var $ = function (sel) { return container.querySelector(sel); };
        var metricField = $('[data-wt-metric]');
        var currencyField = $('[data-wt-currency]');
        var input = $('[data-wt-input]');
        var tabs = container.querySelectorAll('[data-wt-tab]');
        var chips = container.querySelectorAll('[data-wt-chip]');
        var state = { metric: 'price', metrics: null, failed: false };
        if (initial && DEFS[initial.metric]) {
            // Editing a saved target: start on its metric and value, not the 15% seed.
            state.metric = initial.metric;
            input.value = String(initial.value);
        }

        function scale(metric) { return DEFS[metric].unit ? 1e9 : 1; }

        function current() {
            if (!state.metrics) { return null; }
            var v = state.metrics[state.metric === 'price' ? 'price' : state.metric];
            return typeof v === 'number' ? v / scale(state.metric) : null;
        }

        function symbol() {
            var cur = state.metrics && state.metrics.currency;
            return cur ? (SYMBOLS[cur] || cur + ' ') : '';
        }

        function fmt(v) {
            var d = DEFS[state.metric];
            return symbol() + v.toFixed(d.dec) + (d.unit ? 'B' : '');
        }

        function render() {
            var d = DEFS[state.metric];
            var cur = current();
            var t = parseTarget(input.value);

            metricField.value = state.metric;
            $('[data-wt-label]').textContent = d.label;
            $('[data-wt-short]').textContent = d.short;
            $('[data-wt-suffix]').classList.toggle('d-none', !d.unit);
            $('[data-wt-prefix]').textContent = (state.metrics && state.metrics.currency) || '';
            tabs.forEach(function (tab) {
                var on = tab.dataset.wtTab === state.metric;
                tab.classList.toggle('active', on);
                tab.setAttribute('aria-pressed', on ? 'true' : 'false');
            });

            var currentBox = $('[data-wt-current]');
            if (state.failed) { currentBox.textContent = 'Could not fetch current values'; }
            else if (!state.metrics) { currentBox.textContent = 'Loading…'; }
            else { currentBox.textContent = cur === null ? 'Not available' : fmt(cur); }

            var drop = $('[data-wt-drop]');
            if (cur === null || t === null) { drop.textContent = '—'; }
            else if (t >= cur) { drop.textContent = 'Already at target'; }
            else { drop.textContent = ((cur - t) / cur * 100).toFixed(1) + '%'; }

            renderImplied(t);
            chips.forEach(function (chip) { chip.disabled = cur === null; });
        }

        function renderImplied(t) {
            var box = $('[data-wt-implied]');
            var m = state.metrics;
            var shares = m && m.shares_outstanding;
            var text = '';
            if (t !== null && shares > 0 && state.metric !== 'price') {
                var perShare;
                if (state.metric === 'market_cap') {
                    perShare = t * 1e9 / shares;
                    text = '≈ ' + symbol() + perShare.toFixed(0) + ' per share at today’s ' +
                        (shares / 1e6).toFixed(0) + 'M shares. The target holds through splits and buybacks.';
                } else if (typeof m.enterprise_value === 'number' && typeof m.market_cap === 'number') {
                    var netDebt = m.enterprise_value - m.market_cap;
                    perShare = (t * 1e9 - netDebt) / shares;
                    text = '≈ ' + symbol() + perShare.toFixed(0) + ' per share today. Accounts for debt and cash.';
                }
            }
            box.textContent = text;
            box.classList.toggle('d-none', text === '');
        }

        function seedTarget() {
            var cur = current();
            if (cur !== null) { input.value = (cur * 0.85).toFixed(DEFS[state.metric].dec); }
        }

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                if (tab.disabled) { return; }
                state.metric = tab.dataset.wtTab;
                seedTarget();
                render();
            });
        });
        chips.forEach(function (chip) {
            chip.addEventListener('click', function () {
                var cur = current();
                if (cur === null) { return; }
                input.value = (cur * (1 - Number(chip.dataset.wtChip) / 100)).toFixed(DEFS[state.metric].dec);
                render();
            });
        });
        input.addEventListener('input', render);
        render();

        fetch(metricsUrl, { headers: { 'Accept': 'application/json' }, credentials: 'same-origin' })
            .then(function (resp) {
                if (!resp.ok) { throw new Error('metrics ' + resp.status); }
                return resp.json();
            })
            .then(function (m) {
                state.metrics = m;
                currencyField.value = m.currency || '';
                tabs.forEach(function (tab) {
                    tab.disabled = typeof m[tab.dataset.wtTab] !== 'number';
                });
                if (!input.value) { seedTarget(); }
                render();
            })
            .catch(function () {
                state.failed = true;
                render();
            });
    }

    window.WatchTarget = { init: init };
})();
