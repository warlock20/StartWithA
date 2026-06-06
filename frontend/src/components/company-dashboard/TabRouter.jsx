import { useState, useEffect, useRef } from 'react';

/**
 * TabRouter — React island for the company dashboard tab bar + hash routing.
 *
 * Replaces the tab switching logic from company-dashboard.js (lines 28-158).
 * Panels stay as Jinja2-rendered HTML; this component toggles their `active`
 * class. Library and research sub-nav click handlers are attached via bridge
 * pattern (useEffect on DOM elements).
 *
 * Dispatches custom events for lazy-init coordination with the remaining
 * vanilla JS in company-dashboard.js:
 *   - `tab-changed` → { tabId }
 *   - `library-section-changed` → { sectionId }
 *   - `research-section-changed` → { sectionId }
 *
 * Props (via config):
 *   items: Array of { type: 'tab'|'separator', key?, label?, icon?, count?, auto? }
 */
export function TabRouter({ items }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [librarySection, setLibrarySection] = useState('documents');
  const [researchSection, setResearchSection] = useState('summary');
  const handlersRef = useRef({});

  // Keep handlers ref current for global functions
  handlersRef.current = {
    switchToTab: handleSwitchToTab,
    switchLibrarySection: (s) => setLibrarySection(s),
    switchResearchSection: (s) => setResearchSection(s),
  };

  // ------------------------------------------------------------------
  // Parse initial hash on mount
  // ------------------------------------------------------------------
  useEffect(() => {
    const hash = window.location.hash.substring(1);
    if (!hash) return;

    if (hash.startsWith('library/')) {
      const section = hash.split('/')[1] || 'documents';
      setActiveTab('library');
      setLibrarySection(section);
    } else if (hash.startsWith('research/')) {
      const section = hash.split('/')[1] || 'summary';
      setActiveTab('research');
      setResearchSection(section);
    } else if (['documents', 'notes', 'journal'].includes(hash)) {
      // Legacy hash support
      setActiveTab('library');
      setLibrarySection(hash);
    } else if (document.getElementById('panel-' + hash)) {
      setActiveTab(hash);
    }
  }, []);

  // ------------------------------------------------------------------
  // Apply active state to main panels + update hash
  // ------------------------------------------------------------------
  useEffect(() => {
    document.querySelectorAll('.unified-tab-panel').forEach((p) => p.classList.remove('active'));
    var panel = document.getElementById('panel-' + activeTab);
    if (panel) panel.classList.add('active');

    // Update hash
    if (activeTab === 'library') {
      history.replaceState(null, '', '#library/' + librarySection);
    } else if (activeTab === 'research') {
      history.replaceState(null, '', '#research/' + researchSection);
    } else {
      history.replaceState(null, '', '#' + activeTab);
    }

    // Dispatch tab-changed event
    document.dispatchEvent(new CustomEvent('tab-changed', { detail: { tabId: activeTab } }));
  }, [activeTab]);

  // ------------------------------------------------------------------
  // Apply library sub-section state
  // ------------------------------------------------------------------
  useEffect(() => {
    document
      .querySelectorAll('.library-nav-item')
      .forEach((n) => n.classList.remove('active'));
    document
      .querySelectorAll('.library-section')
      .forEach((s) => s.classList.remove('active'));

    var nav = document.querySelector('[data-library-section="' + librarySection + '"]');
    var section = document.getElementById('library-' + librarySection);
    if (nav) nav.classList.add('active');
    if (section) section.classList.add('active');

    if (activeTab === 'library') {
      history.replaceState(null, '', '#library/' + librarySection);
      document.dispatchEvent(
        new CustomEvent('library-section-changed', { detail: { sectionId: librarySection } }),
      );
    }
  }, [librarySection, activeTab]);

  // ------------------------------------------------------------------
  // Apply research sub-section state
  // ------------------------------------------------------------------
  useEffect(() => {
    document
      .querySelectorAll('.research-nav-item')
      .forEach((n) => n.classList.remove('active'));
    document
      .querySelectorAll('.research-section')
      .forEach((s) => s.classList.remove('active'));

    var nav = document.querySelector('[data-research-section="' + researchSection + '"]');
    var section = document.getElementById('research-' + researchSection);
    if (nav) nav.classList.add('active');
    if (section) section.classList.add('active');

    if (activeTab === 'research') {
      history.replaceState(null, '', '#research/' + researchSection);
      document.dispatchEvent(
        new CustomEvent('research-section-changed', { detail: { sectionId: researchSection } }),
      );
    }
  }, [researchSection, activeTab]);

  // ------------------------------------------------------------------
  // Attach click handlers to library/research sub-nav buttons (bridge)
  // ------------------------------------------------------------------
  useEffect(() => {
    function handleLibraryClick(e) {
      var section = e.currentTarget.dataset.librarySection;
      if (section) handlersRef.current.switchLibrarySection(section);
    }
    function handleResearchClick(e) {
      var section = e.currentTarget.dataset.researchSection;
      if (section) handlersRef.current.switchResearchSection(section);
    }

    var libraryItems = document.querySelectorAll('.library-nav-item');
    var researchItems = document.querySelectorAll('.research-nav-item');

    libraryItems.forEach((el) => el.addEventListener('click', handleLibraryClick));
    researchItems.forEach((el) => el.addEventListener('click', handleResearchClick));

    return () => {
      libraryItems.forEach((el) => el.removeEventListener('click', handleLibraryClick));
      researchItems.forEach((el) => el.removeEventListener('click', handleResearchClick));
    };
  }, []);

  // ------------------------------------------------------------------
  // Expose global functions for backward compat
  // ------------------------------------------------------------------
  useEffect(() => {
    window.switchToTab = (...args) => handlersRef.current.switchToTab(...args);
    window.switchLibrarySection = (...args) => handlersRef.current.switchLibrarySection(...args);
    window.switchResearchSection = (...args) => handlersRef.current.switchResearchSection(...args);

    return () => {
      delete window.switchToTab;
      delete window.switchLibrarySection;
      delete window.switchResearchSection;
    };
  }, []);

  // ------------------------------------------------------------------
  // Collapsible sections: detect overflow and show expand button
  // ------------------------------------------------------------------
  useEffect(() => {
    requestAnimationFrame(() => {
      document.querySelectorAll('.unified-collapsible').forEach((el) => {
        var content = el.querySelector('.unified-collapsible-content');
        var btn = el.nextElementSibling;
        if (!content || !btn || !btn.classList.contains('unified-expand-btn')) return;
        if (content.scrollHeight > el.clientHeight + 4) {
          btn.style.display = '';
        } else {
          el.style.maxHeight = 'none';
          var fade = el.querySelector('.unified-collapsible-fade');
          if (fade) fade.style.display = 'none';
          btn.style.display = 'none';
        }
      });
    });
  }, []);

  // ------------------------------------------------------------------
  // Handlers
  // ------------------------------------------------------------------

  function handleSwitchToTab(tabId) {
    // Handle legacy tab IDs that map to library sub-sections
    if (['documents', 'notes', 'journal'].includes(tabId)) {
      setActiveTab('library');
      setLibrarySection(tabId);
      return;
    }
    setActiveTab(tabId);
    if (tabId === 'library') setLibrarySection((s) => s || 'documents');
    if (tabId === 'research') setResearchSection((s) => s || 'summary');
  }

  function handleTabClick(tabKey) {
    handleSwitchToTab(tabKey);
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <div className="unified-tab-bar" id="unifiedTabBar">
      {items.map((item, idx) => {
        if (item.type === 'separator') {
          return (
            <div
              key={'sep-' + idx}
              className="unified-tab-separator"
              style={item.auto ? { marginLeft: 'auto' } : undefined}
            />
          );
        }
        return (
          <button
            key={item.key}
            className={'unified-pill-tab' + (activeTab === item.key ? ' active' : '')}
            data-tab={item.key}
            onClick={() => handleTabClick(item.key)}
          >
            {item.icon && <i className={'bi ' + item.icon} />} {item.label}
            {item.count > 0 && <span className="unified-tab-count">{item.count}</span>}
          </button>
        );
      })}
    </div>
  );
}
