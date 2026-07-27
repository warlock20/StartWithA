import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';

/**
 * Idea Source funnel stacked bar chart.
 * Props: { data: [{ source, killed, promoted, invested }] }
 */
export function SourceFunnelChart({ data }) {
  if (!data || data.length === 0) {
    return <div className="text-muted text-center py-4">No source data yet</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="source" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend />
        <Bar dataKey="killed" stackId="a" fill="rgba(239, 68, 68, 0.7)" name="Killed" />
        <Bar dataKey="promoted" stackId="a" fill="rgba(59, 130, 246, 0.7)" name="Promoted" />
        <Bar dataKey="invested" stackId="a" fill="rgba(16, 185, 129, 0.7)" name="Invested" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
