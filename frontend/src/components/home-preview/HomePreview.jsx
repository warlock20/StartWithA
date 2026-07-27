import { useState } from "react";
import { fonts } from "../../tokens";
import { SweepMockup } from "./SweepMockup";
import { ChecklistMockup } from "./ChecklistMockup";
import { ArgosMockup } from "./ArgosMockup";
import { KnowledgeMockup } from "./KnowledgeMockup";

const TABS = [
  {
    id: "sweep",
    label: "Start with the A's",
    icon: "🔤",
    desc: "Systematic market sweep — every company, one by one",
  },
  {
    id: "checklist",
    label: "Research Checklist",
    icon: "📋",
    desc: "Multi-step workflow with progress tracking and key findings",
  },
  {
    id: "argos",
    label: "Argos — AI Assistant",
    icon: "🛡️",
    desc: "Your personal research assistant — surfaces insights from your data, warns you, helps you improve",
  },
  {
    id: "knowledge",
    label: "Knowledge Hub",
    icon: "📚",
    desc: "Your research notes, curated wisdom, and decision journal",
  },
];

const MOCKUPS = [SweepMockup, ChecklistMockup, ArgosMockup, KnowledgeMockup];

/* Colors matching the "clean" public page theme */
const accent = "#2d6a4f";
const accentText = "#fff";
const textSecondary = "#475569";

export function HomePreview() {
  const [activeTab, setActiveTab] = useState(0);
  const ActiveMockup = MOCKUPS[activeTab];

  return (
    <div>
      {/* Tab bar */}
      <div style={styles.tabBar}>
        {TABS.map((tab, i) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(i)}
            style={{
              ...styles.tabBtn,
              background: activeTab === i ? accent : "#f5f5f5",
              color: activeTab === i ? accentText : textSecondary,
              boxShadow:
                activeTab === i ? `0 2px 12px ${accent}30` : "none",
            }}
          >
            <span style={{ display: "block", fontSize: "1.1rem", marginBottom: 2 }}>
              {tab.icon}
            </span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Active description */}
      <p style={styles.desc}>{TABS[activeTab].desc}</p>

      {/* Mockup */}
      <div style={{ transition: "opacity 0.3s", minHeight: 300 }}>
        <ActiveMockup />
      </div>
    </div>
  );
}

const styles = {
  tabBar: {
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: "0.5rem",
    marginBottom: "1.5rem",
  },
  tabBtn: {
    padding: "0.75rem 0.5rem",
    borderRadius: 10,
    border: "none",
    cursor: "pointer",
    fontFamily: fonts.sans,
    fontSize: "0.8rem",
    fontWeight: 600,
    transition: "all 0.25s",
    textAlign: "center",
    outline: "none",
  },
  desc: {
    textAlign: "center",
    fontFamily: fonts.sans,
    fontSize: "0.85rem",
    color: textSecondary,
    marginBottom: "1.5rem",
    minHeight: "1.2em",
    transition: "opacity 0.3s",
  },
};
