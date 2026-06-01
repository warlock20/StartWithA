/**
 * Client-Side Ticker Symbol Validator
 * Mirrors the Python TickerValidator for consistent validation
 *
 * ES module version for use by React islands.
 * The original app/static/js/ticker-validator.js remains for vanilla JS consumers.
 */

export class TickerValidator {
    // Exchange code mapping: Google Finance prefix → Yahoo Finance suffix
    static EXCHANGE_MAP = {
        // US Markets (no suffix in Yahoo)
        'NYSE': '',
        'NASDAQ': '',
        'NYSEAMERICAN': '',
        'NYSEARCA': '',
        'BATS': '',
        'OTC': '',
        'OTCMKTS': '',

        // International Markets
        'FRA': '.F',       // Frankfurt → Germany (Frankfurt)
        'ETR': '.DE',      // XETRA → Germany (XETRA)
        'BER': '.BE',      // Berlin
        'MUN': '.MU',      // Munich
        'STU': '.SG',      // Stuttgart

        'LON': '.L',       // London
        'LSE': '.L',       // London Stock Exchange

        'EPA': '.PA',      // Euronext Paris
        'PAR': '.PA',      // Paris

        'TYO': '.T',       // Tokyo
        'JPX': '.T',       // Japan Exchange

        'TSE': '.TO',      // Toronto
        'CVE': '.V',       // Canadian Venture

        'NSE': '.NS',      // National Stock Exchange of India
        'BOM': '.BO',      // Bombay Stock Exchange

        'HKG': '.HK',      // Hong Kong
        'HKEX': '.HK',

        'SHE': '.SZ',      // Shenzhen
        'SHA': '.SS',      // Shanghai

        'KRX': '.KS',      // Korea
        'KSE': '.KS',

        'ASX': '.AX',      // Australian Securities Exchange

        'SWX': '.SW',      // Swiss Exchange
        'VTX': '.SW',

        'AMS': '.AS',      // Amsterdam
        'BRU': '.BR',      // Brussels
        'EBR': '.BR',
        'CPH': '.CO',      // Copenhagen
        'HEL': '.HE',      // Helsinki
        'STO': '.ST',      // Stockholm
        'OSL': '.OL',      // Oslo

        'BME': '.MC',      // Madrid
        'MCE': '.MC',
        'BIT': '.MI',      // Milan

        'JSE': '.JO',      // Johannesburg
        'TAE': '.TA',      // Tel Aviv
        'IST': '.IS',      // Istanbul
        'SAU': '.SA',      // Saudi Arabia
    };

    static EXCHANGE_NAMES = {
        '': 'United States',
        '.DE': 'Germany (XETRA)',
        '.F': 'Germany (Frankfurt)',
        '.BE': 'Germany (Berlin)',
        '.MU': 'Germany (Munich)',
        '.SG': 'Germany (Stuttgart)',
        '.DU': 'Germany (Dusseldorf)',
        '.HM': 'Germany (Hamburg)',
        '.HA': 'Germany (Hanover)',
        '.L': 'United Kingdom (LSE)',
        '.PA': 'France (Euronext Paris)',
        '.T': 'Japan (Tokyo)',
        '.TO': 'Canada (Toronto)',
        '.V': 'Canada (Venture)',
        '.NS': 'India (NSE)',
        '.BO': 'India (BSE)',
        '.HK': 'Hong Kong',
        '.SZ': 'China (Shenzhen)',
        '.SS': 'China (Shanghai)',
        '.KS': 'South Korea',
        '.AX': 'Australia',
        '.SW': 'Switzerland',
        '.AS': 'Netherlands',
        '.BR': 'Belgium',
        '.CO': 'Denmark',
        '.HE': 'Finland',
        '.ST': 'Sweden',
        '.OL': 'Norway',
        '.MC': 'Spain',
        '.MI': 'Italy',
        '.JO': 'South Africa',
        '.TA': 'Israel',
        '.IS': 'Turkey',
        '.SA': 'Saudi Arabia',
        '.NZ': 'New Zealand',
        '.TW': 'Taiwan',
        '.VI': 'Austria (Vienna)',
        '.PR': 'Czech Republic (Prague)',
        '.WA': 'Poland (Warsaw)',
        '.BD': 'Hungary (Budapest)',
        '.IC': 'Iceland',
        '.IR': 'Ireland',
        '.LS': 'Portugal (Lisbon)',
        '.AT': 'Greece (Athens)',
        '.RG': 'Latvia (Riga)',
        '.TL': 'Estonia (Tallinn)',
        '.VS': 'Lithuania (Vilnius)',
    };

