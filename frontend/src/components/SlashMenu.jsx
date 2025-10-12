import React from "react";
import { getDefaultReactSlashMenuItems } from "@blocknote/react";
import { RESEARCH_TEMPLATES, insertTemplate } from "./ResearchTemplates";

/**
 * Custom Slash Menu Items for Investment Research
 * Organized by category with beautiful icons
 */

// Category definitions
const CATEGORIES = {
  BASIC: { name: "Basic", icon: "📝", color: "#64748b" },
  RESEARCH: { name: "Research", icon: "🔬", color: "#3b82f6" },
  FINANCIAL: { name: "Financial", icon: "💰", color: "#10b981" },
  ANALYSIS: { name: "Analysis", icon: "📊", color: "#8b5cf6" },
  MEDIA: { name: "Media", icon: "🎬", color: "#f59e0b" },
  TEMPLATES: { name: "Templates", icon: "📋", color: "#ec4899" },
};

/**
 * Get custom slash menu items
 * @param {object} editor - BlockNote editor instance
 */
export function getCustomSlashMenuItems(editor) {
  // Get default items (heading, paragraph, lists, etc.)
  const defaultItems = getDefaultReactSlashMenuItems(editor);

  // Custom research blocks
  const researchItems = [
    {
      title: "Citation",
      onItemClick: () => {
        editor.insertBlocks(
          [
            {
              type: "citation",
              props: {
                source: "",
                url: "",
                accessDate: new Date().toISOString().split("T")[0],
              },
            },
          ],
          editor.getTextCursorPosition().block,
          "after"
        );
      },
      aliases: ["cite", "source", "reference", "citation"],
      group: CATEGORIES.RESEARCH.name,
      icon: "📚",
      subtext: "Add a research citation",
    },
    {
      title: "Company Mention",
      onItemClick: () => {
        editor.insertBlocks(
          [
            {
              type: "companyMention",
              props: { companyName: "", ticker: "", companyId: "" },
            },
          ],
          editor.getTextCursorPosition().block,
          "after"
        );
      },
      aliases: ["company", "stock", "ticker", "mention"],
      group: CATEGORIES.RESEARCH.name,
      icon: "🏢",
      subtext: "Tag a company",
    },
    {
      title: "Highlight",
      onItemClick: () => {
        editor.insertBlocks(
          [
            {
              type: "highlight",
              props: { color: "yellow", importance: "normal" },
            },
          ],
          editor.getTextCursorPosition().block,
          "after"
        );
      },
      aliases: ["highlight", "important", "note", "callout"],
      group: CATEGORIES.RESEARCH.name,
      icon: "⭐",
      subtext: "Highlight key insight",
    },
  ];

  // Financial analysis blocks
  const financialItems = [
    {
      title: "Financial Metrics",
      onItemClick: () => {
        editor.insertBlocks(
          [
            {
              type: "financialMetrics",
              props: {
                companyName: "",
                revenue: "",
                revenueGrowth: "",
                netIncome: "",
                netMargin: "",
                pe: "",
                ps: "",
                debtToEquity: "",
                roe: "",
              },
            },
          ],
          editor.getTextCursorPosition().block,
          "after"
        );
      },
      aliases: ["metrics", "financial", "kpi", "stats", "numbers"],
      group: CATEGORIES.FINANCIAL.name,
      icon: "💰",
      subtext: "Key financial metrics card",
    },
    {
      title: "Data Table",
      onItemClick: () => {
        editor.insertBlocks(
          [
            {
              type: "dataTable",
              props: {
                title: "",
                headers: JSON.stringify(["Metric", "2023", "2024"]),
                rows: JSON.stringify([
                  ["Revenue", "", ""],
                  ["Growth %", "", ""],
                ]),
                columnTypes: JSON.stringify(["text", "currency", "currency"]),
              },
            },
          ],
          editor.getTextCursorPosition().block,
          "after"
        );
      },
      aliases: ["table", "data", "spreadsheet", "grid", "chart"],
      group: CATEGORIES.FINANCIAL.name,
      icon: "📊",
      subtext: "Sortable data table with charts",
    },
    {
      title: "Investment Thesis",
      onItemClick: () => {
        editor.insertBlocks(
          [
            {
              type: "thesis",
              props: {
                title: "",
                bullCase: "",
                bearCase: "",
                baseCase: "",
              },
            },
          ],
          editor.getTextCursorPosition().block,
          "after"
        );
      },
      aliases: ["thesis", "bull", "bear", "case", "analysis"],
      group: CATEGORIES.ANALYSIS.name,
      icon: "💭",
      subtext: "Bull/Bear case analysis",
    },
  ];

  // Research templates
  const templateItems = Object.entries(RESEARCH_TEMPLATES).map(([key, template]) => ({
    title: template.name,
    onItemClick: () => insertTemplate(editor, key),
    aliases: [template.name.toLowerCase(), "template", "framework"],
    group: CATEGORIES.TEMPLATES.name,
    icon: template.icon,
    subtext: template.description,
  }));

  // Media and embeds
  const mediaItems = [
    {
      title: "Embed",
      onItemClick: () => {
        editor.insertBlocks(
          [
            {
              type: "embed",
              props: { url: "", embedType: "auto", caption: "" },
            },
          ],
          editor.getTextCursorPosition().block,
          "after"
        );
      },
      aliases: [
        "embed",
        "youtube",
        "video",
        "twitter",
        "chart",
        "iframe",
        "tradingview",
      ],
      group: CATEGORIES.MEDIA.name,
      icon: "🎬",
      subtext: "Embed video, tweet, or chart",
    },
    {
      title: "Image",
      onItemClick: () => {
        editor.insertBlocks(
          [{ type: "image" }],
          editor.getTextCursorPosition().block,
          "after"
        );
      },
      aliases: ["image", "img", "picture", "photo"],
      group: CATEGORIES.MEDIA.name,
      icon: "🖼️",
      subtext: "Upload an image",
    },
  ];

  // Combine all items
  return [
    ...defaultItems.map((item) => ({
      ...item,
      group: item.group || CATEGORIES.BASIC.name,
    })),
    ...researchItems,
    ...financialItems,
    ...templateItems,
    ...mediaItems,
  ];
}

