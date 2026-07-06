# StartWithA
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
Sector Research Templates
Reusable templates for structured sector analysis using Quill.js
"""

RESEARCH_TEMPLATES = {
    'overview': {
        'name': 'Sector Overview',
        'icon': '📊',
        'description': 'Market size, growth rate, key segments, and regulatory environment',
        'content': """
<h2>📊 Sector Overview</h2>
<h3>Market Size & Growth</h3>
<ul>
    <li>Total addressable market: </li>
    <li>Historical growth rate: </li>
    <li>Projected growth: </li>
</ul>
<h3>Key Segments</h3>
<ul>
    <li>Segment 1: </li>
    <li>Segment 2: </li>
</ul>
<h3>Regulatory Environment</h3>
<p></p>
"""
    },

    'trends': {
        'name': 'Trends & Catalysts',
        'icon': '📈',
        'description': 'Secular trends, technological shifts, and growth drivers',
        'content': """
<h2>📈 Trends & Catalysts</h2>
<h3>Secular Trends</h3>
<ul>
    <li>Trend 1: </li>
    <li>Trend 2: </li>
</ul>
<h3>Technological Shifts</h3>
<p></p>
<h3>Regulatory Changes</h3>
<p></p>
<h3>Growth Drivers</h3>
<ul>
    <li></li>
</ul>
"""
    },

    'risks': {
        'name': 'Risks & Challenges',
        'icon': '⚠️',
        'description': 'Regulatory risks, cyclical factors, and headwinds',
        'content': """
<h2>⚠️ Risks & Challenges</h2>
<h3>Cyclical Factors</h3>
<p></p>
<h3>Regulatory Risks</h3>
<p></p>
<h3>Technological Disruption</h3>
<p></p>
<h3>Other Headwinds</h3>
<ul>
    <li></li>
</ul>
"""
    },

    'opportunities': {
        'name': 'Investment Opportunities',
        'icon': '💡',
        'description': 'Where to find alpha, key metrics, and evaluation criteria',
        'content': """
<h2>💡 Investment Opportunities</h2>
<h3>What Makes a Winner?</h3>
<ul>
    <li>Key success factor 1: </li>
    <li>Key success factor 2: </li>
</ul>
<h3>Key Metrics to Watch</h3>
<ul>
    <li>Metric 1: </li>
    <li>Metric 2: </li>
</ul>
<h3>Red Flags</h3>
<ul>
    <li></li>
</ul>
"""
    },

    'valuation': {
        'name': 'Valuation Framework',
        'icon': '💰',
        'description': 'Common multiples, DCF assumptions, and benchmarks',
        'content': """
<h2>💰 Valuation Framework</h2>
<h3>Common Multiples</h3>
<ul>
    <li>P/E range: </li>
    <li>EV/EBITDA: </li>
    <li>Other: </li>
</ul>
<h3>DCF Assumptions</h3>
<ul>
    <li>WACC: </li>
    <li>Terminal growth: </li>
</ul>
<h3>Peer Benchmarks</h3>
<p></p>
"""
    },

    'competitive_landscape': {
        'name': 'Competitive Landscape',
        'icon': '🏆',
        'description': 'Key players, market share, and competitive positioning',
        'content': """
<h2>🏆 Competitive Landscape</h2>
<h3>Market Leaders</h3>
<ul>
    <li>Company 1: Market share %, strengths</li>
    <li>Company 2: Market share %, strengths</li>
</ul>
<h3>Competitive Moats</h3>
<p></p>
<h3>Market Share Trends</h3>
<p></p>
"""
    },

    'swot': {
        'name': 'SWOT Analysis',
        'icon': '📋',
        'description': 'Strengths, Weaknesses, Opportunities, and Threats',
        'content': """
<h2>📋 SWOT Analysis</h2>
<h3>Strengths</h3>
<ul>
    <li></li>
</ul>
<h3>Weaknesses</h3>
<ul>
    <li></li>
</ul>
<h3>Opportunities</h3>
<ul>
    <li></li>
</ul>
<h3>Threats</h3>
<ul>
    <li></li>
</ul>
"""
    },

    'financial_analysis': {
        'name': 'Financial Analysis',
        'icon': '💵',
        'description': 'Revenue model, profitability, cash flow, and capital structure',
        'content': """
<h2>💵 Financial Analysis</h2>
<h3>Revenue Model</h3>
<ul>
    <li>Primary revenue streams: </li>
    <li>Business model: </li>
    <li>Revenue mix: </li>
</ul>
<h3>Profitability Metrics</h3>
<ul>
    <li>Gross margins: </li>
    <li>Operating margins: </li>
    <li>Net margins: </li>
</ul>
<h3>Cash Flow Characteristics</h3>
<p></p>
<h3>Capital Structure</h3>
<ul>
    <li>Debt levels: </li>
    <li>Interest coverage: </li>
</ul>
<h3>Valuation Metrics</h3>
<ul>
    <li>P/E ratio: </li>
    <li>EV/EBITDA: </li>
    <li>PEG ratio: </li>
</ul>
"""
    },

    'risk_assessment': {
        'name': 'Risk Assessment',
        'icon': '🛡️',
        'description': 'Market risks, operational risks, financial risks, and mitigation',
        'content': """
<h2>🛡️ Risk Assessment</h2>
<h3>Market Risks</h3>
<ul>
    <li>Demand volatility: </li>
    <li>Competitive pressure: </li>
    <li>Price sensitivity: </li>
</ul>
<h3>Operational Risks</h3>
<ul>
    <li>Supply chain vulnerabilities: </li>
    <li>Execution risk: </li>
    <li>Key person dependencies: </li>
</ul>
<h3>Financial Risks</h3>
<ul>
    <li>Leverage concerns: </li>
    <li>Liquidity issues: </li>
    <li>Currency exposure: </li>
</ul>
<h3>Mitigation Strategies</h3>
<p></p>
"""
    }
}


def get_template(template_key):
    """Get a specific template by key"""
    return RESEARCH_TEMPLATES.get(template_key)


def get_all_templates():
    """Get all available templates"""
    return RESEARCH_TEMPLATES


def get_template_list():
    """Get simplified list of templates for UI display"""
    return [
        {
            'key': key,
            'name': template['name'],
            'icon': template['icon'],
            'description': template['description']
        }
        for key, template in RESEARCH_TEMPLATES.items()
    ]
