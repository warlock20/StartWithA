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
Utility functions for managing investor quotes
"""
import yaml
import random
from pathlib import Path
from flask import session


def load_quotes():
    """Load quotes from YAML file"""
    quotes_file = Path(__file__).parent.parent.parent / 'data' / 'investor_quotes.yaml'
    try:
        with open(quotes_file, 'r') as f:
            data = yaml.safe_load(f)
        return data.get('quotes', [])
    except FileNotFoundError:
        return []


def get_session_quote():
    """
    Get a quote for the current session.
    Uses session storage to ensure the same quote is shown throughout the session.
    """
    # Check if we already have a quote in the session
    if 'current_quote' not in session:
        quotes = load_quotes()
        if quotes:
            # Select a random quote and store it in session
            selected_quote = random.choice(quotes)
            session['current_quote'] = selected_quote
        else:
            session['current_quote'] = None

    return session.get('current_quote')


def clear_session_quote():
    """Clear the current session quote (useful for testing or manual refresh)"""
    if 'current_quote' in session:
        session.pop('current_quote')