/**
 * Custom Slash Menu Item Renderer
 * Renders items with beautiful icons and styling
 */
export function SlashMenuItem(props) {
  const { item, onClick } = props;

  // Get category info
  const categoryInfo = Object.values(CATEGORIES).find(
    (cat) => cat.name === item.group
  );
  const categoryColor = categoryInfo?.color || "#64748b";

  return (
    <div
      className="bn-slash-menu-item"
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "12px",
        padding: "8px 12px",
        borderRadius: "6px",
        transition: "all 0.2s",
        cursor: "pointer",
      }}
    >
      {/* Icon */}
      <div
        style={{
          fontSize: "20px",
          width: "28px",
          height: "28px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: `${categoryColor}15`,
          borderRadius: "6px",
        }}
      >
        {item.icon || "📄"}
      </div>

      {/* Content */}
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: "14px",
            fontWeight: 600,
            color: "#1e293b",
            marginBottom: "2px",
          }}
        >
          {item.title}
        </div>
        {item.subtext && (
          <div
            style={{
              fontSize: "12px",
              color: "#64748b",
            }}
          >
            {item.subtext}
          </div>
        )}
      </div>

      {/* Category badge */}
      {item.group && (
        <div
          style={{
            fontSize: "10px",
            fontWeight: 600,
            color: categoryColor,
            backgroundColor: `${categoryColor}15`,
            padding: "2px 8px",
            borderRadius: "4px",
            textTransform: "uppercase",
          }}
        >
          {item.group}
        </div>
      )}
    </div>
  );
}
