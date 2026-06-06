import {
  ResponsiveContainer, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts';

function formatNumber(value) {
  if (Math.abs(value) >= 1e12) return (value / 1e12).toFixed(2) + ' T';
  if (Math.abs(value) >= 1e9) return (value / 1e9).toFixed(2) + ' B';
  if (Math.abs(value) >= 1e6) return (value / 1e6).toFixed(2) + ' M';
  return value.toLocaleString();
}

/**
 * Revenue bar chart.
 * Props: { labels: string[], values: number[] }
 */
export function RevenueChart({ labels, values }) {
  if (!labels || !values || values.length === 0) return null;
  var data = labels.map(function (label, i) {
    return { label: label, value: values[i] };
  });

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={formatNumber} tick={{ fontSize: 11 }} />
        <Tooltip formatter={function (v) { return formatNumber(v); }} />
        <Bar dataKey="value" fill="rgba(54, 162, 235, 0.8)" name="Total Revenue" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/**
 * Net Income area chart.
 * Props: { labels: string[], values: number[] }
 */
export function NetIncomeChart({ labels, values }) {
  if (!labels || !values || values.length === 0) return null;
  var data = labels.map(function (label, i) {
    return { label: label, value: values[i] };
  });

  return (
    <ResponsiveContainer width="100%" height={250}>
      <AreaChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={formatNumber} tick={{ fontSize: 11 }} />
        <Tooltip formatter={function (v) { return formatNumber(v); }} />
        <Area type="monotone" dataKey="value" stroke="rgba(75, 192, 192, 1)" fill="rgba(75, 192, 192, 0.5)" name="Net Income" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
