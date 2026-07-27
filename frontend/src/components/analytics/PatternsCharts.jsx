import {
  ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  LineChart, Line,
  ScatterChart, Scatter, ZAxis,
} from 'recharts';

function EmptyState({ message }) {
  return <div className="text-muted text-center py-4">{message || 'No data yet'}</div>;
}

/**
 * Research Patterns tab: Kill reasons (horizontal bar), Velocity (dual line), Confidence (scatter).
 * Props:
 *   killReasons: [[reason, count], ...]
 *   velocityData: [{ month, projects, ideas }]
 *   confidenceTrend: [{ date, confidence, type, company }]
 */
export function PatternsCharts({ killReasons, velocityData, confidenceTrend }) {
  // Prepare kill reasons data
  var killData = (killReasons || []).map(function (r) {
    return { reason: r[0].length > 30 ? r[0].substring(0, 30) + '\u2026' : r[0], count: r[1] };
  });

  // Separate confidence data by type
  var investPoints = [];
  var passPoints = [];
  if (confidenceTrend && confidenceTrend.length > 0) {
    confidenceTrend.forEach(function (d) {
      var point = { date: d.date, confidence: d.confidence, company: d.company };
      if (d.type === 'invest') {
        investPoints.push(point);
      } else {
        passPoints.push(point);
      }
    });
  }

  var hasKill = killData.length > 0;
  var hasVelocity = velocityData && velocityData.length > 0;
  var hasConfidence = (investPoints.length + passPoints.length) > 0;

  if (!hasKill && !hasVelocity && !hasConfidence) {
    return <EmptyState message="No research pattern data yet. Complete some research projects to see insights!" />;
  }

  return (
    <div className="row">
      {/* Kill Reasons (horizontal bar) */}
      <div className="col-lg-6 mb-4">
        <div className="analytics-chart-card">
          <div className="analytics-chart-body">
            <h5 className="mb-3" style={{ fontWeight: 700, color: '#111827' }}>Top Kill Reasons</h5>
            {hasKill ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={killData} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 120 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis dataKey="reason" type="category" tick={{ fontSize: 10 }} width={110} />
                  <Tooltip />
                  <Bar dataKey="count" fill="rgba(239, 68, 68, 0.7)" name="Times Used" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <EmptyState message="No kill reasons recorded" />}
          </div>
        </div>
      </div>

      {/* Velocity (dual line) */}
      <div className="col-lg-6 mb-4">
        <div className="analytics-chart-card">
          <div className="analytics-chart-body">
            <h5 className="mb-3" style={{ fontWeight: 700, color: '#111827' }}>Research Velocity</h5>
            {hasVelocity ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={velocityData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="projects" stroke="#10b981" strokeWidth={2} name="Projects" dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="ideas" stroke="#3b82f6" strokeWidth={2} name="Ideas" dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : <EmptyState message="No velocity data" />}
          </div>
        </div>
      </div>

      {/* Confidence Scatter */}
      <div className="col-12 mb-4">
        <div className="analytics-chart-card">
          <div className="analytics-chart-body">
            <h5 className="mb-3" style={{ fontWeight: 700, color: '#111827' }}>Decision Confidence Trends</h5>
            {hasConfidence ? (
              <ResponsiveContainer width="100%" height={300}>
                <ScatterChart margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" name="Date" tick={{ fontSize: 10 }} />
                  <YAxis dataKey="confidence" name="Confidence" domain={[0, 10]} tick={{ fontSize: 11 }} />
                  <ZAxis range={[40, 40]} />
                  <Tooltip
                    content={function ({ active, payload }) {
                      if (!active || !payload || !payload[0]) return null;
                      var d = payload[0].payload;
                      return (
                        <div style={{ background: '#fff', border: '1px solid #e5e7eb', padding: '8px 12px', borderRadius: 6, fontSize: 12 }}>
                          <div><strong>{d.company || 'Unknown'}</strong></div>
                          <div>Date: {d.date}</div>
                          <div>Confidence: {d.confidence}/10</div>
                        </div>
                      );
                    }}
                  />
                  <Legend />
                  {investPoints.length > 0 && (
                    <Scatter name="Invest" data={investPoints} fill="rgba(16, 185, 129, 0.7)" />
                  )}
                  {passPoints.length > 0 && (
                    <Scatter name="Pass" data={passPoints} fill="rgba(239, 68, 68, 0.7)" />
                  )}
                </ScatterChart>
              </ResponsiveContainer>
            ) : <EmptyState message="No confidence data" />}
          </div>
        </div>
      </div>
    </div>
  );
}
