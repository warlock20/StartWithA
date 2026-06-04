import {
  ResponsiveContainer,
  PieChart, Pie, Cell, Legend, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts';

var COC_COLORS = ['rgba(22, 163, 74, 0.8)', 'rgba(220, 38, 38, 0.8)', 'rgba(107, 114, 128, 0.8)'];

/**
 * Circle of Competence tab: CoC breakdown doughnut + sector performance stacked bar.
 * Props:
 *   cocBreakdown: { yes, no, unsure }
 *   cocSectorData: [{ name, invested, passed_full, mid_research_pass, killed }]
 */
export function CocCharts({ cocBreakdown, cocSectorData }) {
  // Prepare doughnut data
  var bd = cocBreakdown || { yes: 0, no: 0, unsure: 0 };
  var total = bd.yes + bd.no + bd.unsure;
  var doughnutData = [
    { name: 'Within CoC', value: bd.yes || 0 },
    { name: 'Outside CoC', value: bd.no || 0 },
    { name: 'Unsure', value: bd.unsure || 0 },
  ];

  // Prepare sector performance data
  var sectorData = (cocSectorData || []).map(function (s) {
    return {
      name: s.name,
      invested: s.invested,
      passed: (s.passed_full || 0) + (s.mid_research_pass || 0),
      killed: s.killed,
    };
  });

  var hasDoughnut = total > 0;
  var hasSector = sectorData.length > 0;

  return (
    <div className="row">
      {/* CoC Breakdown Doughnut */}
      <div className="col-lg-6 mb-4">
        <div className="analytics-chart-card">
          <div className="analytics-chart-body">
            <h5 className="mb-3" style={{ fontWeight: 700, color: '#111827' }}>CoC Breakdown</h5>
            {hasDoughnut ? (
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
            ) : (
              <div className="text-muted text-center py-4">No CoC assessments yet</div>
            )}
          </div>
        </div>
      </div>

      {/* Sector Performance Stacked Bar */}
      <div className="col-lg-6 mb-4">
        <div className="analytics-chart-card">
          <div className="analytics-chart-body">
            <h5 className="mb-3" style={{ fontWeight: 700, color: '#111827' }}>Sector Performance</h5>
            {hasSector ? (
              <ResponsiveContainer width="100%" height={280}>
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
            ) : (
              <div className="text-muted text-center py-4">No sector performance data yet</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
