/**
 * SweepPicker — card grid for selecting a market sweep.
 */
export function SweepPicker({ sweeps, onSelect }) {
  if (sweeps.length === 0) {
    return (
      <div className="sweep-empty">
        <i className="bi bi-globe-americas" />
        <h5>No market sweeps available</h5>
        <p>Ask your admin to upload a company list via the admin panel.</p>
      </div>
    );
  }

  return (
    <div className="sweep-picker">
      <h3>Choose a Market</h3>
      <div className="sweep-picker-grid">
        {sweeps.map((s) => {
          const pct = s.total_companies
            ? Math.round((s.reviewed / s.total_companies) * 100)
            : 0;
          return (
            <div key={s.id} className="sweep-picker-card" onClick={() => onSelect(s.id)}>
              <div className="sweep-picker-card__country">{s.country}</div>
              <div className="sweep-picker-card__name">{s.name}</div>
              <div className="sweep-picker-card__stats">
                <span className="sweep-picker-card__stat">
                  <i className="bi bi-buildings" /> {s.total_companies}
                </span>
                <span className="sweep-picker-card__stat">
                  <i className="bi bi-check2" /> {s.reviewed} reviewed
                </span>
                <span className="sweep-picker-card__stat">
                  <i className="bi bi-inbox" /> {s.inbox_count} inbox
                </span>
              </div>
              <div className="sweep-picker-card__progress">
                <div className="sweep-picker-card__progress-fill" style={{ width: pct + '%' }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
