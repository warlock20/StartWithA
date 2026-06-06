import { useEffect } from 'react';

/**
 * SidebarBehavior — Behavior-only bridge for the Jinja2-rendered sidebar.
 *
 * Returns null (no DOM output). On mount:
 *   - Restores collapsed/expanded state from localStorage
 *   - Highlights active sidebar item by URL match
 *   - Auto-closes mobile sidebar on link click
 *   - Dismisses NEW badges via sendBeacon
 *
 * Global functions (exposed on window for onclick handlers):
 *   toggleSidebar(), toggleMobileSidebar(), closeMobileSidebar(), toggleSidebarSection(btn)
 */
export function SidebarBehavior() {
  useEffect(function () {
    // ── Restore sidebar collapsed state from localStorage ──
    if (localStorage.getItem('sidebar-collapsed') === 'true') {
      document.body.classList.add('sidebar-collapsed');
    }

    // ── Restore section collapsed/expanded states ──
    var saved = JSON.parse(localStorage.getItem('sidebar-sections') || '{}');
    document.querySelectorAll('.sidebar-section-toggle').forEach(function (toggle) {
      var textEl = toggle.querySelector('.sidebar-item-text');
      var key = textEl ? textEl.textContent.trim() : '';
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
      // Ensure parent sections are expanded so active item is visible
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

    // ── Auto-close mobile sidebar on link click ──
    function handleLinkClick() {
      if (window.innerWidth <= 768) {
        window.closeMobileSidebar();
      }
    }
    document.querySelectorAll('.sidebar-item[href]').forEach(function (item) {
      item.addEventListener('click', handleLinkClick);
    });

    // ── Dismiss NEW badges on click ──
    function handleBadgeDismiss() {
      var badge = this.querySelector('.sidebar-badge--new');
      if (!badge) return;
      var group = this.getAttribute('data-feature-group');
      badge.remove();
      navigator.sendBeacon('/auth/dismiss-new-feature/' + group);
    }
    document.querySelectorAll('.sidebar-item[data-feature-group]').forEach(function (item) {
      item.addEventListener('click', handleBadgeDismiss);
    });

    // ── Cleanup ──
    return function () {
      document.querySelectorAll('.sidebar-item[href]').forEach(function (item) {
        item.removeEventListener('click', handleLinkClick);
      });
      document.querySelectorAll('.sidebar-item[data-feature-group]').forEach(function (item) {
        item.removeEventListener('click', handleBadgeDismiss);
      });
    };
  }, []);

  return null;
}
