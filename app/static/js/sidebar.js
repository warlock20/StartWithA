/**
 * Sidebar Navigation — toggle, collapse, mobile, active state
 */
document.addEventListener('DOMContentLoaded', function () {

    // ── Restore sidebar collapsed state from localStorage ──
    if (localStorage.getItem('sidebar-collapsed') === 'true') {
        document.body.classList.add('sidebar-collapsed');
    }

    // ── Restore section collapsed/expanded states ──
    var saved = JSON.parse(localStorage.getItem('sidebar-sections') || '{}');
    document.querySelectorAll('.sidebar-section-toggle').forEach(function (toggle) {
        var key = (toggle.querySelector('.sidebar-item-text') || {}).textContent;
        if (key) key = key.trim();
        if (!key) return;

        var subitems = toggle.nextElementSibling;
        if (saved[key] === false) {
            toggle.classList.remove('expanded');
            if (subitems) subitems.classList.remove('open');
        } else if (saved[key] === true || toggle.classList.contains('expanded')) {
            toggle.classList.add('expanded');
            if (subitems) subitems.classList.add('open');
        }
    });

    // ── Highlight active sidebar item based on current URL path ──
    var currentPath = window.location.pathname;
    var bestMatch = null;
    var bestLen = 0;

    document.querySelectorAll('.sidebar-item[href]').forEach(function (item) {
        var href = item.getAttribute('href');
        if (!href || href === '#') return;
        try {
            var itemPath = new URL(href, window.location.origin).pathname;
            // Exact match or prefix match (but not just "/")
            if (currentPath === itemPath || (itemPath.length > 1 && currentPath.startsWith(itemPath))) {
                if (itemPath.length > bestLen) {
                    bestMatch = item;
                    bestLen = itemPath.length;
                }
            }
        } catch (e) { /* ignore bad URLs */ }
    });

    if (bestMatch) {
        bestMatch.classList.add('active');
        // Make sure parent sections are expanded so the active item is visible
        var parent = bestMatch.closest('.sidebar-subitems');
        while (parent) {
            parent.classList.add('open');
            var prevToggle = parent.previousElementSibling;
            if (prevToggle && prevToggle.classList.contains('sidebar-section-toggle')) {
                prevToggle.classList.add('expanded');
            }
            parent = parent.parentElement ? parent.parentElement.closest('.sidebar-subitems') : null;
        }
    }

    // ── Auto-close mobile sidebar when a link is clicked ──
    document.querySelectorAll('.sidebar-item[href]').forEach(function (item) {
        item.addEventListener('click', function () {
            if (window.innerWidth <= 768) {
                closeMobileSidebar();
            }
        });
    });

    // ── Dismiss NEW badges on click ──
    // Uses sendBeacon so the request survives page navigation
    // (fetch gets cancelled when the browser navigates to the link's href)
    document.querySelectorAll('.sidebar-item[data-feature-group]').forEach(function (item) {
        item.addEventListener('click', function () {
            var badge = item.querySelector('.sidebar-badge--new');
            if (!badge) return;
            var group = item.getAttribute('data-feature-group');
            badge.remove();
            navigator.sendBeacon('/auth/dismiss-new-feature/' + group);
        });
    });
});

/* ── Global functions (called from onclick attributes) ── */

function toggleSidebar() {
    document.body.classList.toggle('sidebar-collapsed');
    localStorage.setItem('sidebar-collapsed', document.body.classList.contains('sidebar-collapsed'));
}

function toggleMobileSidebar() {
    var sidebar = document.getElementById('appSidebar');
    var overlay = document.getElementById('mobileOverlay');
    if (sidebar) sidebar.classList.toggle('mobile-open');
    if (overlay) overlay.classList.toggle('active');
}

function closeMobileSidebar() {
    var sidebar = document.getElementById('appSidebar');
    var overlay = document.getElementById('mobileOverlay');
    if (sidebar) sidebar.classList.remove('mobile-open');
    if (overlay) overlay.classList.remove('active');
}

function toggleSidebarSection(btn) {
    btn.classList.toggle('expanded');
    var subitems = btn.nextElementSibling;
    if (subitems) subitems.classList.toggle('open');

    // Persist section states
    var states = {};
    document.querySelectorAll('.sidebar-section-toggle').forEach(function (toggle) {
        var key = (toggle.querySelector('.sidebar-item-text') || {}).textContent;
        if (key) states[key.trim()] = toggle.classList.contains('expanded');
    });
    localStorage.setItem('sidebar-sections', JSON.stringify(states));
}
