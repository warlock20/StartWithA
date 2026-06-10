#!/usr/bin/env python3
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

"""Test session_history field on ResearchProject"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_research_project_has_session_history():
    """ResearchProject has session_history JSON field"""
    from app.models.research import ResearchProject
    assert hasattr(ResearchProject, 'session_history'), "Missing session_history field"
    print("PASS: ResearchProject has session_history")


def test_journal_entry_supports_capture():
    """JournalEntry has source_url for external captures"""
    from app.models.journal import JournalEntry
    assert hasattr(JournalEntry, 'source_url'), "Missing source_url field"
    assert hasattr(JournalEntry, 'source'), "Missing source field"
    assert hasattr(JournalEntry, 'project_id'), "Missing project_id field"
    print("PASS: JournalEntry supports external capture flow")


if __name__ == '__main__':
    test_research_project_has_session_history()
    test_journal_entry_supports_capture()
    print("\nAll model tests passed!")