    /**
     * Parse and validate a ticker symbol
     * @param {string} tickerInput - Raw ticker input
     * @returns {Object} Validation result
     */
    static parseAndValidate(tickerInput) {
        const result = {
            isValid: false,
            normalizedTicker: null,
            displayTicker: null,
            exchangeCode: '',
            exchangeName: 'United States',
            originalFormat: 'unknown',
            errors: [],
            warnings: []
        };

        if (!tickerInput) {
            result.errors.push('Ticker symbol is required');
            return result;
        }

        // Clean and uppercase
        const ticker = tickerInput.trim().toUpperCase();

        if (ticker.length > 20) {
            result.errors.push('Ticker too long (max 20 characters)');
            return result;
        }

        // Try to parse the ticker
        const parsed = this._parseTickerFormat(ticker);

        if (!parsed.success) {
            result.errors.push(parsed.error);
            return result;
        }

        result.originalFormat = parsed.format;
        result.normalizedTicker = parsed.normalized;
        result.displayTicker = parsed.display;
        result.exchangeCode = parsed.exchangeSuffix;
        result.exchangeName = this.EXCHANGE_NAMES[parsed.exchangeSuffix] || 'Unknown Exchange';

        // Validate the normalized ticker
        const validation = this._validateNormalizedTicker(parsed.normalized);

        if (!validation.isValid) {
            result.errors.push(...validation.errors);
            return result;
        }

        result.isValid = true;
        result.warnings = validation.warnings;

        return result;
    }

    /**
     * Parse ticker from various formats
     * @private
     */
    static _parseTickerFormat(ticker) {
        // Format 1: Google Finance (PREFIX:TICKER)
        const googlePattern = /^([A-Z]{2,15}):([A-Z0-9.]{1,10})$/;
        let match = ticker.match(googlePattern);

        if (match) {
            const exchangePrefix = match[1];
            let symbol = match[2];

            const exchangeSuffix = this.EXCHANGE_MAP[exchangePrefix];

            if (exchangeSuffix === undefined) {
                return {
                    success: false,
                    error: `Unknown exchange: ${exchangePrefix}. Use Yahoo format (e.g., SAP.DE) or supported exchange codes.`
                };
            }

            // Handle share classes for US stocks
            if (exchangeSuffix === '' && symbol.includes('.')) {
                symbol = symbol.replace('.', '-');
            }

            return {
                success: true,
                format: 'google',
                normalized: symbol + exchangeSuffix,
                display: `${exchangePrefix}:${symbol}`,
                exchangeSuffix: exchangeSuffix
            };
        }

        // Format 2: Check for US share class FIRST (before general Yahoo pattern)
        // Examples: BRK.B, BF.A (single letter after dot = share class, not exchange)
        if (ticker.includes('.') && !ticker.includes(':')) {
            if (/^[A-Z]{1,5}\.[A-Z]$/.test(ticker)) {
                return {
                    success: true,
                    format: 'yahoo',
                    normalized: ticker.replace('.', '-'),
                    display: ticker,
                    exchangeSuffix: ''
                };
            }
        }

        // Format 3: Yahoo Finance (TICKER.SUFFIX or TICKER)
        const yahooPattern = /^([A-Z0-9-]{1,10})(\.[A-Z]{1,3})?$/;
        match = ticker.match(yahooPattern);

        if (match) {
            const symbol = match[1];
            const exchangeSuffix = match[2] || '';

            // Validate exchange suffix
            if (exchangeSuffix && !this.EXCHANGE_NAMES[exchangeSuffix]) {
                return {
                    success: false,
                    error: `Unknown exchange suffix: ${exchangeSuffix}`
                };
            }

            return {
                success: true,
                format: 'yahoo',
                normalized: symbol + exchangeSuffix,
                display: ticker,
                exchangeSuffix: exchangeSuffix
            };
        }

        return {
            success: false,
            error: 'Invalid ticker format. Use: AAPL, SAP.DE, or FRA:SAP'
        };
    }

