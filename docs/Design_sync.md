# Design Sync - Page Cohesion Rules

## Global Rules
- All pages use the same font, text sizes, and spacing from our CSS constants
- All pages default to Group 1 unless explicitly listed in another group
- Unified header: semantic `<header class="dashboard-header">` + `dashboard-container` everywhere
- Title: `dashboard-title font-poppins` + `dashboard-subtitle` (consistent naming)

## Unified Header Pattern
- **Base**: 2-column top row (title+subtitle left, action buttons right)
- **Optional**: `dashboard-metrics-strip` row below for pages needing KPIs (portfolio, analytics)
- Portfolio pages must migrate from `portfolio-page-header` to this unified pattern

## Group 1: Main Platform Pages (Default)
Standard dashboard layout with header + content sections.
- /ideas/inbox
- /research/workflow/my-projects
- /analytics/dashboard
- /portfolio/ (with metrics strip)
- /portfolio/position/<id> (with metrics strip)
- /portfolio/intelligence (with metrics strip)
- All other pages not listed elsewhere

## Group 2: Action/Focused Pages
Centered card layout, editorial style, single-task focus. This pages as mentioned in single-task focus. We can remove the backbutton, i.e., smart back button from the right top and use the cancel button to direct back smartly (i.e., the logic of smart button)

- /ideas/add
- /ideas/<id>/promote
- /ideas/<id>/kill
- /portfolio/transaction/add
- portfolio/position/<id>/thesis/new
- journal/entry/new
- learning/mistakes/new
- learning/weekly-review

## Group 3: Public/Marketing Pages
Editorial layout, no dashboard header, premium typography-first design.
Warm off-white background, slate + forest green palette.
No navigation dots, no emoji icons, no gradient text.

- / (landing page)
- /mental-models (product walkthrough)
- /auth/login
