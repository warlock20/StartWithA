import { mountIsland } from './lib/mountIsland';
import { DocumentAnnotations } from './components/annotations/DocumentAnnotations';

/**
 * Document Annotations — React island entry.
 *
 * Called after PDF pages are fully rendered. Mounts into a hidden div and
 * renders the sidebar list + popover via portals into the existing template DOM.
 *
 * Also exposes window.DocumentAnnotations.toggleSidebar / enterAddMode
 * for backward compat with the inline onclick in the sidebar close button.
 */
window.initDocumentAnnotations = function (elementId, config) {
  return mountIsland(elementId, DocumentAnnotations, config);
};
