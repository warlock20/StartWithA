import { fonts } from "../../tokens";

const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

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
};

export function SweepMockup() {
  return (
    <div style={styles.container}>
      {/* Window chrome */}
      <div style={styles.chrome}>
        <div style={{ display: "flex", gap: 6 }}>
          {["#ff5f57", "#febd2e", "#28c840"].map((c) => (
            <div key={c} style={{ ...styles.dot, background: c }} />
          ))}
        </div>
        <div style={styles.chromeTitle}>Start with A — DAX 40</div>
      </div>

      {/* App content */}
      <div style={styles.body}>
        {/* Header */}
        <div style={styles.header}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 18 }}>🇩🇪</span>
            <div>
              <div style={styles.headerTitle}>DAX 40 — Germany</div>
              <div style={{ fontSize: 11, color: app.muted }}>
                33 of 40 reviewed
              </div>
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={styles.headerPercent}>83%</div>
            <div style={{ fontSize: 10, color: app.faint }}>complete</div>
          </div>
        </div>

        {/* Progress bar */}
        <div style={styles.progressTrack}>
          <div style={styles.progressFill} />
        </div>

        {/* Alphabet strip */}
        <div style={styles.alphaStrip}>
          {LETTERS.map((l, i) => {
            const status = i < 4 ? "done" : i === 4 ? "active" : "pending";
            return (
              <div
                key={l}
                style={{
                  ...styles.alphaLetter,
                  background:
                    status === "done"
                      ? app.accent
                      : status === "active"
                        ? app.softGreen
                        : "#f3f4f6",
                  color:
                    status === "done"
                      ? "#fff"
                      : status === "active"
                        ? app.accent
                        : app.faint,
                  border:
                    status === "active"
                      ? `1.5px dashed ${app.accent}`
                      : "1.5px solid transparent",
                }}
              >
                {l}
              </div>
            );
          })}
        </div>

        {/* Focus + Queue */}
        <div style={{ display: "flex", gap: 14 }}>
          {/* Focus card */}
          <div style={styles.focusCard}>
            <div style={styles.focusIndex}>#12 of 40</div>
            <div style={styles.focusName}>E.ON SE</div>
            <div style={styles.focusTicker}>EOAN</div>
            <div style={styles.metaGrid}>
              {[
                { label: "Sector", value: "Utilities" },
                { label: "Market Cap", value: "€34.8B" },
              ].map((m) => (
                <div key={m.label} style={styles.metaCell}>
                  <div style={styles.metaLabel}>{m.label}</div>
                  <div style={styles.metaValue}>{m.value}</div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button style={styles.inboxBtn}>📥 Inbox</button>
              <button style={styles.killBtn}>✕ Kill</button>
            </div>
          </div>

          {/* Queue */}
          <div style={styles.queueCard}>
            <div style={styles.queueTitle}>Up Next</div>
            {["Fresenius SE", "Hannover Rück", "HeidelbergCement", "Henkel AG"].map(
              (name, i) => (
                <div
                  key={name}
                  style={{
                    ...styles.queueItem,
                    background: i === 0 ? app.softGreen : "transparent",
                    border:
                      i === 0
                        ? `1px solid ${app.softGreenBorder}`
                        : "1px solid transparent",
                    fontWeight: i === 0 ? 600 : 400,
                    color: i === 0 ? app.text : app.muted,
                  }}
                >
                  {name}
                </div>
              )
            )}
          </div>
        </div>

        {/* Session bar */}
        <div style={styles.sessionBar}>
          <span style={{ fontWeight: 600, color: app.accent }}>⚡ 28 min</span>
          <span style={styles.sessionDivider} />
          <span>
            <strong style={{ color: app.text }}>14</strong> reviewed
          </span>
          <span style={styles.sessionDivider} />
          <span style={{ color: "#059669" }}>
            <strong>2</strong> → inbox
          </span>
          <span style={styles.sessionDivider} />
          <span>
            <strong style={{ color: app.text }}>12</strong> killed
          </span>
          <span style={{ marginLeft: "auto", fontSize: 9, color: app.faint }}>
            Today's session
          </span>
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
  body: { padding: "18px 22px" },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
  },
  headerTitle: {
    fontFamily: fonts.heading,
    fontWeight: 700,
    fontSize: 15,
    color: app.text,
  },
  headerPercent: {
    fontFamily: fonts.heading,
    fontWeight: 800,
    fontSize: 24,
    color: app.accent,
    lineHeight: 1,
  },
  progressTrack: {
    height: 5,
    background: app.border,
    borderRadius: 3,
    marginBottom: 14,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    width: "83%",
    background: `linear-gradient(90deg, #475569, ${app.accent})`,
    borderRadius: 3,
  },
  alphaStrip: {
    display: "flex",
    gap: 2,
    marginBottom: 16,
    justifyContent: "center",
    flexWrap: "wrap",
  },
  alphaLetter: {
    width: 26,
    height: 26,
    borderRadius: 4,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 10,
    fontWeight: 700,
    fontFamily: fonts.mono,
  },
  focusCard: {
    flex: 1,
    background: app.cardBg,
    border: `1px solid ${app.border}`,
    borderRadius: 10,
    padding: 16,
  },
  focusIndex: {
    fontSize: 10,
    color: app.faint,
    fontFamily: fonts.mono,
    marginBottom: 10,
  },
  focusName: {
    fontFamily: fonts.heading,
    fontWeight: 700,
    fontSize: 17,
    color: app.text,
    marginBottom: 2,
  },
  focusTicker: {
    fontSize: 12,
    color: app.muted,
    fontFamily: fonts.mono,
    marginBottom: 14,
  },
  metaGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 6,
    marginBottom: 14,
  },
  metaCell: {
    padding: "6px 8px",
    background: app.softGreen,
    borderRadius: 5,
  },
  metaLabel: {
    fontSize: 8,
    color: app.faint,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  metaValue: {
    fontSize: 11,
    fontWeight: 600,
    color: app.text,
    marginTop: 1,
  },
  inboxBtn: {
    flex: 1,
    padding: "8px",
    borderRadius: 7,
    border: "1.5px solid #86efac",
    background: "#f0fdf4",
    color: "#15803d",
    fontWeight: 700,
    fontSize: 12,
    cursor: "default",
    fontFamily: fonts.sans,
  },
  killBtn: {
    flex: 1,
    padding: "8px",
    borderRadius: 7,
    border: "1.5px solid #fca5a5",
    background: "#fef2f2",
    color: "#b91c1c",
    fontWeight: 700,
    fontSize: 12,
    cursor: "default",
    fontFamily: fonts.sans,
  },
  queueCard: {
    width: 160,
    background: app.cardBg,
    border: `1px solid ${app.border}`,
    borderRadius: 10,
    padding: 12,
  },
  queueTitle: {
    fontSize: 9,
    fontWeight: 600,
    color: app.faint,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    marginBottom: 8,
  },
  queueItem: {
    padding: "5px 7px",
    borderRadius: 4,
    marginBottom: 2,
    fontSize: 11,
    fontFamily: fonts.sans,
  },
  sessionBar: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "8px 12px",
    marginTop: 12,
    background: app.softGreen,
    borderRadius: 7,
    border: `1px solid ${app.softGreenBorder}`,
    fontSize: 11,
    color: app.muted,
  },
  sessionDivider: {
    width: 1,
    height: 12,
    background: app.softGreenBorder,
  },
};
