"""
Navigation Utilities

Provides smart back navigation that remembers where users came from
and returns them to the appropriate context.
"""

from flask import request, url_for, session as flask_session
from urllib.parse import urlparse


def get_smart_return_url(default_route=None, default_kwargs=None):
    """
    Determine the smart return URL based on where the user came from.

    Checks in order:
    1. Explicit 'next' parameter in URL
    2. HTTP Referer header
    3. Default route provided

    Args:
        default_route: Flask route name to use as fallback (e.g., 'companies.list_companies')
        default_kwargs: Dict of kwargs for the default route

    Returns:
        tuple: (return_url, context_label)
            - return_url: The URL to return to
            - context_label: Human-readable label (e.g., "Research", "Companies")
    """
    # Check for explicit next parameter
    return_url = request.args.get('next')
    if return_url:
        context_label = _get_context_label(return_url)
        return return_url, context_label

    # Check HTTP Referer header first (most accurate source indicator)
    referer = request.headers.get('Referer')
    if referer:
        parsed = urlparse(referer)
        path = parsed.path

        # Research project - use specific labels
        if '/research/workflow/projects/' in path:
            if '/summary' in path:
                return path, "Research Summary"
            elif '/execute/' in path:
                return path, "Research Step"
            else:
                return path, "Research"

        # Research session/checklist (updated to new routing)
        if '/research/checklist/' in path or '/research/session/' in path:
            return path, "Checklist"

        # Sector analysis
        if '/sectors/' in path and '/analysis/' in path:
            return path, "Sector Analysis"

        # Companies dashboard
        if '/companies' in path and '/documents' not in path:
            return path, "Companies"

        # Ideas/Pipeline
        if '/ideas/' in path:
            return path, "Ideas"

        # Learning center
        if '/learning/' in path:
            return path, "Learning"

        # Journal
        if '/journal/' in path:
            return path, "Journal"

        # Analytics
        if '/analytics' in path:
            return path, "Analytics"

    # Fallback: check for research workflow context in Flask session
    # (only used when no Referer and no explicit 'next' param are available)
    research_context = flask_session.get('research_context')
    if research_context and research_context.get('project_id'):
        project_id = research_context.get('project_id')
        return_url = url_for('research_workflow.project_dashboard', project_id=project_id)
        return return_url, "Research"

    # Default fallback
    if default_route:
        if default_kwargs:
            return url_for(default_route, **default_kwargs), "Back"
        return url_for(default_route), "Back"

    # Ultimate fallback to dashboard
    return url_for('main.index'), "Dashboard"


def _get_context_label(path):
    """
    Get human-readable label from a path.

    Args:
        path: URL path

    Returns:
        str: Context label
    """
    if '/research/workflow/projects/' in path:
        # Be more specific for different research workflow pages
        if '/summary' in path:
            return "Research Summary"
        elif '/execute/' in path:
            return "Research Step"
        else:
            return "Research"
    elif '/research/checklist/' in path or '/research/session/' in path:
        return "Checklist"
    elif '/sectors/' in path:
        return "Sector Analysis"
    elif '/companies' in path:
        return "Companies"
    elif '/ideas/' in path:
        return "Ideas"
    elif '/learning/' in path:
        return "Learning"
    elif '/journal/' in path:
        return "Journal"
    elif '/analytics' in path:
        return "Analytics"
    else:
        return "Previous Page"


def get_return_url_with_label(default_route=None, default_kwargs=None):
    """
    Convenience method that returns URL and label separately.

    Returns:
        tuple: (url, label)
    """
    return get_smart_return_url(default_route, default_kwargs)
