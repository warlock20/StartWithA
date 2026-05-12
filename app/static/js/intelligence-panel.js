/**
 * Intelligence Panel - DOM Controller
 * Manages the Investment Intelligence Panel on Add Transaction page.
 * Depends on: intelligence-engine.js, Chart.js (loaded via _chart_js.html)
 */
'use strict';

var IntelligencePanel = (function() {
    // State
    var state = {
        activeTab: 'payback',
        growthRate: 15,
        companyData: null,    // { ticker, pe_ratio, eps_ttm, current_price, sector, currency }
        loading: false,
        chartInstance: null,
        fetchCounter: 0       // Prevents stale responses
    };

    // DOM references (cached on init)
    var els = {};

    // Currency symbols lookup
    var CURRENCY_SYMBOLS = {
        'USD': '$', 'EUR': '\u20ac', 'GBP': '\u00a3', 'JPY': '\u00a5',
        'CAD': 'C$', 'AUD': 'A$', 'CHF': 'CHF', 'CNY': '\u00a5',
        'HKD': 'HK$', 'INR': '\u20b9', 'KRW': '\u20a9', 'SEK': 'kr',
        'NOK': 'kr', 'DKK': 'kr'
    };

    function init() {
        // Cache DOM elements
        els.panel = document.getElementById('intel-panel');
        els.placeholder = document.getElementById('intel-placeholder');
        els.column = document.getElementById('intel-column');
        els.tickerLabel = document.getElementById('intel-ticker-label');
        els.growthSlider = document.getElementById('growth-rate-slider');
        els.growthDisplay = document.getElementById('growth-rate-display');
        els.mosGrowthSlider = document.getElementById('mos-growth-rate-slider');
        els.mosGrowthDisplay = document.getElementById('mos-growth-rate-display');
        els.paybackChart = document.getElementById('payback-chart');
        els.warningStrip = document.getElementById('intel-warning-strip');

        // Tab buttons
        els.tabs = document.querySelectorAll('.intel-tab');
        els.calcCards = {
            payback: document.getElementById('calc-payback'),
            margin: document.getElementById('calc-margin'),
            breakeven: document.getElementById('calc-breakeven')
        };

        // Attach event listeners
        attachListeners();

        // Set initial visibility based on current form state
        var type = document.querySelector('input[name="type"]:checked');
        if (type) {
            updatePanelVisibility(type.value);
        }
    }

    function attachListeners() {
        // Growth rate slider (Earnings Payback)
        if (els.growthSlider) {
            els.growthSlider.addEventListener('input', function() {
                state.growthRate = Number(this.value);
                els.growthDisplay.textContent = state.growthRate + '%';
                // Sync Margin of Safety slider too
                if (els.mosGrowthSlider) {
                    els.mosGrowthSlider.value = state.growthRate;
                    els.mosGrowthDisplay.textContent = state.growthRate + '%';
                }
                recalculate();
            });
        }

        // Growth rate slider (Margin of Safety)
        if (els.mosGrowthSlider) {
            els.mosGrowthSlider.addEventListener('input', function() {
                state.growthRate = Number(this.value);
                els.mosGrowthDisplay.textContent = state.growthRate + '%';
                // Sync Earnings Payback slider too
                if (els.growthSlider) {
                    els.growthSlider.value = state.growthRate;
                    els.growthDisplay.textContent = state.growthRate + '%';
                }
                recalculate();
            });
        }

        // Tab switching
        els.tabs.forEach(function(tab) {
            tab.addEventListener('click', function() {
                switchTab(this.getAttribute('data-tab'));
            });
        });

        // Listen for form changes
        var companySelect = document.getElementById('company_id');
        var typeRadios = document.querySelectorAll('input[name="type"]');
        var quantityInput = document.getElementById('quantity');
        var priceInput = document.getElementById('price_per_share');
        var feesInput = document.getElementById('fees');

        if (companySelect) {
            companySelect.addEventListener('change', onCompanyChange);
        }

        typeRadios.forEach(function(radio) {
            radio.addEventListener('change', onTransactionTypeChange);
        });

        [quantityInput, priceInput, feesInput].forEach(function(input) {
            if (input) input.addEventListener('input', onFormValueChange);
        });
    }

    function onTransactionTypeChange() {
        var type = document.querySelector('input[name="type"]:checked');
        if (!type) return;
        updatePanelVisibility(type.value);
    }

    function onCompanyChange() {
        var companySelect = document.getElementById('company_id');
        var companyId = companySelect ? companySelect.value : null;
        var type = document.querySelector('input[name="type"]:checked');

        if (!companyId || !type || type.value !== 'BUY') {
            state.companyData = null;
            updatePanelVisibility(type ? type.value : 'BUY');
            return;
        }

        // Fetch intelligence data
        fetchCompanyIntelligence(companyId);
    }

    function onFormValueChange() {
        recalculate();
    }

    function fetchCompanyIntelligence(companyId) {
        state.loading = true;
        state.fetchCounter++;
        var myFetch = state.fetchCounter;

        showLoadingState();

        fetch('/portfolio/api/company-intelligence/' + companyId)
            .then(function(response) { return response.json(); })
            .then(function(data) {
                // Ignore stale responses
                if (myFetch !== state.fetchCounter) return;

                state.loading = false;
                if (data.success && data.data && !data.data.data_unavailable) {
                    state.companyData = data.data;
                    els.tickerLabel.textContent = data.data.ticker;
                    prefillPrice(data.data.current_price);
                    showPanel();
                    recalculate();
                } else if (data.success && data.data && data.data.data_unavailable) {
                    state.companyData = data.data;
                    els.tickerLabel.textContent = data.data.ticker;
                    prefillPrice(data.data.current_price);
                    showPanel();
                    showPartialData();
                } else {
                    state.companyData = null;
                    showDataUnavailable();
                }
            })
            .catch(function(err) {
                if (myFetch !== state.fetchCounter) return;
                console.error('Intelligence fetch failed:', err);
                state.loading = false;
                state.companyData = null;
                showDataUnavailable();
            });
    }

    function updatePanelVisibility(txType) {
        var companySelect = document.getElementById('company_id');
        var hasCompany = companySelect && companySelect.value;

        if (txType !== 'BUY') {
            hidePanel();
            hidePlaceholder();
            return;
        }

        if (!hasCompany || !state.companyData) {
            hidePanel();
            showPlaceholder();
            return;
        }

        hidePlaceholder();
        showPanel();
    }

    function showPanel() {
        if (els.panel) els.panel.style.display = '';
        if (els.placeholder) els.placeholder.style.display = 'none';
    }

    function hidePanel() {
        if (els.panel) els.panel.style.display = 'none';
    }

    function showPlaceholder() {
        if (els.placeholder) els.placeholder.style.display = '';
    }

    function hidePlaceholder() {
        if (els.placeholder) els.placeholder.style.display = 'none';
    }

    function showLoadingState() {
        showPanel();
        hidePlaceholder();
        var body = document.querySelector('.intel-panel-body');
        if (body) {
            var cards = body.querySelectorAll('.calc-card');
            cards.forEach(function(card) {
                if (card.style.display !== 'none') {
                    var calcBody = card.querySelector('.calc-body');
                    if (calcBody) {
                        calcBody.insertAdjacentHTML('afterbegin',
                            '<div class="intel-loading" id="intel-loading-indicator"><div class="spinner"></div><span>Loading market data...</span></div>');
                    }
                }
            });
        }
    }

    function removeLoadingIndicator() {
        var indicator = document.getElementById('intel-loading-indicator');
        if (indicator) indicator.remove();
    }

    function showDataUnavailable() {
        showPanel();
        hidePlaceholder();
        var summaries = ['payback-summary', 'mos-summary'];
        summaries.forEach(function(id) {
            var el = document.getElementById(id);
            if (el) {
                el.innerHTML = '<div class="intel-unavailable"><i class="bi bi-cloud-slash"></i><p>Unable to load market data.</p>' +
                    '<button class="intel-retry-btn" onclick="IntelligencePanel.retry()"><i class="bi bi-arrow-clockwise"></i> Retry</button></div>';
            }
        });
    }

    function showPartialData() {
        // Data exists but PE/EPS unavailable
        removeLoadingIndicator();
        var paybackSummary = document.getElementById('payback-summary');
        if (paybackSummary && !state.companyData.pe_ratio) {
            paybackSummary.innerHTML = '<div class="calc-empty">P/E data unavailable for ' + escapeHtml(state.companyData.ticker) + '</div>';
        }
        var mosSummary = document.getElementById('mos-summary');
        if (mosSummary && !state.companyData.eps_ttm) {
            mosSummary.innerHTML = '<div class="calc-empty">EPS data unavailable for ' + escapeHtml(state.companyData.ticker) + '</div>';
        }
        // Break-even still works with form values
        renderBreakEven();
    }

    function switchTab(tabId) {
        state.activeTab = tabId;

        // Update tab active states
        els.tabs.forEach(function(tab) {
            tab.classList.toggle('active', tab.getAttribute('data-tab') === tabId);
        });

        // Show/hide calc cards
        Object.keys(els.calcCards).forEach(function(key) {
            if (els.calcCards[key]) {
                els.calcCards[key].style.display = (key === tabId) ? '' : 'none';
            }
        });

        // Re-render active tab
        recalculate();
    }

    function recalculate() {
        removeLoadingIndicator();
        if (!state.companyData) return;

        renderPayback();
        renderMarginOfSafety();
        renderBreakEven();
    }

    // ═══════════════════════════════════════════
    // EARNINGS PAYBACK PERIOD
    // ═══════════════════════════════════════════
    function renderPayback() {
        var cd = state.companyData;
        var pe = cd.pe_ratio;

        var summaryEl = document.getElementById('payback-summary');
        var insightEl = document.getElementById('payback-insight');
        var insightText = document.getElementById('payback-insight-text');

        if (!pe || pe <= 0) {
            summaryEl.innerHTML = '<div class="calc-empty">' +
                (pe && pe < 0 ? 'Negative P/E \u2014 company is not currently profitable. Earnings payback not applicable.' :
                'P/E data unavailable for ' + escapeHtml(cd.ticker)) + '</div>';
            insightEl.style.display = 'none';
            destroyChart();
            return;
        }

        var result = IntelligenceEngine.calcEarningsPayback(pe, state.growthRate);
        if (!result) return;

        // Render Chart
        renderPaybackChart(result, pe);

        // Summary
        var paybackColor = !result.paybackYear ? '#ef4444'
            : result.paybackYear <= 10 ? '#2d6a4f'
            : result.paybackYear <= 20 ? '#d97706' : '#ef4444';

        var valueText = result.paybackYear ? result.paybackYear + ' years' : '30+ years';
        var labelText = result.paybackYear
            ? 'At ' + state.growthRate + '% annual growth, cumulative earnings cover the price in ' + result.paybackYear + ' years.'
            : 'At ' + state.growthRate + '% growth, earnings won\u2019t cover the price within 30 years. Consider whether P/E of ' + pe.toFixed(1) + '\u00d7 is justified.';

        summaryEl.innerHTML = '<div class="calc-summary-value" style="color:' + paybackColor + '">' + valueText + '</div>'
            + '<div class="calc-summary-label">' + labelText + '</div>';

        // Insight
        var reqCAGR = IntelligenceEngine.findRequiredCAGR(pe, 10);
        insightEl.style.display = '';
        insightText.innerHTML = 'For a 10-year payback, this company needs <strong>' + reqCAGR.toFixed(1) + '%</strong> annual earnings growth.';
    }

    function renderPaybackChart(result, pe) {
        if (typeof Chart === 'undefined') return;

        destroyChart();

        var ctx = els.paybackChart.getContext('2d');
        var grad = ctx.createLinearGradient(0, 0, 0, 180);
        grad.addColorStop(0, 'rgba(45,106,79,.22)');
        grad.addColorStop(1, 'rgba(45,106,79,.01)');

        // Sample labels for readability (don't show all 31 points)
        var displayLabels = result.labels.map(function(y) {
            return y === 0 ? 'Now' : y % 5 === 0 ? 'Yr ' + y : '';
        });

        state.chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: displayLabels,
                datasets: [
                    {
                        label: 'Cumulative Earnings',
                        data: result.cumulativeData,
                        borderColor: '#2d6a4f',
                        backgroundColor: grad,
                        fill: true,
                        tension: 0.35,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        borderWidth: 2.5
                    },
                    {
                        label: 'Purchase Price (P/E)',
                        data: result.labels.map(function() { return pe; }),
                        borderColor: '#ef4444',
                        borderDash: [6, 4],
                        fill: false,
                        pointRadius: 0,
                        borderWidth: 1.5
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        titleFont: { family: 'Inter', size: 11 },
                        bodyFont: { family: 'Inter', size: 11 },
                        padding: 8,
                        cornerRadius: 6,
                        callbacks: {
                            title: function(items) {
                                var idx = items[0].dataIndex;
                                return idx === 0 ? 'Now' : 'Year ' + idx;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { family: 'Inter', size: 10 }, color: '#9ca3af', maxTicksLimit: 7 }
                    },
                    y: {
                        grid: { color: 'rgba(0,0,0,.04)' },
                        ticks: { font: { family: 'Inter', size: 10 }, color: '#9ca3af' }
                    }
                },
                interaction: { intersect: false, mode: 'index' }
            }
        });
    }

    function destroyChart() {
        if (state.chartInstance) {
            state.chartInstance.destroy();
            state.chartInstance = null;
        }
    }

    // ═══════════════════════════════════════════
    // MARGIN OF SAFETY (Graham Formula)
    // ═══════════════════════════════════════════
    function renderMarginOfSafety() {
        var cd = state.companyData;
        var eps = cd.eps_ttm;
        var price = getFormPrice() || cd.current_price;
        var cs = CURRENCY_SYMBOLS[cd.currency] || '$';

        var summaryEl = document.getElementById('mos-summary');
        var insightEl = document.getElementById('mos-insight');
        var fairValueEl = document.getElementById('mos-fair-value');
        var yourPriceEl = document.getElementById('mos-your-price');
        var gaugeFill = document.getElementById('mos-gauge-fill');

        if (!eps || !price) {
            summaryEl.innerHTML = '<div class="calc-empty">' +
                (!eps ? 'EPS data unavailable for ' + escapeHtml(cd.ticker) : 'Enter a price to calculate margin of safety') + '</div>';
            insightEl.style.display = 'none';
            fairValueEl.textContent = '--';
            yourPriceEl.textContent = '--';
            gaugeFill.style.width = '50%';
            gaugeFill.style.background = '#9ca3af';
            return;
        }

        var result = IntelligenceEngine.calcMarginOfSafety(eps, state.growthRate, price);
        if (!result) return;

        // Update values
        fairValueEl.textContent = cs + result.intrinsicValue.toFixed(2);
        yourPriceEl.textContent = cs + result.currentPrice.toFixed(2);

        // Gauge fill
        var gaugeWidth = Math.min(Math.max(50 + result.margin / 2, 2), 98);
        var gaugeColor;
        if (result.margin > 30) gaugeColor = '#2d6a4f';
        else if (result.margin > 15) gaugeColor = '#10b981';
        else if (result.margin > 0) gaugeColor = '#f59e0b';
        else if (result.margin > -15) gaugeColor = '#f97316';
        else gaugeColor = '#ef4444';

        gaugeFill.style.width = gaugeWidth + '%';
        gaugeFill.style.background = gaugeColor;

        // Summary
        var marginText, summaryColor;
        if (result.margin >= 0) {
            marginText = '+' + result.margin.toFixed(1) + '% margin';
            summaryColor = result.margin > 30 ? '#2d6a4f' : result.margin > 15 ? '#10b981' : '#f59e0b';
        } else {
            marginText = result.margin.toFixed(1) + '% premium';
            summaryColor = '#ef4444';
        }

        var explanation = result.margin >= 30
            ? 'Strong margin of safety. The stock appears significantly undervalued based on Graham\u2019s formula.'
            : result.margin >= 15
            ? 'Decent margin of safety. Some buffer exists between fair value and current price.'
            : result.margin >= 0
            ? 'Thin margin of safety. Limited downside protection at this price.'
            : 'Trading above estimated fair value. Consider whether growth assumptions justify the premium.';

        summaryEl.innerHTML = '<div class="calc-summary-value" style="color:' + summaryColor + '">' + marginText + '</div>'
            + '<div class="calc-summary-label">' + explanation + '</div>';

        // Insight
        insightEl.style.display = '';
    }

    // ═══════════════════════════════════════════
    // BREAK-EVEN ANALYSIS
    // ═══════════════════════════════════════════
    function renderBreakEven() {
        var cd = state.companyData;
        var cs = cd ? (CURRENCY_SYMBOLS[cd.currency] || '$') : '$';
        var quantity = getFormQuantity();
        var price = getFormPrice();
        var fees = getFormFees();

        var totalCostEl = document.getElementById('be-total-cost');
        var totalDetailEl = document.getElementById('be-total-detail');
        var priceEl = document.getElementById('be-price');
        var priceDetailEl = document.getElementById('be-price-detail');
        var insightEl = document.getElementById('be-insight');
        var insightText = document.getElementById('be-insight-text');

        if (!quantity || !price) {
            totalCostEl.textContent = '--';
            totalDetailEl.textContent = '';
            priceEl.textContent = '--';
            priceDetailEl.textContent = '';
            insightEl.style.display = 'none';
            return;
        }

        var result = IntelligenceEngine.calcBreakEven(quantity, price, fees);
        if (!result) return;

        totalCostEl.textContent = cs + formatNumber(result.totalCost);
        totalDetailEl.textContent = result.quantity + ' \u00d7 ' + cs + result.pricePerShare.toFixed(2) + (result.fees > 0 ? ' + ' + cs + result.fees.toFixed(2) + ' fees' : '');

        priceEl.textContent = cs + result.breakEvenPrice.toFixed(2);
        priceDetailEl.textContent = result.feesPerShare > 0 ? cs + result.feesPerShare.toFixed(4) + '/share above purchase' : 'Equals purchase price';

        // Insight
        if (fees > 0) {
            var feePct = ((result.breakEvenPrice - price) / price * 100);
            insightEl.style.display = '';
            insightEl.className = 'calc-insight';
            insightText.innerHTML = 'Fees add <strong>' + cs + result.feesPerShare.toFixed(4) + '</strong> per share. Stock must rise <strong>' + feePct.toFixed(2) + '%</strong> just to cover trading costs.';
        } else {
            insightEl.style.display = '';
            insightEl.className = 'calc-insight calc-insight--neutral';
            insightText.innerHTML = 'No fees \u2014 your break-even price equals your purchase price.';
        }
    }

    // ═══════════════════════════════════════════
    // WARNING STRIP
    // ═══════════════════════════════════════════
    function renderWarningStrip(warnings) {
        var strip = els.warningStrip;
        if (!strip) return;

        if (!warnings || warnings.length === 0) {
            strip.innerHTML = '';
            return;
        }

        var html = '';
        warnings.forEach(function(w) {
            var severityClass = 'intel-warn--' + w.severity;
            var icon = w.severity === 'high' ? 'bi-exclamation-triangle-fill'
                : w.severity === 'medium' ? 'bi-exclamation-triangle-fill'
                : 'bi-info-circle-fill';

            html += '<div class="intel-warn-item ' + severityClass + '">'
                + '<i class="bi ' + icon + '"></i>'
                + '<div><strong>' + escapeHtml(w.title) + '</strong>'
                + '<p>' + escapeHtml(w.message) + '</p></div></div>';
        });

        strip.innerHTML = html;
    }

    // ═══════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════
    function prefillPrice(currentPrice) {
        if (!currentPrice) return;
        var priceInput = document.getElementById('price_per_share');
        if (!priceInput) return;
        priceInput.value = currentPrice.toFixed(2);
        // Fire input event so the existing total calculation and warnings update
        priceInput.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function getFormPrice() {
        var el = document.getElementById('price_per_share');
        return el ? parseFloat(el.value) || 0 : 0;
    }

    function getFormQuantity() {
        var el = document.getElementById('quantity');
        return el ? parseFloat(el.value) || 0 : 0;
    }

    function getFormFees() {
        var el = document.getElementById('fees');
        return el ? parseFloat(el.value) || 0 : 0;
    }

    function formatNumber(num) {
        if (num >= 1000000) return (num / 1000000).toFixed(2) + 'M';
        if (num >= 1000) return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return num.toFixed(2);
    }

    function escapeHtml(text) {
        if (!text) return '';
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function retry() {
        var companySelect = document.getElementById('company_id');
        if (companySelect && companySelect.value) {
            fetchCompanyIntelligence(companySelect.value);
        }
    }

    // Public API
    return {
        init: init,
        retry: retry,
        syncWarnings: renderWarningStrip
    };
})();

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    IntelligencePanel.init();
});
