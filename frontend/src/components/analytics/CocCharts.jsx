import {
  ResponsiveContainer,
  PieChart, Pie, Cell, Legend, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts';

var COC_COLORS = ['rgba(22, 163, 74, 0.8)', 'rgba(220, 38, 38, 0.8)', 'rgba(107, 114, 128, 0.8)'];

/**
 * CoC Breakdown doughnut chart.
 * Props: { cocBreakdown: { yes, no, unsure } }
 */
export function CocBreakdownChart({ cocBreakdown }) {
  var bd = cocBreakdown || { yes: 0, no: 0, unsure: 0 };
  var total = bd.yes + bd.no + bd.unsure;
  var doughnutData = [
    { name: 'Within CoC', value: bd.yes || 0 },
    { name: 'Outside CoC', value: bd.no || 0 },
    { name: 'Unsure', value: bd.unsure || 0 },
  ];

  if (total === 0) {
    return <div className="text-muted text-center py-4">No CoC assessments yet</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={doughnutData}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={55}
          outerRadius={95}
          strokeWidth={2}
        >
          {doughnutData.map(function (_, i) {
            return <Cell key={i} fill={COC_COLORS[i]} />;
          })}
        </Pie>
        <Legend />
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

/**
 * Sector performance stacked bar chart.
 * Props: { data: [{ name, invested, passed_full, mid_research_pass, killed }] }
 */
export function CocSectorChart({ data }) {
  var sectorData = (data || []).map(function (s) {
    return {
      name: s.name,
      invested: s.invested,
      passed: (s.passed_full || 0) + (s.mid_research_pass || 0),
      killed: s.killed,
    };
  });

  if (sectorData.length === 0) {
    return <div className="text-muted text-center py-4">No sector performance data yet</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={sectorData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend />
        <Bar dataKey="invested" stackId="a" fill="rgba(22, 163, 74, 0.8)" name="Invested" />
        <Bar dataKey="passed" stackId="a" fill="rgba(220, 38, 38, 0.8)" name="Passed" />
        <Bar dataKey="killed" stackId="a" fill="rgba(107, 114, 128, 0.8)" name="Early Kills" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

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
