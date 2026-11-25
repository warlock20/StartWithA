// Decision Intelligence (portfolio/decisions_intelligence.html): tabs that load on first
// open, the URL sync, links between tabs, and the research scope switch.
(function () {
    var DISMISSED_KEY = 'di-dismissed-alerts';
    var DISMISSED_MAX = 50;

    function readDismissed() {
        try {
            var list = JSON.parse(window.localStorage.getItem(DISMISSED_KEY) || '[]');
            return Array.isArray(list) ? list : [];
        } catch (e) {
            return [];
        }
    }

    function saveDismissed(id) {
        try {
            var list = readDismissed().filter(function (item) { return item !== id; });
            list.push(id);
            window.localStorage.setItem(DISMISSED_KEY, JSON.stringify(list.slice(-DISMISSED_MAX)));
        } catch (e) {
            // Storage is unavailable (private mode): the alert stays closed for this view only
        }
    }

    function hideStripWhenEmpty(strip) {
        var open = strip.querySelectorAll('.dashboard-alert-card:not([hidden])');
        if (!open.length) strip.hidden = true;
    }

    function setupAlerts() {
        var strip = document.querySelector('.dashboard-alerts-strip');
        if (!strip) return;
        var dismissed = readDismissed();
        strip.querySelectorAll('.dashboard-alert-card[data-alert-id]').forEach(function (card) {
            if (dismissed.indexOf(card.getAttribute('data-alert-id')) !== -1) card.hidden = true;
        });
        strip.addEventListener('click', function (event) {
            var button = event.target.closest('.dashboard-alert-card__close');
            if (!button) return;
            var card = button.closest('.dashboard-alert-card');
            saveDismissed(card.getAttribute('data-alert-id'));
            card.hidden = true;
            hideStripWhenEmpty(strip);
        });
        hideStripWhenEmpty(strip);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupAlerts);
    } else {
        setupAlerts();
    }

    // A finding action's result (?re=<code>) is shown once: drop it from the URL (tab and hash stay),
    // so a reload or the tab sync below does not show the status line again
    var landing = new URL(window.location.href);
    if (landing.searchParams.has('re')) {
        landing.searchParams.delete('re');
        window.history.replaceState(null, '', landing.toString());
    }

    var tabList = document.getElementById('di-tabs');
    if (!tabList) return;

    var content = document.querySelector('.di-tab-content');
    var LOADING = 'Loading\u2026';
    var FAILED = 'Could not load this tab. Reload the page.';
    var pendingHash = null;
    var pendingJump = false;

    function paneFor(button) {
        return document.querySelector(button.getAttribute('data-bs-target'));
    }

    // One in-flight fetch per pane, so rapid re-clicks share it
    var inFlight = new WeakMap();

    function showMessage(pane, text) {
        var message = document.createElement('p');
        message.setAttribute('role', 'status');
        message.className = 'di-rq-empty';
        message.textContent = text;
        pane.replaceChildren(message);
    }

    // Fetch a pane's HTML once; resolves when the pane is filled
    function load(pane) {
        if (pane.dataset.loaded === 'true') return Promise.resolve();
        if (inFlight.has(pane)) return inFlight.get(pane);
        showMessage(pane, LOADING);
        var promise = fetch(pane.dataset.panelUrl, { credentials: 'same-origin' }).then(function (response) {
            if (!response.ok || response.redirected) throw new Error('status ' + response.status);
            return response.text();
        }).then(function (html) {
            pane.innerHTML = html;
            pane.dataset.loaded = 'true';
        }).catch(function () {
            showMessage(pane, FAILED);
        }).then(function () {
            inFlight.delete(pane);
        });
        inFlight.set(pane, promise);
        return promise;
    }

    // Scroll to the anchor and move focus there; with no anchor, focus the tab button
    function jumpTo(hash, button) {
        var target = hash ? document.getElementById(hash.replace(/^#/, '')) : null;
        if (!target) {
            button.focus();
            return;
        }
        if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        target.focus({ preventScroll: true });
    }

    tabList.addEventListener('shown.bs.tab', function (event) {
        var button = event.target;
        var url = new URL(window.location.href);
        url.searchParams.set('tab', button.dataset.tab);
        url.hash = '';
        window.history.replaceState(null, '', url.toString());

        var hash = pendingHash;
        var jump = pendingJump;
        pendingHash = null;
        pendingJump = false;
        load(paneFor(button)).then(function () { if (jump) jumpTo(hash, button); });
    });

    document.addEventListener('click', function (event) {
        var link = event.target.closest('[data-tab-link]');
        if (!link) return;
        var button = document.getElementById('di-tab-' + link.dataset.tabLink);
        if (!button) return;
        event.preventDefault();
        if (button.classList.contains('active')) {
            jumpTo(link.hash, button);
            return;
        }
        pendingHash = link.hash;
        pendingJump = true;
        bootstrap.Tab.getOrCreateInstance(button).show();
    });

    // Research scope switch (Closed trades / Closed + open), by delegation: the pane may load later.
    // It drives every scoped panel in its tab (Research quality and Research effectiveness).
    content.addEventListener('click', function (event) {
        var button = event.target.closest('[data-scope-btn]');
        if (!button) return;
        var section = button.closest('.tab-pane');
        if (!section) return;
        section.querySelectorAll('[data-scope-btn]').forEach(function (other) {
            other.setAttribute('aria-pressed', other === button ? 'true' : 'false');
        });
        section.querySelectorAll('[data-scope]').forEach(function (panel) {
            panel.hidden = panel.dataset.scope !== button.dataset.scopeBtn;
        });
    });
}());
