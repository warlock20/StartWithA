import { mountIsland } from './lib/mountIsland';
import { RevenueChart, NetIncomeChart } from './components/financials/FinancialsCharts';

window.initRevenueChart = function (elementId, config) {
  return mountIsland(elementId, RevenueChart, config);
};

window.initNetIncomeChart = function (elementId, config) {
  return mountIsland(elementId, NetIncomeChart, config);
};
