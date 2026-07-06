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

from flask import Blueprint

# Define the blueprint: 'auth' is the name of this blueprint.
# __name__ helps Flask locate the blueprint.
# template_folder='templates' tells this blueprint to look for its templates
# in a subfolder named 'templates' WITHIN the blueprint's directory (i.e., app/auth/templates/)
# We'll use a URL prefix to avoid route name collisions and organize URLs.
auth_bp = Blueprint('auth', __name__, template_folder='templates', url_prefix='/auth')

from app.auth import routes  # Import routes after blueprint definition to avoid circular imports
from app.auth import auth0_routes  # Import Auth0 routes to register them with the blueprint
from app.auth import gdpr_routes  # GDPR data export & account deletion