    /**
     * Validate normalized ticker format
     * @private
     */
    static _validateNormalizedTicker(ticker) {
        const result = {
            isValid: true,
            errors: [],
            warnings: []
        };

        // Split ticker and exchange
        let symbol, exchange;
        if (ticker.includes('.')) {
            const parts = ticker.split('.');
            if (parts.length !== 2) {
                result.isValid = false;
                result.errors.push('Invalid format: multiple dots found');
                return result;
            }
            [symbol, exchange] = parts;
        } else {
            symbol = ticker;
            exchange = '';
        }

        // Validate symbol
        if (!/^[A-Z0-9-]{1,10}$/.test(symbol)) {
            result.isValid = false;
            result.errors.push('Ticker must be 1-10 alphanumeric characters or hyphens');
            return result;
        }

        // Check invalid patterns
        if (symbol.startsWith('-') || symbol.endsWith('-')) {
            result.isValid = false;
            result.errors.push('Ticker cannot start or end with hyphen');
            return result;
        }

        if (symbol.includes('--')) {
            result.isValid = false;
            result.errors.push('Ticker cannot contain consecutive hyphens');
            return result;
        }

        // Validate exchange suffix
        if (exchange) {
            if (!/^[A-Z]{1,3}$/.test(exchange)) {
                result.isValid = false;
                result.errors.push('Exchange suffix must be 1-3 uppercase letters');
                return result;
            }

            const fullSuffix = '.' + exchange;
            if (!this.EXCHANGE_NAMES[fullSuffix]) {
                result.warnings.push(`Unknown exchange suffix: ${fullSuffix}`);
            }
        }

        // Warnings
        if (symbol.length === 1) {
            result.warnings.push('Single-character tickers are rare');
        }

        if (symbol.length > 5 && !exchange) {
            result.warnings.push('Long US ticker symbols are uncommon');
        }

        if (/^[0-9]/.test(symbol)) {
            result.warnings.push('Ticker starts with number - common for some international exchanges');
        }

        if (symbol.includes('-') && exchange) {
            result.warnings.push('Share class indicators (hyphen) typically only for US stocks');
        }

        return result;
    }

    /**
     * Get base ticker without exchange or share class
     */
    static getBaseTicker(ticker) {
        // Remove exchange suffix
        if (ticker.includes('.')) {
            ticker = ticker.split('.')[0];
        }

        // Remove share class
        if (ticker.includes('-')) {
            ticker = ticker.split('-')[0];
        }

        return ticker;
    }

    /**
     * Format ticker for display
     */
    static formatForDisplay(ticker, includeExchangeName = true) {
        const result = this.parseAndValidate(ticker);

        if (!result.isValid) {
            return ticker;
        }

        if (includeExchangeName && result.exchangeCode) {
            return `${result.normalizedTicker} (${result.exchangeName})`;
        }

        return result.normalizedTicker;
    }

    /**
     * Quick validation helper
     */
    static validate(ticker) {
        const result = this.parseAndValidate(ticker);
        return {
            isValid: result.isValid,
            normalizedTicker: result.normalizedTicker,
            error: result.errors.join('; ') || null
        };
    }
}
