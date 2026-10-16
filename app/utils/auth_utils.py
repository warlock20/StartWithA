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
Authorization Utilities
Centralized authorization and access control helpers.
"""

import os

from flask_login import current_user

# Create a list of allowed emails in your Railway Variables
ALLOWED_USERS = os.environ.get('ALLOWED_USERS', '').split(',')

def is_authorized(email):
    # If ALLOWED_USERS is empty, everyone is allowed (dev mode)
    if not ALLOWED_USERS or ALLOWED_USERS == ['']:
        return True
    return email in ALLOWED_USERS


def owned_or_404(model_class, resource_id):
    """Fetch a resource owned by the current user, or abort with 404.

    A resource that exists but belongs to someone else also gets a 404, so
    responses don't reveal which IDs exist.

        company = owned_or_404(Company, company_id)
    """
    return model_class.query.filter_by(id=resource_id, user_id=current_user.id).first_or_404()
