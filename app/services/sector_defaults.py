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

# app/services/sector_defaults.py

from app import db
from app.models import Sector
from app.utils.time_utils import now_utc


# Default sectors to seed for new users
DEFAULT_SECTORS = [
    {
        'name': 'Software as a Service',
        'display_name': 'SaaS',
        'slug': 'saas',
        'category': 'technology',
        'description': 'Cloud-based software delivered via subscription model',
        'aliases': ['SaaS', 'Software-as-a-Service', 'Cloud Software'],
        'key_characteristics': [
            'Recurring revenue',
            'High gross margins (70%+)',
            'Network effects',
            'Low marginal costs',
            'Scalability'
        ],
        'typical_metrics': {
            'revenue': ['ARR', 'MRR', 'ARR Growth Rate', 'Net Dollar Retention'],
            'retention': ['Gross Revenue Retention', 'Churn Rate', 'Customer Retention'],
            'efficiency': ['CAC Payback Period', 'LTV/CAC Ratio', 'Rule of 40', 'Magic Number'],
            'engagement': ['DAU/MAU', 'Activation Rate', 'Feature Adoption']
        },
        'icon': None,
        'color': '#3498db'
    },
    {
        'name': 'Financial Technology',
        'display_name': 'FinTech',
        'slug': 'fintech',
        'category': 'finance',
        'description': 'Technology-enabled financial services and payment processing',
        'aliases': ['FinTech', 'Financial Tech', 'Banking Tech', 'PayTech'],
        'key_characteristics': [
            'Regulatory complexity',
            'Network effects',
            'Transaction-based revenue',
            'Capital requirements',
            'Trust and security critical'
        ],
        'typical_metrics': {
            'volume': ['Transaction Volume', 'GMV', 'TPV', 'Payment Volume'],
            'monetization': ['Take Rate', 'ARPU', 'Revenue per Transaction'],
            'efficiency': ['CAC', 'Payback Period', 'Operating Leverage'],
            'risk': ['Fraud Rate', 'Charge-back Rate', 'Default Rate']
        },
        'icon': None,
        'color': '#2ecc71'
    },
    {
        'name': 'Healthcare Technology',
        'display_name': 'HealthTech',
        'slug': 'healthtech',
        'category': 'healthcare',
        'description': 'Technology solutions for healthcare delivery and management',
        'aliases': ['HealthTech', 'Health Tech', 'Medical Technology', 'Digital Health'],
        'key_characteristics': [
            'Heavy regulation (FDA, HIPAA)',
            'Long sales cycles',
            'Mission critical systems',
            'Complex stakeholders',
            'Clinical validation required'
        ],
        'typical_metrics': {
            'adoption': ['Provider Adoption', 'Patient Engagement', 'Active Users'],
            'outcomes': ['Clinical Outcomes', 'Cost Savings', 'Time Savings'],
            'revenue': ['Revenue per Provider', 'Contract Value', 'Lives Covered']
        },
        'icon': None,
        'color': '#e74c3c'
    },
    {
        'name': 'E-Commerce',
        'display_name': 'E-Commerce',
        'slug': 'ecommerce',
        'category': 'consumer',
        'description': 'Online retail and marketplace platforms',
        'aliases': ['E-Commerce', 'eCommerce', 'Online Retail', 'Digital Commerce'],
        'key_characteristics': [
            'Marketplace dynamics',
            'Logistics complexity',
            'Low gross margins',
            'Scale advantages',
            'Customer acquisition focus'
        ],
        'typical_metrics': {
            'volume': ['GMV', 'Order Volume', 'AOV', 'Units Sold'],
            'efficiency': ['CAC', 'Fulfillment Cost', 'Contribution Margin', 'Take Rate'],
            'retention': ['Repeat Purchase Rate', 'Cohort LTV', 'Customer Lifetime Value'],
            'conversion': ['Conversion Rate', 'Cart Abandonment', 'Browse-to-Purchase']
        },
        'icon': None,
        'color': '#f39c12'
    },
    {
        'name': 'Consumer Internet',
        'display_name': 'Consumer Internet',
        'slug': 'consumer-internet',
        'category': 'consumer',
        'description': 'Consumer-facing internet platforms and social applications',
        'aliases': ['Consumer Tech', 'Consumer Apps', 'Social Media', 'Social Networks'],
        'key_characteristics': [
            'Network effects',
            'Ad-based monetization',
            'Viral growth potential',
            'Engagement focused',
            'Winner-take-most dynamics'
        ],
        'typical_metrics': {
            'engagement': ['DAU', 'MAU', 'DAU/MAU Ratio', 'Time Spent', 'Sessions per User'],
            'monetization': ['ARPU', 'ARPPU', 'Ad Revenue per User', 'CPM'],
            'growth': ['User Growth Rate', 'Viral Coefficient', 'K-Factor'],
            'content': ['Content Creation Rate', 'UGC Volume', 'Engagement Rate']
        },
        'icon': None,
        'color': '#9b59b6'
    },
    {
        'name': 'Enterprise Software',
        'display_name': 'Enterprise Software',
        'slug': 'enterprise-software',
        'category': 'technology',
        'description': 'Business-focused software for large organizations',
        'aliases': ['Enterprise Software', 'B2B Software', 'Business Software'],
        'key_characteristics': [
            'Long sales cycles',
            'High contract values',
            'Sticky customers',
            'Complex implementations',
            'Multi-year contracts'
        ],
        'typical_metrics': {
            'revenue': ['ARR', 'ACV', 'TCV', 'Expansion Revenue'],
            'retention': ['Dollar-based Net Retention', 'Logo Retention', 'Churn'],
            'sales': ['Sales Cycle Length', 'Win Rate', 'Pipeline Coverage'],
            'efficiency': ['CAC Payback', 'S&M as % of Revenue', 'LTV/CAC']
        },
        'icon': None,
        'color': '#34495e'
    },
    {
        'name': 'Artificial Intelligence',
        'display_name': 'AI & ML',
        'slug': 'ai-ml',
        'category': 'technology',
        'description': 'Artificial intelligence and machine learning platforms',
        'aliases': ['AI', 'ML', 'Machine Learning', 'Artificial Intelligence', 'AI/ML'],
        'key_characteristics': [
            'Data moats',
            'Compute intensive',
            'Model performance critical',
            'Integration complexity',
            'Rapid innovation'
        ],
        'typical_metrics': {
            'performance': ['Model Accuracy', 'Inference Time', 'Training Time'],
            'usage': ['API Calls', 'Tokens Processed', 'Queries per Second'],
            'efficiency': ['Cost per Inference', 'GPU Utilization', 'Compute Costs'],
            'revenue': ['Revenue per API Call', 'Seat Licenses', 'Usage-based Revenue']
        },
        'icon': None,
        'color': '#16a085'
    },
    {
        'name': 'Cybersecurity',
        'display_name': 'Cybersecurity',
        'slug': 'cybersecurity',
        'category': 'technology',
        'description': 'Security software and services',
        'aliases': ['Cybersecurity', 'InfoSec', 'Security Software', 'Cyber Defense'],
        'key_characteristics': [
            'Mission critical',
            'High switching costs',
            'Compliance driven',
            'Continuous evolution',
            'Zero-day threats'
        ],
        'typical_metrics': {
            'effectiveness': ['Threat Detection Rate', 'False Positive Rate', 'MTTD', 'MTTR'],
            'revenue': ['ARR', 'Seat Count', 'Device Count'],
            'retention': ['Net Revenue Retention', 'Renewal Rate', 'Expansion Revenue'],
            'coverage': ['Endpoints Protected', 'Network Coverage', 'Cloud Workloads']
        },
        'icon': None,
        'color': '#c0392b'
    },
    {
        'name': 'Cloud Infrastructure',
        'display_name': 'Cloud Infrastructure',
        'slug': 'cloud-infrastructure',
        'category': 'technology',
        'description': 'Cloud computing and infrastructure services',
        'aliases': ['Cloud', 'IaaS', 'PaaS', 'Cloud Computing', 'Infrastructure'],
        'key_characteristics': [
            'Capital intensive',
            'Economies of scale',
            'Network effects',
            'Multi-tenant architecture',
            'Pay-as-you-go model'
        ],
        'typical_metrics': {
            'usage': ['Compute Hours', 'Storage GB', 'API Calls', 'Bandwidth'],
            'revenue': ['Revenue per Customer', 'Consumption Revenue', 'Reserved Instances'],
            'efficiency': ['Server Utilization', 'Gross Margin', 'COGS per GB'],
            'growth': ['New Customer Adds', 'Expansion Rate', 'Usage Growth']
        },
        'icon': None,
        'color': '#7f8c8d'
    },
    {
        'name': 'Semiconductors',
        'display_name': 'Semiconductors',
        'slug': 'semiconductors',
        'category': 'technology',
        'description': 'Chip design and manufacturing',
        'aliases': ['Chips', 'Semiconductors', 'Silicon', 'IC Design'],
        'key_characteristics': [
            'Capital intensive',
            'Cyclical industry',
            'Long development cycles',
            'Intellectual property critical',
            'Fab vs fabless models'
        ],
        'typical_metrics': {
            'production': ['Wafer Starts', 'Yield Rate', 'Die per Wafer', 'Capacity Utilization'],
            'financial': ['ASP', 'Gross Margin', 'R&D as % Revenue', 'Capex Intensity'],
            'market': ['Market Share', 'Design Wins', 'Socket Count'],
            'technology': ['Process Node', 'Transistor Count', 'Performance per Watt']
        },
        'icon': None,
        'color': '#2c3e50'
    }
]


