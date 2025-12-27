Add link to journal entries in Research workflow

## Navigation

- Fix smart back button circular navigation loops
  - Smart back button using HTTP Referer creates loops (A → B → A → B)
  - Options: Context-specific static buttons OR navigation stack with loop detection
  - Files: `app/utils/navigation_utils.py`, `app/templates/components/smart_back_button.html`
  - Address on-the-fly as issues are encountered

## Configuration

- Make timezone configurable per user or from environment variables (currently hardcoded to UTC+2 in `app/utils/time_utils.py:14`)
  - Add user timezone preference in profile settings
  - OR: Use environment variable for platform-wide timezone
  - Location: `app/utils/time_utils.py` line 13-14
