/**
 * Search results list for the Company Search Modal.
 * Displays Yahoo Finance suggestions and user's existing companies.
 */
export function SearchResults({ yahooSuggestions, userCompanies, onSelectYahoo, onSelectUser }) {
  if (yahooSuggestions.length === 0 && userCompanies.length === 0) return null;

  return (
    <div className="mb-3">
      <h6>Search Results:</h6>
      <div className="list-group" id="resultsList">
        {yahooSuggestions.map((s, i) => (
          <a
            key={`yahoo-${s.ticker_symbol}-${i}`}
            href="#"
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
        {userCompanies.map((c) => (
          <a
            key={`user-${c.id}`}
            href="#"
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
      </div>
    </div>
  );
}
