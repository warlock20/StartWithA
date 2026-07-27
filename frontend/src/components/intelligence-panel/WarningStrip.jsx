/**
 * Warning strip for the Intelligence Panel.
 * Renders severity-coded warning items synced from the transaction warnings system.
 */
export function WarningStrip({ warnings }) {
  if (!warnings || warnings.length === 0) {
    return <div className="intel-warning-strip" />;
  }

  return (
    <div className="intel-warning-strip">
      {warnings.map((w, i) => {
        const severityClass = `intel-warn--${w.severity}`;
        const icon =
          w.severity === 'high' || w.severity === 'medium'
            ? 'bi-exclamation-triangle-fill'
            : 'bi-info-circle-fill';

        return (
          <div key={w.code || i} className={`intel-warn-item ${severityClass}`}>
            <i className={`bi ${icon}`} />
            <div>
              <strong>{w.title}</strong>
              <p>{w.message}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
