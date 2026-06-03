/**
 * TabBar — the `.unified-pill-tab` pattern from the company dashboard.
 *
 * Renders a row of pill-shaped tab buttons that match the existing CSS
 * classes in `_company-dashboard.css`.
 *
 * Usage:
 *   <TabBar
 *     tabs={[
 *       { key: 'overview', label: 'Overview', icon: 'bi-grid-1x2' },
 *       { key: 'timeline', label: 'Timeline', icon: 'bi-list-ul', count: 12 },
 *       { key: 'research', label: 'Research', icon: 'bi-microscope' },
 *     ]}
 *     activeTab="overview"
 *     onTabChange={(key) => setActiveTab(key)}
 *     separators={[1, 3]}   // optional: indices after which to insert separators
 *   />
 */
export function TabBar({ tabs, activeTab, onTabChange, separators = [], className = '' }) {
  return (
    <div className={`unified-tab-bar ${className}`.trim()}>
      {tabs.map((tab, i) => (
        <TabItem
          key={tab.key}
          tab={tab}
          isActive={activeTab === tab.key}
          onClick={() => onTabChange(tab.key)}
          showSeparatorAfter={separators.includes(i)}
        />
      ))}
    </div>
  );
}

function TabItem({ tab, isActive, onClick, showSeparatorAfter }) {
  return (
    <>
      <button
        className={`unified-pill-tab${isActive ? ' active' : ''}${tab.hidden ? ' d-none' : ''}`}
        data-tab={tab.key}
        onClick={onClick}
        disabled={tab.disabled}
      >
        {tab.icon && <i className={`bi ${tab.icon}`} />} {tab.label}
        {tab.count != null && tab.count > 0 && (
          <span className="unified-tab-count">{tab.count}</span>
        )}
      </button>
      {showSeparatorAfter && <div className="unified-tab-separator" />}
    </>
  );
}
