import { mountIsland } from './lib/mountIsland';
import { CompanyResourcesManager } from "./components/CompanyResourcesManager";

/**
 * Initialize Company Resources Manager
 * Called from Flask template to mount the React island.
 *
 * @param {string} elementId - DOM element ID to mount to
 * @param {object} config - Component configuration
 * @param {number} config.companyId
 * @param {string} config.companyName
 * @param {Function} config.openUploadModal
 * @param {Function} config.openLinkModal
 */
window.initCompanyResourcesManager = function (elementId, config = {}) {
  return mountIsland(elementId, CompanyResourcesManager, {
    companyId: config.companyId,
    companyName: config.companyName,
    openUploadModal: config.openUploadModal,
    openLinkModal: config.openLinkModal,
  });
};
