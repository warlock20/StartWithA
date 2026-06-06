import {
  ResponsiveContainer, PieChart, Pie, Cell, Legend, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  AreaChart, Area,
} from 'recharts';

var STEP_COLORS = ['#4A90E2', '#50E3C2', '#F5A623', '#D0021B', '#7B68EE', '#FF6B9D', '#10b981', '#f59e0b'];

function EmptyState({ message }) {
  return <div className="text-muted text-center py-4">{message || 'No data yet'}</div>;
}

/**
 * Time Analysis tab: 4 charts in a 2x2 grid.
 * Props:
 *   stepData: [{ step, hours }]
 *   companyData: [{ company, hours }]
 *   productivityByHour: { "0": count, "1": count, ... }
 *   productivityByDay: { 0: count, 1: count, ... }
 */
export function TimeAnalysisCharts({ stepData, companyData, productivityByHour, productivityByDay }) {
  // Prepare hour data
  var hourData = [];
  if (productivityByHour) {
    var keys = Object.keys(productivityByHour).sort(function (a, b) { return parseInt(a) - parseInt(b); });
    hourData = keys.map(function (h) {
      return { hour: h + ':00', count: productivityByHour[h] };
    });
  }

  // Prepare day data
  var dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  var dayData = dayLabels.map(function (label, idx) {
    return { day: label, count: (productivityByDay && productivityByDay[idx]) || 0 };
  });

  var hasStepData = stepData && stepData.length > 0;
  var hasCompanyData = companyData && companyData.length > 0;
  var hasHourData = hourData.length > 0;
  var hasDayData = dayData.some(function (d) { return d.count > 0; });

  if (!hasStepData && !hasCompanyData && !hasHourData && !hasDayData) {
    return <EmptyState message="No time analysis data yet. Start tracking your research time!" />;
  }

  return (
    <div className="row">
      {/* Step Doughnut */}
      <div className="col-lg-6 mb-4">
        <div className="analytics-chart-card">
          <div className="analytics-chart-body">
            <h5 className="mb-3" style={{ fontWeight: 700, color: '#111827' }}>Time by Research Step</h5>
            {hasStepData ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={stepData}
                    dataKey="hours"
                    nameKey="step"
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={90}
                  >
                    {stepData.map(function (_, i) {
                      return <Cell key={i} fill={STEP_COLORS[i % STEP_COLORS.length]} />;
                    })}
                  </Pie>
                  <Legend />
                  <Tooltip formatter={function (v) { return v.toFixed(1) + 'h'; }} />
                </PieChart>
              </ResponsiveContainer>
            ) : <EmptyState message="No step data" />}
          </div>
        </div>
      </div>

      {/* Company Bar */}
      <div className="col-lg-6 mb-4">
        <div className="analytics-chart-card">
          <div className="analytics-chart-body">
            <h5 className="mb-3" style={{ fontWeight: 700, color: '#111827' }}>Time by Company</h5>
            {hasCompanyData ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={companyData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="company" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={function (v) { return v.toFixed(1) + 'h'; }} />
                  <Bar dataKey="hours" fill="rgba(59, 130, 246, 0.7)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <EmptyState message="No company data" />}
          </div>
        </div>
      </div>

      {/* Hour Line */}
      <div className="col-lg-6 mb-4">
        <div className="analytics-chart-card">
          <div className="analytics-chart-body">
            <h5 className="mb-3" style={{ fontWeight: 700, color: '#111827' }}>Activity by Hour of Day</h5>
            {hasHourData ? (
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={hourData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="hour" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Area type="monotone" dataKey="count" stroke="#ef4444" fill="rgba(239, 68, 68, 0.1)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : <EmptyState message="No hourly data" />}
          </div>
        </div>
      </div>

      {/* Day Bar */}
      <div className="col-lg-6 mb-4">
        <div className="analytics-chart-card">
          <div className="analytics-chart-body">
            <h5 className="mb-3" style={{ fontWeight: 700, color: '#111827' }}>Activity by Day of Week</h5>
            {hasDayData ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={dayData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="rgba(245, 166, 35, 0.7)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <EmptyState message="No daily data" />}
          </div>
        </div>
      </div>
    </div>
  );
}
