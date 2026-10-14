# Project Instructions for Claude Code

## License Header (AGPL-3.0)

Every new `.py` file MUST start with this license header:

```python
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
```

This is enforced by CI — PRs will fail without it.

## Authorship

Never add Claude as an author or co-author of anything that goes to the repository or GitHub:

- Commits are authored and committed as `Kiran Mathews <kiranmathews20@gmail.com>`. Set `git config user.name "Kiran Mathews"` and `git config user.email "kiranmathews20@gmail.com"` before committing.
- No `Co-Authored-By: Claude`, `Claude-Session:` or similar trailers in commit messages.
- No "Generated with Claude Code" lines, claude.ai session links or other Claude attribution in PR titles, PR descriptions, issues or comments. If a tool appends one automatically, edit it out afterwards.
