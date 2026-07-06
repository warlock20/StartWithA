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

# Define the blueprint: 'checklists' is the name of this blueprint.
# template_folder='templates' will look for app/checklists/templates/
# url_prefix='/checklists' means all routes in this blueprint will start with /checklists
checklists_bp = Blueprint('checklists', __name__, template_folder='templates', url_prefix='/checklists')

from app.checklists import routes # Import routes after blueprint definition