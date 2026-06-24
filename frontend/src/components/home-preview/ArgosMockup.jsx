import { fonts } from "../../tokens";

const app = {
  bg: "#fff",
  border: "#e5e7eb",
  text: "#111827",
  muted: "#6b7280",
  faint: "#9ca3af",
  accent: "#2d6a4f",
  aiBg: "#f0fdf4",
  aiBorder: "#dcfce7",
  warnBg: "#fffbeb",
  warnBorder: "#fde68a",
  infoBg: "#eff6ff",
  infoBorder: "#bfdbfe",
  successBg: "#f0fdf4",
  successBorder: "#dcfce7",
  dangerBg: "#fef2f2",
  dangerBorder: "#fecaca",
};

const TYPE_COLORS = {
  warn: { bg: app.warnBg, border: app.warnBorder, accent: "#d97706" },
  info: { bg: app.infoBg, border: app.infoBorder, accent: "#2563eb" },
  success: { bg: app.successBg, border: app.successBorder, accent: "#059669" },
  danger: { bg: app.dangerBg, border: app.dangerBorder, accent: "#dc2626" },
};

const INSIGHTS = [
  {
    type: "warn",
    icon: "⚠️",
    label: "Pattern Detected",
    title: "You may be chasing momentum again",
    body: "E.ON is up 38% in 6 months. Your last 3 \"inbox\" decisions were also high-momentum names — and 2 of them you later regretted. Your best picks historically were contrarian.",
    source: "Based on your decision journal (14 entries)",
  },
  {
    type: "info",
    icon: "📚",
    label: "From Your Knowledge Hub",
    title: "You wrote about this sector before",
    body: '"European utilities — energy transition tailwinds are real, but regulatory overhang is always underpriced. Focus on capital discipline." — your research note from Feb 2026.',
    source: "Knowledge Hub · Utilities tag",
  },
  {
    type: "success",
    icon: "✦",
    label: "Behavioral Insight",
    title: "Your hit rate improves when you slow down",
    body: "Companies where you spent 45+ minutes in research had a 3x better outcome than quick decisions. You've spent 8 minutes on E.ON so far.",
    source: "Across 127 decisions in your history",
  },
  {
    type: "danger",
    icon: "🔁",
    label: "Repeated Mistake",
    title: "You've killed similar companies before — then bought them later at higher prices",
    body: "RWE and Uniper were killed in your MDAX sweep, then added to watchlist 3 months later at 20%+ higher. Utility names match this pattern.",
    source: "Decision journal · Kill → Regret pattern",
  },
];

export function ArgosMockup() {
  return (
    <div style={styles.container}>
      {/* Window chrome */}
      <div style={styles.chrome}>
        <div style={{ display: "flex", gap: 6 }}>
          {["#ff5f57", "#febd2e", "#28c840"].map((c) => (
            <div key={c} style={{ ...styles.dot, background: c }} />
          ))}
        </div>
        <div style={styles.chromeTitle}>Argos — E.ON SE</div>
      </div>

      <div style={{ padding: "18px 22px" }}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.headerIcon}>🛡️</div>
          <div style={{ flex: 1 }}>
            <div style={styles.headerTitle}>Argos — Research Assistant</div>
            <div style={{ fontSize: 11, color: app.muted }}>
              Insights from your research history · E.ON SE
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={styles.insightCount}>4</div>
            <div style={{ fontSize: 9, color: app.faint }}>insights found</div>
          </div>
        </div>

        {/* Insight cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {INSIGHTS.map((ins, i) => {
            const tc = TYPE_COLORS[ins.type];
            return (
              <div
                key={i}
                style={{
                  padding: "12px 14px",
                  borderRadius: 10,
                  background: tc.bg,
                  border: `1px solid ${tc.border}`,
                }}
              >
                <div style={styles.insightHeader}>
                  <span style={{ fontSize: 12 }}>{ins.icon}</span>
                  <span style={{ ...styles.insightLabel, color: tc.accent }}>
                    {ins.label}
                  </span>
                </div>
                <div style={styles.insightTitle}>{ins.title}</div>
                <p style={styles.insightBody}>{ins.body}</p>
                <div style={styles.insightSource}>{ins.source}</div>
              </div>
            );
          })}
        </div>
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
    alignItems: "center",
    gap: 10,
    marginBottom: 16,
  },
  headerIcon: {
    width: 34,
    height: 34,
    borderRadius: 8,
    background: app.aiBg,
    border: `1px solid ${app.aiBorder}`,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 16,
  },
  headerTitle: {
    fontFamily: fonts.heading,
    fontWeight: 700,
    fontSize: 16,
    color: app.text,
  },
  insightCount: {
    fontFamily: fonts.heading,
    fontWeight: 800,
    fontSize: 22,
    color: "#d97706",
    lineHeight: 1,
  },
  insightHeader: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    marginBottom: 6,
  },
  insightLabel: {
    fontSize: 9,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  insightTitle: {
    fontSize: 12,
    fontWeight: 700,
    color: app.text,
    marginBottom: 4,
  },
  insightBody: {
    fontSize: 11,
    color: app.muted,
    lineHeight: 1.6,
    margin: "0 0 6px",
  },
  insightSource: {
    fontSize: 9,
    color: app.faint,
    fontStyle: "italic",
  },
};
