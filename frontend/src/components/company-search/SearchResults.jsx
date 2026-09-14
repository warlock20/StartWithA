/**
 * Search results list for the Company Search Modal.
 *
 * Three sources, ranked by how much they know about the company:
 *   1. the user's own companies  — already theirs
 *   2. market-sweep rows         — carry a human-entered ISIN
 *   3. the finance provider      — a name and a ticker, nothing more
 *
 * The sweep sits above the provider deliberately. A provider listing of a
 * company the sweep already covers is the same company minus its identifier,
 * and creating from it is what leaves a portfolio holding two of everything.
 */
export function SearchResults({
  yahooSuggestions,
  userCompanies,
  sweepCompanies = [],
  onSelectYahoo,
  onSelectUser,
  onSelectSweep,
}) {
  if (yahooSuggestions.length === 0
      && userCompanies.length === 0
      && sweepCompanies.length === 0) return null;

  return (
    <div className="mb-3">
      <h6>Search Results:</h6>
      <div className="list-group" id="resultsList">
        {userCompanies.map((c) => (
          <a
            key={`user-${c.id}`}
            href="#"
            data-testid="user-result"
            className="list-group-item list-group-item-action"
            onClick={(e) => { e.preventDefault(); onSelectUser(c); }}
          >
            <div className="d-flex justify-content-between align-items-start">
              <div>
                <h6 className="mb-1">{c.name}</h6>
                <p className="mb-1">{c.ticker_symbol || 'No ticker'}</p>
                <small className="text-muted">{c.industry || 'Industry not specified'}</small>
              </div>
              <div className="text-end">
                <small className="text-primary">Your Portfolio</small>
              </div>
            </div>
          </a>
        ))}
        {sweepCompanies.map((s) => (
          <a
            key={`sweep-${s.sweep_company_id}`}
            href="#"
            data-testid="sweep-result"
            className="list-group-item list-group-item-action"
            onClick={(e) => { e.preventDefault(); onSelectSweep(s); }}
          >
            <div className="d-flex justify-content-between align-items-start">
              <div>
                <h6 className="mb-1">{s.company_name}</h6>
                <p className="mb-1">
                  {s.ticker || 'No ticker'}
                  {s.isin && (
                    <>
                      {' '}
                      <span className="badge bg-success-subtle text-success-emphasis">
                        ISIN {s.isin}
                      </span>
                    </>
                  )}
                </p>
                <small className="text-muted">
                  {s.sector_label || 'Sector not specified'}
                </small>
              </div>
              <div className="text-end">
                <small className="text-success d-block">Add to Portfolio</small>
                <small className="text-muted">
                  {s.sweep_country || s.sweep_name} sweep
                </small>
              </div>
            </div>
          </a>
        ))}
        {yahooSuggestions.map((s, i) => (
          <a
            key={`yahoo-${s.ticker_symbol}-${i}`}
            href="#"
            data-testid="yahoo-result"
            className="list-group-item list-group-item-action"
            onClick={(e) => { e.preventDefault(); onSelectYahoo(s); }}
          >
            <div className="d-flex justify-content-between align-items-start">
              <div>
                <h6 className="mb-1">{s.name}</h6>
                <p className="mb-1">{s.ticker_symbol}</p>
                <small className="text-muted">{s.industry || 'Industry not specified'}</small>
              </div>
              <div className="text-end">
                <small className="text-success">Add to Portfolio</small>
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
