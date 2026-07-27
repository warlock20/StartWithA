import { mountIsland } from './lib/mountIsland';
import { SectorCanvas } from './components/sector-canvas/SectorCanvas';
import { CompanySidebar } from './components/sector-canvas/CompanySidebar';

/**
 * Sector Canvas — React island entry point.
 *
 * Exposes:
 *   window.initSectorCanvas(elementId, config)
 *   window.initCompanySidebar(elementId, config)
 *   window.initScrollFadeEffects()
 */

window.initSectorCanvas = function (elementId, config) {
  return mountIsland(elementId, SectorCanvas, config);
};

window.initCompanySidebar = function (elementId, config) {
  return mountIsland(elementId, CompanySidebar, config);
};

/**
 * Scroll fade effects — lightweight scroll listeners for
 * research tab content, sticky sidebar, and notes canvas.
 * Not React, just plain DOM listeners.
 */
window.initScrollFadeEffects = function () {
  var selectors = ['.research-tab-content', '.sticky-sidebar', '.notes-canvas'];
  selectors.forEach(function (sel) {
    var el = document.querySelector(sel);
    if (!el) return;
    el.addEventListener('scroll', function () {
      if (this.scrollTop > 20) {
        this.classList.add('scrolled');
      } else {
        this.classList.remove('scrolled');
      }
      // Also track near-bottom for research tab content
      if (sel === '.research-tab-content') {
        var isNearBottom = this.scrollHeight - this.scrollTop - this.clientHeight < 20;
        if (isNearBottom) {
          this.classList.add('scrolled-bottom');
        } else {
          this.classList.remove('scrolled-bottom');
        }
      }
    });
  });
};
