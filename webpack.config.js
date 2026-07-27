const path = require('path');

module.exports = {
  entry: {
    'blocknote-editor': './frontend/src/blocknote-editor.js',
    'company-resources-manager': './frontend/src/company-resources-manager.js',
    'session-summary': './frontend/src/session-summary.js',
    'duplicate-detector': './frontend/src/duplicate-detector.js',
    'hashtag-autocomplete': './frontend/src/hashtag-autocomplete.js',
    'company-search': './frontend/src/company-search.js',
    'company-tagging': './frontend/src/company-tagging.js',
    'intelligence-panel': './frontend/src/intelligence-panel.js',
    'ai-research-assistant': './frontend/src/ai-research-assistant.js',
    'document-annotations': './frontend/src/document-annotations.js',
    'market-sweep': './frontend/src/market-sweep.js',
    'company-dashboard-tabs': './frontend/src/company-dashboard-tabs.js',
    'standalone-qa': './frontend/src/standalone-qa.js',
    'journal-entries': './frontend/src/journal-entries.js',
    'company-annotations-panel': './frontend/src/company-annotations-panel.js',
    'settings-form': './frontend/src/settings-form.js',
    'sec-filings-fetcher': './frontend/src/sec-filings-fetcher.js',
    'transactions-table': './frontend/src/transactions-table.js',
    'sector-canvas': './frontend/src/sector-canvas.js',
    'analytics-charts': './frontend/src/analytics-charts.js',
    'sidebar': './frontend/src/sidebar.js',
    'financials-charts': './frontend/src/financials-charts.js',
    'checklist-inspector': './frontend/src/checklist-inspector.js',
    'portfolio-dashboard': './frontend/src/portfolio-dashboard.js',
    'home-preview': './frontend/src/home-preview.js',
  },
  output: {
    filename: '[name].bundle.js',
    path: path.resolve(__dirname, 'app/static/js/dist'),
    clean: true,
  },
  module: {
    rules: [
      {
        test: /\.jsx?$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: [
              ['@babel/preset-env', { targets: 'defaults' }],
              ['@babel/preset-react', { runtime: 'automatic' }]
            ]
          }
        }
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader']
      }
    ]
  },
  resolve: {
    extensions: ['.js', '.jsx']
  },
  devtool: 'source-map',
  optimization: {
    minimize: true,
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        // Disable automatic splitting of shared app modules — each entry
        // bundle inlines its own app dependencies.  Only vendor code
        // (node_modules) gets split into shared chunks that are loaded
        // globally via _base.html.
        default: false,
        blocknote: {
          test: /[\\/]node_modules[\\/](@blocknote|@mantine|@tabler[\\/]icons-react|@tiptap|prosemirror-[^/\\]+|@floating-ui|@radix-ui|@emoji-mart|yjs|y-prosemirror|lib0|parse5|micromark[^/\\]*|linkifyjs|unified|vfile[^/\\]*|hast-[^/\\]+|mdast-[^/\\]+|rehype-[^/\\]+|remark-[^/\\]+|unist-[^/\\]+|property-information|hastscript|comma-separated-tokens|space-separated-tokens|stringify-entities|markdown-table|longest-streak|decode-named-character-reference|character-entities-legacy|ccount|trim-lines|trim-trailing-lines|zwitch|web-namespaces|html-void-elements|html-whitespace-sensitive-tag-names|is-buffer|extend|orderedmap|uuid)[\\/]/,
          name: 'vendors-blocknote',
          chunks: 'all',
          priority: 30,
        },
        recharts: {
          test: /[\\/]node_modules[\\/](recharts|d3-[^/\\]+|victory-vendor|@reduxjs|react-redux|redux|redux-thunk|reselect|immer|decimal\.js-light|eventemitter3|internmap)[\\/]/,
          name: 'vendors-recharts',
          chunks: 'all',
          priority: 20,
        },
        core: {
          test: /[\\/]node_modules[\\/](react|react-dom|@tanstack|scheduler)[\\/]/,
          name: 'vendors-core',
          chunks: 'all',
          priority: 15,
        },
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          chunks: 'all',
          priority: 10,
        },
      },
    },
  }
};
