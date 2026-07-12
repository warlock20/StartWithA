import {
  ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';

var SOURCE_COLORS = [
  '#2d6a4f', '#3b82f6', '#0891b2', '#8b5cf6',
  '#f59e0b', '#10b981', '#6366f1', '#dc2626',
  '#d97706', '#ec4899',
];

function EmptyState({ message }) {
  return <div className="text-muted text-center py-4">{message || 'No data yet'}</div>;
}

/**
 * Research Velocity — grouped bar chart (started vs completed per month).
 * Props: { data: [{ month, started, completed }] }
 */
export function InsightsVelocityChart({ data }) {
  if (!data || data.length === 0) {
    return <EmptyState message="No velocity data yet. Complete some research projects to see trends!" />;
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" />
        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
        <Tooltip
          contentStyle={{
            background: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: 6,
            fontSize: 12,
          }}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
          iconSize={8}
        />
        <Bar
          dataKey="started"
          name="Started"
          fill="#3b82f6"
          radius={[3, 3, 0, 0]}
          maxBarSize={40}
        />
        <Bar
          dataKey="completed"
          name="Completed"
          fill="#10b981"
          radius={[3, 3, 0, 0]}
          maxBarSize={40}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

/**
 * Idea Sources — stacked proportional bar with color-coded legend grid.
 * Props: { data: [{ source, count }] }
 */
export function InsightsSourcesChart({ data }) {
  if (!data || data.length === 0) {
    return <EmptyState message="No idea source data yet" />;
  }

  var total = data.reduce(function (sum, d) { return sum + (d.count || 0); }, 0);
  if (total === 0) {
    return <EmptyState message="No idea source data yet" />;
  }

  var MAX_SHOWN = 7;
  var shown = data.slice(0, MAX_SHOWN);
  var rest = data.slice(MAX_SHOWN);
  var othersCount = rest.reduce(function (sum, d) { return sum + (d.count || 0); }, 0);

  var items = shown.map(function (d, i) {
    return {
      name: d.source,
      count: d.count,
      color: SOURCE_COLORS[i % SOURCE_COLORS.length],
      pct: Math.round((d.count / total) * 100),
    };
  });

  if (othersCount > 0) {
    items.push({
      name: rest.length + ' others',
      count: othersCount,
      color: SOURCE_COLORS[MAX_SHOWN % SOURCE_COLORS.length],
      pct: Math.round((othersCount / total) * 100),
    });
  }

  return (
    <div>
      <div style={{
        display: 'flex',
        height: 28,
        borderRadius: 6,
        overflow: 'hidden',
        marginBottom: 16,
      }}>
        {items.map(function (item, i) {
          return (
            <div
              key={i}
              style={{
                width: (item.count / total * 100) + '%',
                backgroundColor: item.color,
                minWidth: 3,
              }}
              title={item.name + ': ' + item.count + ' (' + item.pct + '%)'}
            />
          );
        })}
      </div>
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '10px 28px',
      }}>
        {items.map(function (item, i) {
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{
                width: 10,
                height: 10,
                borderRadius: 2,
                backgroundColor: item.color,
                flexShrink: 0,
              }} />
              <span style={{ color: '#6b7280', fontSize: 13 }}>{item.name}</span>
              <span style={{ fontWeight: 700, color: '#1f2937', fontSize: 13 }}>{item.count}</span>
              <span style={{ color: '#9ca3af', fontSize: 13 }}>{item.pct}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
