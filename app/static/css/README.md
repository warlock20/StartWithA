# CSS Architecture Documentation

## Overview

The platform uses a **modular CSS architecture** with a single entry point (`design-system.css`) that imports specialized modules.

## File Structure

```
css/
├── design-system.css          # Main entry point (imports all modules)
├── design-system-backup.css   # Backup of original monolithic file
├── modules/                   # Modular CSS components
│   ├── _variables.css         # CSS custom properties (colors, spacing, typography)
│   ├── _base.css              # Global base styles, typography, layout
│   ├── _buttons.css           # Basic button styles
│   ├── _forms.css             # Form control styles
│   ├── _tables.css            # Table styling
│   ├── _alerts.css            # Alert & message boxes
│   ├── _cards.css             # Base card components
│   ├── _navigation.css        # Navbar, dropdowns, navigation
│   ├── _utilities.css         # Utility classes, loader, timeline
│   ├── _public-home.css       # Public homepage styles
│   ├── _dashboard.css         # Dashboard components (placeholder)
│   ├── _projects.css          # Research projects (placeholder)
│   ├── _sector-analysis.css   # Sector analysis (placeholder)
│   └── _idea-pipeline.css     # Idea pipeline (placeholder)
```

## How It Works

1. **Single Import**: HTML templates import only `design-system.css`
2. **CSS @import**: `design-system.css` loads all modules using `@import url('modules/_file.css')`
3. **No Build Step**: Pure CSS, no preprocessor required
4. **Modular Organization**: Each module handles a specific concern

## Current State

### ✅ Fully Modularized (766 lines across 10 modules)
- CSS Variables
- Base styles
- Basic buttons
- Forms
- Tables
- Alerts
- Basic cards
- Navigation
- Utilities
- Public homepage (partial)

### ⚠️ Partially Modularized (~4,000 lines in main file)
The following sections are still in `design-system.css`:
- **Professional Custom Button System** (lines 220-530)
  - Advanced button variants (platform-primary, platform-secondary, etc.)
  - Button states and animations
  - Icon buttons

- **Professional Card System** (lines 48-220, 531-1192)
  - Pro cards, framework cards
  - Dashboard-specific cards
  - Sector/Idea cards

- **Modern Dashboard Components** (lines 1193+)
  - Dashboard grids and layouts
  - Research project cards
  - Status indicators
  - Complex interactive components

### 📋 Identified Duplicates

**Known Issue**: The `.btn` class is defined in 3 places:
1. `modules/_buttons.css` - Basic button styling (✅ Keep)
2. `design-system.css:224` - Professional button system base (🔄 Needs consolidation)
3. `design-system.css:801` - Button enhancements (🔄 Needs consolidation)

## Next Steps to Complete Modularization

### Phase 1: Consolidate Button Styles
```bash
# Move lines 220-530 from design-system.css to:
modules/_button-system.css    # Advanced button variants
```

### Phase 2: Extract Dashboard Components
```bash
# Move to specialized modules:
modules/_dashboard.css         # Dashboard grids, stats, widgets
modules/_projects.css          # Project cards and layouts
modules/_sector-analysis.css   # Sector notebook components
modules/_idea-pipeline.css     # Idea cards and pipeline
```

### Phase 3: Extract Page-Specific Styles
Create page-specific modules for:
- `_question-bank.css`
- `_destination-analysis.css`
- `_too-hard-projects.css`

## Benefits of Current Architecture

✅ **Maintainability**: Edit specific modules (50-150 lines) instead of 6,000+ line file
✅ **Organization**: Logical separation by component type
✅ **No Breaking Changes**: All existing styles still work
✅ **Progressive Enhancement**: Can modularize incrementally
✅ **Easy Debugging**: Find styles by module name

## Usage Guide

### Adding New Styles

1. **For new variables**: Add to `modules/_variables.css`
2. **For new buttons**: Add to `modules/_buttons.css` or create `_button-system.css`
3. **For new components**: Create a new module file
4. **Import the module**: Add `@import url('modules/_your-module.css');` to `design-system.css`

### Editing Existing Styles

1. **Check if modularized**: Look in `modules/` directory first
2. **If in modules**: Edit the specific module file
3. **If in main file**: Edit `design-system.css` (lines after imports)
4. **Consider extracting**: If editing frequently, extract to a module

### Finding Styles

```bash
# Search across all modules
grep -r "class-name" modules/

# Search in main file
grep -n "class-name" design-system.css

# List all modules
ls -lh modules/
```

## Performance Notes

- **HTTP/2**: Modern browsers load parallel @imports efficiently
- **Caching**: Individual modules can be cached separately
- **File Size**: Total size unchanged, just reorganized
- **Load Time**: Minimal impact with HTTP/2

## Migration from Old System

The original monolithic file is saved as `design-system-backup.css` for reference.

To revert (if needed):
```bash
mv design-system.css design-system-modular.css
mv design-system-backup.css design-system.css
```

## Contributing

When adding new styles:
1. Check if a relevant module exists
2. If yes, add to existing module
3. If no, create a new module file with `_module-name.css` naming
4. Import it in `design-system.css`
5. Document the module purpose at the top of the file
