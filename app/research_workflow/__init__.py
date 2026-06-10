# Investment Checklist Platform
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

research_workflow_bp = Blueprint('research_workflow', __name__,
                                 template_folder='templates',
                                 url_prefix='/research/workflow')

# Import routes to register them with the blueprint
from app.research_workflow import (api_routes, template_routes, session_routes,
                                  project_workflow_routes, project_management_routes,
                                  project_data_routes, utility_routes, free_research_routes,
                                  argos_routes, bias_check_routes, companion_routes, checklist_check_routes,
                                  ai_research_assistant_routes, sweep_routes)
from . import export_routes  # noqa: F401
