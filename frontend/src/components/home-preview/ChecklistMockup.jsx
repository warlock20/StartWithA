import { fonts } from "../../tokens";

const app = {
  bg: "#fff",
  border: "#e5e7eb",
  text: "#111827",
  muted: "#6b7280",
  faint: "#9ca3af",
  cardBg: "#fff",
  softGreen: "#f0fdf4",
  softGreenBorder: "#dcfce7",
  accent: "#2d6a4f",
  softRed: "#fef2f2",
  softRedBorder: "#fecaca",
  softAmber: "#fffbeb",
  softAmberBorder: "#fde68a",
};

const STEPS = [
  { label: "Free Research", status: "done", time: "30615 min" },
  { label: "Checklist", status: "active", time: "Est: 60 min" },
  { label: "Investment Thesis", status: "pending", time: "" },
];

const VITALS = [
  { label: "Status", value: "In Progress", color: "#3b82f6" },
  { label: "Progress", value: "33.3%", bar: true },
  { label: "Time Spent", value: "607.8 hrs", color: app.accent },
  { label: "Days Since Work", value: "4d", color: undefined },
];

export function ChecklistMockup() {
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
          Siemens AG — Research Checklist
        </div>
      </div>

      <div style={{ display: "flex" }}>
        {/* Main content */}
        <div style={{ flex: 1, padding: "18px 22px" }}>
          {/* Header */}
          <div style={{ marginBottom: 16 }}>
            <div style={styles.frameworkLabel}>Value Investing Framework</div>
            <div style={styles.companyName}>Siemens AG</div>
            <div style={styles.companyTicker}>SIE · Industrials</div>
          </div>

          {/* Workflow steps */}
          <div style={styles.workflowTitle}>Project Workflow</div>
          {STEPS.map((step, i) => (
            <div
              key={i}
              style={{
                ...styles.stepRow,
                background: step.status === "active" ? app.softGreen : "transparent",
                border:
                  step.status === "active"
                    ? `1.5px dashed ${app.accent}`
                    : "1.5px solid transparent",
              }}
            >
              <div
                style={{
                  ...styles.stepDot,
                  background:
                    step.status === "done"
                      ? app.accent
                      : step.status === "active"
                        ? app.softGreen
                        : app.border,
                  border:
                    step.status === "active"
                      ? `2px solid ${app.accent}`
                      : "none",
                }}
              >
                {step.status === "done" ? "✓" : ""}
              </div>
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: step.status === "active" ? 700 : 500,
                    color: app.text,
                  }}
                >
                  {step.status === "active" && (
                    <span style={styles.currentLabel}>Current Step</span>
                  )}
                  {step.label}
                </div>
                {step.time && (
                  <div style={{ fontSize: 9, color: app.faint }}>{step.time}</div>
                )}
              </div>
              {step.status === "done" && (
                <div style={{ display: "flex", gap: 4 }}>
                  <span style={styles.chip}>Notes</span>
                  <span style={styles.chip}>Revisit</span>
                </div>
              )}
              {step.status === "active" && (
                <button style={styles.continueBtn}>Continue →</button>
              )}
            </div>
          ))}
        </div>

        {/* Sidebar */}
        <div style={styles.sidebar}>
          <div style={styles.sidebarTitle}>Project Vitals</div>
          {VITALS.map((item, i) => (
            <div
              key={i}
              style={{
                marginBottom: 8,
                paddingBottom: 8,
                borderBottom:
                  i < 3 ? `1px solid ${app.border}` : "none",
              }}
            >
              <div style={styles.vitalRow}>
                <span style={{ fontSize: 10, color: app.muted }}>
                  {item.label}
                </span>
                {item.value === "In Progress" ? (
                  <span style={styles.statusBadge}>{item.value}</span>
                ) : (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: item.color || app.text,
                    }}
                  >
                    {item.value}
                  </span>
                )}
              </div>
              {item.bar && (
                <div style={styles.vitalBar}>
                  <div style={styles.vitalBarFill} />
                </div>
              )}
            </div>
          ))}

          {/* Key Findings */}
          <div style={{ ...styles.sidebarTitle, marginTop: 6 }}>
            Key Findings
          </div>
          <div style={styles.greenFlag}>
            <span style={{ fontWeight: 600, color: "#059669" }}>
              Green Flag:{" "}
            </span>
            <span style={{ color: app.muted }}>Strong moat</span>
          </div>
          <div style={styles.redFlag}>
            <span style={{ fontWeight: 600, color: "#dc2626" }}>
              Red Flag:{" "}
            </span>
            <span style={{ color: app.muted }}>Capital allocation</span>
          </div>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            <span style={styles.tagGreen}>+ Green</span>
            <span style={styles.tagRed}>+ Red</span>
            <span style={styles.tagAmber}>⚠ Must Exit</span>
          </div>
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
  frameworkLabel: {
    fontSize: 9,
    fontWeight: 600,
    color: app.accent,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    marginBottom: 4,
  },
  companyName: {
    fontFamily: fonts.heading,
    fontWeight: 700,
    fontSize: 16,
    color: app.text,
  },
  companyTicker: {
    fontSize: 11,
    color: app.muted,
    fontFamily: fonts.mono,
  },
  workflowTitle: {
    fontSize: 10,
    fontWeight: 600,
    color: app.text,
    marginBottom: 10,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  },
  stepRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "8px 10px",
    marginBottom: 4,
    borderRadius: 8,
  },
  stepDot: {
    width: 18,
    height: 18,
    borderRadius: "50%",
    flexShrink: 0,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#fff",
    fontSize: 9,
  },
  currentLabel: {
    fontSize: 8,
    color: app.accent,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    display: "block",
    marginBottom: 1,
  },
  chip: {
    fontSize: 9,
    padding: "2px 6px",
    borderRadius: 4,
    border: `1px solid ${app.border}`,
    color: app.muted,
  },
  continueBtn: {
    fontSize: 11,
    padding: "5px 12px",
    borderRadius: 6,
    border: "none",
    background: app.accent,
    color: "#fff",
    fontWeight: 600,
    cursor: "default",
  },
  sidebar: {
    width: 210,
    borderLeft: `1px solid ${app.border}`,
    padding: "16px 14px",
    background: "#fafbfc",
  },
  sidebarTitle: {
    fontSize: 12,
    fontWeight: 700,
    color: app.text,
    marginBottom: 10,
  },
  vitalRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  statusBadge: {
    fontSize: 8,
    padding: "1px 6px",
    borderRadius: 3,
    background: "#3b82f6",
    color: "#fff",
    fontWeight: 600,
  },
  vitalBar: {
    height: 3,
    background: app.border,
    borderRadius: 2,
    marginTop: 4,
    overflow: "hidden",
  },
  vitalBarFill: {
    height: "100%",
    width: "33%",
    background: "#3b82f6",
    borderRadius: 2,
  },
  greenFlag: {
    padding: "5px 7px",
    borderRadius: 5,
    background: app.softGreen,
    border: `1px solid ${app.softGreenBorder}`,
    marginBottom: 4,
    fontSize: 10,
  },
  redFlag: {
    padding: "5px 7px",
    borderRadius: 5,
    background: app.softRed,
    border: `1px solid ${app.softRedBorder}`,
    marginBottom: 8,
    fontSize: 10,
  },
  tagGreen: {
    fontSize: 8,
    padding: "3px 6px",
    borderRadius: 4,
    background: "#f0fdf4",
    border: "1px solid #dcfce7",
    color: "#15803d",
    fontWeight: 600,
  },
  tagRed: {
    fontSize: 8,
    padding: "3px 6px",
    borderRadius: 4,
    background: "#fef2f2",
    border: "1px solid #fecaca",
    color: "#dc2626",
    fontWeight: 600,
  },
  tagAmber: {
    fontSize: 8,
    padding: "3px 6px",
    borderRadius: 4,
    background: app.softAmber,
    border: `1px solid ${app.softAmberBorder}`,
    color: "#d97706",
    fontWeight: 600,
  },
};
