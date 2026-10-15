import {
  ResponsiveContainer,
  PieChart, Pie, Cell, Legend, Tooltip,
} from 'recharts';

var SECTOR_PALETTE = [
  '#2d6a4f', '#3b82f6', '#f59e0b', '#ef4444',
  '#8b5cf6', '#0891b2', '#d97706', '#6366f1',
  '#10b981', '#ec4899',
];

/**
 * Sector Distribution doughnut chart.
 * Props: { data: [{ name, count }] }
 */
export function SectorDonutChart({ data }) {
  if (!data || data.length === 0) {
    return <div className="text-muted text-center py-4">No sector data yet</div>;
  }

  var total = data.reduce(function (sum, d) { return sum + (d.count || 0); }, 0);
  if (total === 0) {
    return <div className="text-muted text-center py-4">No sector data yet</div>;
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          dataKey="count"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius="42%"
          outerRadius="70%"
          strokeWidth={2}
          stroke="#fff"
        >
          {data.map(function (_, i) {
            return <Cell key={i} fill={SECTOR_PALETTE[i % SECTOR_PALETTE.length]} />;
          })}
        </Pie>
        <Legend
          wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
          iconSize={10}
        />
        <Tooltip
          formatter={function (value) {
            var pct = total > 0 ? ((value / total) * 100).toFixed(1) : '0';
            return value + ' (' + pct + '%)';
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
