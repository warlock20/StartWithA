// Decision Intelligence (portfolio/decisions_intelligence.html): tabs that load on first
// open, the URL sync, links between tabs, and the research scope switch.
(function () {
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

    // Research scope switch (Closed + open / Closed only), by delegation: the pane may load later
    content.addEventListener('click', function (event) {
        var button = event.target.closest('[data-scope-btn]');
        if (!button) return;
        var section = button.closest('#research-quality');
        section.querySelectorAll('[data-scope-btn]').forEach(function (other) {
            other.setAttribute('aria-pressed', other === button ? 'true' : 'false');
        });
        section.querySelectorAll('[data-scope]').forEach(function (panel) {
            panel.hidden = panel.dataset.scope !== button.dataset.scopeBtn;
        });
    });
}());
