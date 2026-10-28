/**
 * Table cards and folded columns — entry point for the plain-script table
 * component.
 *
 * Exposes window.TableCards and window.TableFold for
 * app/static/js/data-table-component.js, which cannot import ES modules.
 * React islands import lib/tableCards and lib/tableFold directly.
 */
import { prepareCardsConfig, enableTableCards } from './lib/tableCards';
import { prepareFoldConfig, enableTableFold } from './lib/tableFold';

window.TableCards = { prepareCardsConfig, enableTableCards };
window.TableFold = { prepareFoldConfig, enableTableFold };
