/**
 * Research Templates
 * Pre-built frameworks and templates for investment research
 */

export const RESEARCH_TEMPLATES = {
  // Porter's Five Forces Analysis
  portersFiveForces: {
    name: "Porter's Five Forces",
    icon: "⚔️",
    category: "Strategic Analysis",
    description: "Analyze industry competition and attractiveness",
    blocks: [
      {
        type: "heading",
        props: { level: 2 },
        content: [{ type: "text", text: "Porter's Five Forces Analysis", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "1. Threat of New Entrants", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Barriers to entry (capital requirements, regulations, etc.)", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Economies of scale", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Brand loyalty and switching costs", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "2. Bargaining Power of Suppliers", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Supplier concentration", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Cost of switching suppliers", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "3. Bargaining Power of Buyers", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Customer concentration", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Price sensitivity", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "4. Threat of Substitutes", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Alternative products/services", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Relative price-performance", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "5. Industry Rivalry", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Number of competitors", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Industry growth rate", styles: {} }],
      },
    ],
  },

  // SWOT Analysis
  swotAnalysis: {
    name: "SWOT Analysis",
    icon: "🎯",
    category: "Strategic Analysis",
    description: "Evaluate Strengths, Weaknesses, Opportunities, and Threats",
    blocks: [
      {
        type: "heading",
        props: { level: 2 },
        content: [{ type: "text", text: "SWOT Analysis", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Strengths (Internal Positives)", styles: { bold: true } }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "What does the company do well?", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "What unique resources or capabilities?", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Weaknesses (Internal Negatives)", styles: { bold: true } }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "What could be improved?", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "What are the limitations?", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Opportunities (External Positives)", styles: { bold: true } }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "What market trends favor the company?", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "What gaps can the company fill?", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Threats (External Negatives)", styles: { bold: true } }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "What are the competitive threats?", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "What regulatory/economic risks?", styles: {} }],
      },
    ],
  },

  // Business Model Canvas
  businessModel: {
    name: "Business Model Canvas",
    icon: "🏗️",
    category: "Business Analysis",
    description: "Map out the business model comprehensively",
    blocks: [
      {
        type: "heading",
        props: { level: 2 },
        content: [{ type: "text", text: "Business Model Canvas", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Customer Segments", styles: {} }],
      },
      {
        type: "paragraph",
        content: [{ type: "text", text: "Who are the target customers?", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Value Propositions", styles: {} }],
      },
      {
        type: "paragraph",
        content: [{ type: "text", text: "What value is delivered to customers?", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Channels", styles: {} }],
      },
      {
        type: "paragraph",
        content: [{ type: "text", text: "How is value delivered?", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Revenue Streams", styles: {} }],
      },
      {
        type: "paragraph",
        content: [{ type: "text", text: "How does the company make money?", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Key Resources", styles: {} }],
      },
      {
        type: "paragraph",
        content: [{ type: "text", text: "What assets are required?", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Key Activities", styles: {} }],
      },
      {
        type: "paragraph",
        content: [{ type: "text", text: "What are the critical activities?", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Key Partnerships", styles: {} }],
      },
      {
        type: "paragraph",
        content: [{ type: "text", text: "Who are the strategic partners?", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Cost Structure", styles: {} }],
      },
      {
        type: "paragraph",
        content: [{ type: "text", text: "What are the main costs?", styles: {} }],
      },
    ],
  },

  // Investment Checklist
  investmentChecklist: {
    name: "Investment Checklist",
    icon: "✅",
    category: "Investment Decision",
    description: "Comprehensive pre-investment checklist",
    blocks: [
      {
        type: "heading",
        props: { level: 2 },
        content: [{ type: "text", text: "Investment Checklist", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Business Quality", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "[ ] Sustainable competitive advantage (moat)", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "[ ] Strong management team with aligned incentives", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "[ ] Predictable and growing revenue streams", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Financial Health", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "[ ] Strong balance sheet (low debt)", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "[ ] High return on capital (ROE, ROIC)", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "[ ] Consistent free cash flow generation", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Valuation", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "[ ] Trading at reasonable valuation vs. intrinsic value", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "[ ] Margin of safety built in", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Risk Assessment", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "[ ] Downside risks identified and acceptable", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "[ ] Regulatory and competitive risks understood", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Growth Potential", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "[ ] Clear growth drivers identified", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "[ ] Total addressable market (TAM) is large and growing", styles: {} }],
      },
    ],
  },

  // Earnings Call Notes
  earningsCallNotes: {
    name: "Earnings Call Notes",
    icon: "📞",
    category: "Research Notes",
    description: "Structured template for earnings call notes",
    blocks: [
      {
        type: "heading",
        props: { level: 2 },
        content: [{ type: "text", text: "Earnings Call Notes - [Company] Q[X] [Year]", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Key Financials", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Revenue: ", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "EPS: ", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Guidance: ", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Management Commentary", styles: {} }],
      },
      {
        type: "paragraph",
        content: [{ type: "text", text: "Key themes and insights from management...", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Q&A Highlights", styles: {} }],
      },
      {
        type: "paragraph",
        content: [{ type: "text", text: "Important questions and answers...", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "My Takeaways", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "What stood out?", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "What changed my thesis?", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Red flags or concerns?", styles: {} }],
      },
    ],
  },

  // Competitive Landscape
  competitiveLandscape: {
    name: "Competitive Landscape",
    icon: "🏁",
    category: "Market Analysis",
    description: "Map competitors and competitive positioning",
    blocks: [
      {
        type: "heading",
        props: { level: 2 },
        content: [{ type: "text", text: "Competitive Landscape", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Market Leader", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Company: ", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Market Share: ", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "Key Strengths: ", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Key Competitors", styles: {} }],
      },
      {
        type: "paragraph",
        content: [{ type: "text", text: "List and analyze 3-5 main competitors...", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Emerging Players", styles: {} }],
      },
      {
        type: "paragraph",
        content: [{ type: "text", text: "New entrants or disruptive competitors...", styles: {} }],
      },
      {
        type: "heading",
        props: { level: 3 },
        content: [{ type: "text", text: "Competitive Differentiation", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "How does our target company differentiate?", styles: {} }],
      },
      {
        type: "bulletListItem",
        content: [{ type: "text", text: "What is their defensible moat?", styles: {} }],
      },
    ],
  },
};

/**
 * Get all templates grouped by category
 */
export function getTemplatesByCategory() {
  const categories = {};

  Object.entries(RESEARCH_TEMPLATES).forEach(([key, template]) => {
    if (!categories[template.category]) {
      categories[template.category] = [];
    }
    categories[template.category].push({ key, ...template });
  });

  return categories;
}

/**
 * Insert template into editor
 */
export function insertTemplate(editor, templateKey) {
  const template = RESEARCH_TEMPLATES[templateKey];
  if (!template) return;

  // Insert all blocks from template
  template.blocks.forEach((block) => {
    editor.insertBlocks(
      [block],
      editor.getTextCursorPosition().block,
      "after"
    );
  });
}
