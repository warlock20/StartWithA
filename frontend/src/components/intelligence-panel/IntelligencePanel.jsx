import { useState, useEffect, useRef } from 'react';
import { apiGet } from '../../lib/api';
import { PaybackTab } from './PaybackTab';
import { MarginTab } from './MarginTab';
import { WarningStrip } from './WarningStrip';

const CURRENCY_SYMBOLS = {
  USD: '$', EUR: '\u20ac', GBP: '\u00a3', JPY: '\u00a5',
  CAD: 'C$', AUD: 'A$', CHF: 'CHF', CNY: '\u00a5',
  HKD: 'HK$', INR: '\u20b9', KRW: '\u20a9', SEK: 'kr',
  NOK: 'kr', DKK: 'kr',
};

/**
 * Investment Intelligence Panel — React island for the Add Transaction page.
 *
 * Bridge pattern: observes external form elements (#company_id, input[name="type"],
 * #price_per_share) and shows/hides based on transaction type + company selection.
 *
 * Exposes `window.IntelligencePanel.syncWarnings(warnings)` so the existing
 * transaction-warnings system can feed warnings into the panel.
 */
export function IntelligencePanel() {
  const [activeTab, setActiveTab] = useState('payback');
  const [growthRate, setGrowthRate] = useState(15);
  const [companyData, setCompanyData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [dataError, setDataError] = useState(false);
  const [formPrice, setFormPrice] = useState(0);
  const [txType, setTxType] = useState('BUY');
  const [hasCompany, setHasCompany] = useState(false);
  const [warnings, setWarnings] = useState([]);

  const fetchCounterRef = useRef(0);

  // ------------------------------------------------------------------
  // Expose global API for backward compat (syncWarnings + retry)
  // ------------------------------------------------------------------
  useEffect(() => {
    window.IntelligencePanel = {
      syncWarnings: (w) => setWarnings(w || []),
      retry: () => {
        const cs = document.getElementById('company_id');
        if (cs && cs.value) doFetch(cs.value);
      },
    };
    return () => { delete window.IntelligencePanel; };
  }, []);

  // ------------------------------------------------------------------
  // Bridge: observe external form elements
  // ------------------------------------------------------------------
  useEffect(() => {
    const companySelect = document.getElementById('company_id');
    const typeRadios = document.querySelectorAll('input[name="type"]');
    const priceInput = document.getElementById('price_per_share');

    function onCompanyChange() {
      const companyId = companySelect ? companySelect.value : null;
      setHasCompany(!!companyId);

      const type = document.querySelector('input[name="type"]:checked');
      if (!companyId || !type || type.value !== 'BUY') {
        setCompanyData(null);
        setDataError(false);
        return;
      }
      doFetch(companyId);
    }

    function onTypeChange() {
      const type = document.querySelector('input[name="type"]:checked');
      setTxType(type ? type.value : 'BUY');
    }

    function onPriceInput() {
      setFormPrice(parseFloat(priceInput?.value) || 0);
    }

    if (companySelect) companySelect.addEventListener('change', onCompanyChange);
    typeRadios.forEach((r) => r.addEventListener('change', onTypeChange));
    if (priceInput) priceInput.addEventListener('input', onPriceInput);

    // Set initial state from current form values
    const type = document.querySelector('input[name="type"]:checked');
    if (type) setTxType(type.value);
    setHasCompany(!!(companySelect && companySelect.value));
    if (priceInput) setFormPrice(parseFloat(priceInput.value) || 0);

    return () => {
      if (companySelect) companySelect.removeEventListener('change', onCompanyChange);
      typeRadios.forEach((r) => r.removeEventListener('change', onTypeChange));
      if (priceInput) priceInput.removeEventListener('input', onPriceInput);
    };
  }, []);

  // ------------------------------------------------------------------
  // Fetch company intelligence data
  // ------------------------------------------------------------------
  async function doFetch(companyId) {
    setIsLoading(true);
    setDataError(false);
    fetchCounterRef.current++;
    const myFetch = fetchCounterRef.current;

    try {
      const data = await apiGet(`/portfolio/api/company-intelligence/${companyId}`);
      if (myFetch !== fetchCounterRef.current) return;

      if (data.success && data.data) {
        setCompanyData(data.data);
        prefillPrice(data.data.current_price);
      } else {
        setCompanyData(null);
        setDataError(true);
      }
    } catch (err) {
      if (myFetch !== fetchCounterRef.current) return;
      console.error('Intelligence fetch failed:', err);
      setCompanyData(null);
      setDataError(true);
    } finally {
      if (myFetch === fetchCounterRef.current) setIsLoading(false);
    }
  }

  function prefillPrice(currentPrice) {
    if (!currentPrice) return;
    const priceInput = document.getElementById('price_per_share');
    if (!priceInput) return;
    priceInput.value = currentPrice.toFixed(2);
    priceInput.dispatchEvent(new Event('input', { bubbles: true }));
    setFormPrice(currentPrice);
  }

  function handleRetry() {
    const cs = document.getElementById('company_id');
    if (cs && cs.value) doFetch(cs.value);
  }

  // ------------------------------------------------------------------
  // Visibility logic
  // ------------------------------------------------------------------
  if (txType !== 'BUY') return null;

  const showPlaceholder = !hasCompany && !isLoading;
  const showPanel = hasCompany && (companyData || isLoading || dataError);

  const cs = CURRENCY_SYMBOLS[companyData?.currency] || '$';
  const price = formPrice || companyData?.current_price || 0;

  return (
    <>
      {showPanel && (
        <div className="intel-panel" id="intel-panel">
          {/* Header + Tabs */}
          <div className="intel-panel-header">
            <div className="intel-panel-title-row">
              <span className="intel-panel-icon">
                <i className="bi bi-lightbulb-fill" />
              </span>
              <div style={{ flex: 1 }}>
                <h3 className="intel-panel-title">Investment Intelligence</h3>
                <p className="intel-panel-subtitle">
                  Real-time analysis for{' '}
                  <strong id="intel-ticker-label">{companyData?.ticker || '---'}</strong>
                </p>
              </div>
            </div>
            <div className="intel-tabs">
              <button
                type="button"
                className={`intel-tab${activeTab === 'payback' ? ' active' : ''}`}
                onClick={() => setActiveTab('payback')}
              >
                <i className="bi bi-clock-history" />
                <span>Earnings Payback</span>
              </button>
              <button
                type="button"
                className={`intel-tab${activeTab === 'margin' ? ' active' : ''}`}
                onClick={() => setActiveTab('margin')}
              >
                <i className="bi bi-shield-check" />
                <span>Margin of Safety</span>
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="intel-panel-body">
            {isLoading && (
              <div className="intel-loading" id="intel-loading-indicator">
                <div className="spinner" />
                <span>Loading market data...</span>
              </div>
            )}

            {!isLoading && dataError && (
              <div className="calc-card">
                <div className="calc-body">
                  <div className="intel-unavailable">
                    <i className="bi bi-cloud-slash" />
                    <p>Unable to load market data.</p>
                    <button className="intel-retry-btn" type="button" onClick={handleRetry}>
                      <i className="bi bi-arrow-clockwise" /> Retry
                    </button>
                  </div>
                </div>
              </div>
            )}

            {!isLoading && !dataError && companyData && (
              <>
                {activeTab === 'payback' && (
                  <PaybackTab
                    companyData={companyData}
                    growthRate={growthRate}
                    onGrowthRateChange={setGrowthRate}
                  />
                )}
                {activeTab === 'margin' && (
                  <MarginTab
                    companyData={companyData}
                    growthRate={growthRate}
                    onGrowthRateChange={setGrowthRate}
                    price={price}
                    currencySymbol={cs}
                  />
                )}
              </>
            )}

            <WarningStrip warnings={warnings} />
          </div>
        </div>
      )}

      {showPlaceholder && (
        <div className="intel-placeholder" id="intel-placeholder">
          <i className="bi bi-lightbulb" />
          <p>
            Select a company above to see investment intelligence &mdash; earnings payback,
            margin of safety, and break-even analysis.
          </p>
        </div>
      )}
    </>
  );
}
