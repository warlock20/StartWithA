/**
 * Table cards — entry point for the plain-script table component.
 *
 * Exposes window.TableCards for app/static/js/data-table-component.js, which
 * cannot import ES modules. React islands import lib/tableCards directly.
 */
import { prepareCardsConfig, enableTableCards } from './lib/tableCards';

window.TableCards = { prepareCardsConfig, enableTableCards };
