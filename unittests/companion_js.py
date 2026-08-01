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

"""Shared helper for the companion's static JS contract checks.

The companion is several modules that all extend one ``window.CompanionChat``.
The contract tests care that a behaviour exists, not which module holds it, so
they read the modules as one text — moving a method between them is a refactor,
not a behaviour change, and shouldn't turn a suite red.
"""

import glob
import os

JS_DIR = os.path.join(os.path.dirname(__file__), '..', 'app/static/js/companion')


def module_paths():
    """Every companion module, in a stable order."""
    return sorted(glob.glob(os.path.join(JS_DIR, '*.js')))


def companion_js():
    """All companion modules concatenated."""
    return '\n'.join(
        open(path, encoding='utf-8').read() for path in module_paths())
