import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';

/**
 * Research Activity line chart (last 30 days).
 * Props: { data: [{ date, hours }] }
 */
export function OverviewActivityChart({ data }) {
  if (!data || data.length === 0) {
    return <div className="text-muted text-center py-4">No research activity data yet</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={function (v) { return v + 'h'; }} tick={{ fontSize: 11 }} />
        <Tooltip formatter={function (v) { return [v.toFixed(1) + 'h', 'Research']; }} />
        <Area
          type="monotone"
          dataKey="hours"
          stroke="#3b82f6"
          fill="rgba(59, 130, 246, 0.1)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
