import { fonts } from "../../tokens";

const app = {
  bg: "#fff",
  border: "#e5e7eb",
  text: "#111827",
  muted: "#6b7280",
  faint: "#9ca3af",
  accent: "#2d6a4f",
  tabActive: "#fff",
  tabActiveBg: "#1e293b",
  noteBg: "#fff",
  noteHeader: "#eef2ff",
  noteHeaderBorder: "#c7d2fe",
};

const TABS = [
  { label: "All Items", count: 14, active: true },
  { label: "Curated Wisdom", count: 1, active: false },
  { label: "Research Notes", count: 13, active: false },
];

const NOTES = [
  {
    title: "Moved to Watchlist",
    body: "Valuation too high. Too expensive.",
    tags: ["Investment Action", "#Moved-to-Watchlist"],
    date: "Jun 06, 2026",
  },
  {
    title: "Research Tips",
    body: "Technology patented 20-30 years back. Check recent patents for future direction.",
    tags: ["Industry Analysis", "#ResearchTechniques"],
    date: "Apr 15, 2026",
  },
];

export function KnowledgeMockup() {
  return (
    <div style={styles.container}>
      {/* Window chrome */}
      <div style={styles.chrome}>
        <div style={{ display: "flex", gap: 6 }}>
          {["#ff5f57", "#febd2e", "#28c840"].map((c) => (
            <div key={c} style={{ ...styles.dot, background: c }} />
          ))}
        </div>
        <div style={styles.chromeTitle}>
          Knowledge Hub — Research Notes
        </div>
      </div>

      <div style={{ padding: "18px 22px" }}>
        {/* Header */}
        <div style={styles.header}>
          <div>
            <div style={styles.headerTitle}>Knowledge Hub</div>
            <div style={{ fontSize: 11, color: app.muted }}>
              Your research notes and curated wisdom
            </div>
          </div>
          <button style={styles.createBtn}>
            <span style={{ fontSize: 12 }}>+</span> Create New Entry
          </button>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
          {TABS.map((tab, i) => (
            <div
              key={i}
              style={{
                ...styles.tab,
                background: tab.active ? app.tabActiveBg : "transparent",
                color: tab.active ? app.tabActive : app.muted,
                border: tab.active ? "none" : `1px solid ${app.border}`,
                fontWeight: tab.active ? 600 : 400,
              }}
            >
              {tab.label}
              <span
                style={{
                  ...styles.tabCount,
                  background: tab.active
                    ? "rgba(255,255,255,0.2)"
                    : app.border,
                  color: tab.active ? app.tabActive : app.faint,
                }}
              >
                {tab.count}
              </span>
            </div>
          ))}
        </div>

        {/* Search */}
        <div style={styles.searchBar}>
          <span style={{ color: app.faint, fontSize: 13 }}>🔍</span>
          <span style={{ color: app.faint, fontSize: 12 }}>
            Search knowledge base...
          </span>
          <span
            style={{
              marginLeft: "auto",
              fontSize: 10,
              color: app.faint,
            }}
          >
            Group by: Company ▾
          </span>
        </div>

        {/* Company groups */}
        {[
          { name: "Siemens AG", count: 2, expanded: true },
          { name: "SAP SE", count: 1, expanded: false },
        ].map((group, gi) => (
          <div key={gi} style={{ marginBottom: 10 }}>
            <div style={styles.groupHeader}>
              <span style={{ fontSize: 10, color: app.muted }}>
                {group.expanded ? "▾" : "▸"}
              </span>
              <span
                style={{ fontSize: 12, fontWeight: 700, color: app.text }}
              >
                {group.name}
              </span>
              <span style={{ fontSize: 10, color: app.faint }}>
                {group.count} item{group.count > 1 ? "s" : ""}
              </span>
            </div>
            {group.expanded && (
              <div style={styles.notesGrid}>
                {NOTES.map((note, ni) => (
                  <div key={ni} style={styles.noteCard}>
                    <div style={styles.noteCardHeader}>
                      <span style={styles.noteType}>RESEARCH NOTE</span>
                    </div>
                    <div style={{ padding: 10 }}>
                      <div style={styles.noteTitle}>{note.title}</div>
                      <div style={styles.noteCompany}>Siemens AG</div>
                      <div style={styles.noteBody}>{note.body}</div>
                      <div style={styles.tagRow}>
                        {note.tags.map((tag, ti) => (
                          <span
                            key={ti}
                            style={{
                              ...styles.noteTag,
                              background: ti === 0 ? "#eff6ff" : "#f1f5f9",
                              color: ti === 0 ? "#2563eb" : app.muted,
                            }}
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                      <div style={{ fontSize: 9, color: app.faint }}>
                        {note.date}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

const styles = {
  container: {
    background: app.bg,
    border: `1px solid ${app.border}`,
    borderRadius: 16,
    overflow: "hidden",
    boxShadow: "0 24px 64px rgba(0,0,0,0.1), 0 4px 16px rgba(0,0,0,0.05)",
    maxWidth: 820,
    margin: "0 auto",
  },
  chrome: {
    padding: "10px 16px",
    borderBottom: `1px solid ${app.border}`,
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  dot: { width: 10, height: 10, borderRadius: "50%" },
  chromeTitle: {
    flex: 1,
    textAlign: "center",
    fontSize: 11,
    color: app.faint,
    fontFamily: fonts.sans,
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
  },
  headerTitle: {
    fontFamily: fonts.heading,
    fontWeight: 700,
    fontSize: 16,
    color: app.text,
  },
  createBtn: {
    fontSize: 11,
    padding: "6px 14px",
    borderRadius: 7,
    border: "none",
    background: "#1e293b",
    color: "#fff",
    fontWeight: 600,
    cursor: "default",
    display: "flex",
    alignItems: "center",
    gap: 4,
  },
  tab: {
    display: "flex",
    alignItems: "center",
    gap: 5,
    padding: "5px 12px",
    borderRadius: 6,
    fontSize: 11,
    cursor: "default",
  },
  tabCount: {
    fontSize: 9,
    padding: "1px 5px",
    borderRadius: 8,
    fontWeight: 600,
  },
  searchBar: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 12px",
    borderRadius: 8,
    border: `1px solid ${app.border}`,
    marginBottom: 16,
  },
  groupHeader: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 10px",
    borderRadius: 6,
    border: `1px solid ${app.border}`,
    cursor: "default",
  },
  notesGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 8,
    marginTop: 8,
    paddingLeft: 4,
  },
  noteCard: {
    borderRadius: 8,
    border: `1px solid ${app.border}`,
    overflow: "hidden",
    background: app.noteBg,
  },
  noteCardHeader: {
    padding: "4px 10px",
    background: app.noteHeader,
    borderBottom: `1px solid #e0e7ff`,
  },
  noteType: {
    fontSize: 9,
    fontWeight: 600,
    color: "#4f46e5",
  },
  noteTitle: {
    fontSize: 12,
    fontWeight: 700,
    color: app.text,
    marginBottom: 2,
  },
  noteCompany: { fontSize: 9, color: app.faint, marginBottom: 6 },
  noteBody: {
    fontSize: 10,
    color: app.muted,
    lineHeight: 1.5,
    marginBottom: 8,
  },
  tagRow: {
    display: "flex",
    gap: 3,
    flexWrap: "wrap",
    marginBottom: 6,
  },
  noteTag: {
    fontSize: 8,
    padding: "1px 5px",
    borderRadius: 3,
    fontWeight: 500,
  },
};