def seed_default_sectors(user_id):
    """
    Create default sectors for a new user.

    Args:
        user_id: User ID to create sectors for

    Returns:
        List of created Sector objects
    """
    sectors = []

    for sector_data in DEFAULT_SECTORS:
        # Check if sector already exists
        existing = Sector.query.filter_by(
            user_id=user_id,
            slug=sector_data['slug']
        ).first()

        if existing:
            continue  # Skip if already exists

        sector = Sector(
            user_id=user_id,
            name=sector_data['name'],
            display_name=sector_data['display_name'],
            slug=sector_data['slug'],
            category=sector_data.get('category'),
            description=sector_data.get('description'),
            key_characteristics=sector_data.get('key_characteristics'),
            typical_metrics=sector_data.get('typical_metrics'),
            aliases=sector_data.get('aliases'),
            icon=sector_data.get('icon'),
            color=sector_data.get('color'),
            is_default=True
        )
        sectors.append(sector)

    if sectors:
        db.session.bulk_save_objects(sectors)
        db.session.commit()

    return sectors


def get_default_sector_names():
    """
    Get list of default sector names.

    Returns:
        List of sector display names
    """
    return [sector['display_name'] for sector in DEFAULT_SECTORS]


def get_default_sector_by_slug(slug):
    """
    Get default sector configuration by slug.

    Args:
        slug: Sector slug

    Returns:
        Dict with sector configuration or None
    """
    for sector in DEFAULT_SECTORS:
        if sector['slug'] == slug:
            return sector
    return None
