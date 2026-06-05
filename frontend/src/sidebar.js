import { mountIsland } from './lib/mountIsland';
import { SidebarBehavior } from './components/layout/SidebarBehavior';

/**
 * Sidebar — React island entry point.
 *
 * Global functions are defined at module scope so they're available
 * immediately for onclick handlers in the Jinja2 sidebar template.
 * The SidebarBehavior component handles init-time DOM setup (localStorage
 * restore, active state, event listeners) via useEffect.
 */

// ── Global functions called from onclick attributes ──

window.toggleSidebar = function () {
  document.body.classList.toggle('sidebar-collapsed');
  localStorage.setItem('sidebar-collapsed', document.body.classList.contains('sidebar-collapsed'));
};

window.toggleMobileSidebar = function () {
  var sidebar = document.getElementById('appSidebar');
  var overlay = document.getElementById('mobileOverlay');
  if (sidebar) sidebar.classList.toggle('mobile-open');
  if (overlay) overlay.classList.toggle('active');
};

window.closeMobileSidebar = function () {
  var sidebar = document.getElementById('appSidebar');
  var overlay = document.getElementById('mobileOverlay');
  if (sidebar) sidebar.classList.remove('mobile-open');
  if (overlay) overlay.classList.remove('active');
};

window.toggleSidebarSection = function (btn) {
  btn.classList.toggle('expanded');
  var subitems = btn.nextElementSibling;
  if (subitems) subitems.classList.toggle('open');

  // Persist section states
  var states = {};
  document.querySelectorAll('.sidebar-section-toggle').forEach(function (toggle) {
    var textEl = toggle.querySelector('.sidebar-item-text');
    var key = textEl ? textEl.textContent.trim() : '';
    if (key) states[key] = toggle.classList.contains('expanded');
  });
  localStorage.setItem('sidebar-sections', JSON.stringify(states));
};

// ── Mount behavior island on DOMContentLoaded ──

window.initSidebar = function (elementId) {
  return mountIsland(elementId, SidebarBehavior, {});
};

document.addEventListener('DOMContentLoaded', function () {
  var mount = document.getElementById('sidebar-behavior-mount');
  if (mount && window.initSidebar) {
    window.initSidebar('sidebar-behavior-mount');
  }
});
