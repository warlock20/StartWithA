import { mountIsland } from './lib/mountIsland';
import { TransactionsTable } from './components/company-dashboard/TransactionsTable';

window.initTransactionsTable = function (elementId, config) {
  return mountIsland(elementId, TransactionsTable, config);
};
