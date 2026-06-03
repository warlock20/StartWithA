import { mountIsland } from './lib/mountIsland';
import { CompanySearchModal } from './components/company-search/CompanySearchModal';

/**
 * Company Search Modal — React island entry point.
 *
 * Auto-mounts into #company-search-mount on DOMContentLoaded.
 * The component registers window.openCompanyModal(callback) on mount.
 *
 * Usage in Jinja2 templates:
 *   <div id="company-search-mount"></div>
 *   <script defer src="{{ url_for('static', filename='js/dist/company-search.bundle.js') }}"></script>
 *   <!-- Then call: openCompanyModal(function(company) { ... }) -->
 */
document.addEventListener('DOMContentLoaded', function () {
  mountIsland('company-search-mount', CompanySearchModal);
});
