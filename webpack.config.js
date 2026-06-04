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
