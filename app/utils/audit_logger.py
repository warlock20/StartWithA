"""
GDPR Audit Logger — Art. 5(2) Accountability

Structured audit trail for security-sensitive actions:
- AI calls (consent, provider, token usage)
- Data exports (GDPR Art. 15)
- Account deletions (GDPR Art. 17)
- Consent changes (GDPR Art. 7)
- Authentication events

Writes to a dedicated 'audit' logger so entries can be routed
to a separate log file or log aggregator in production.
"""

import json
import logging

from flask import request
from app.utils.time_utils import now_utc

audit_logger = logging.getLogger('audit')


def _base_entry(user_id, action):
    """Build the common audit entry structure."""
    return {
        'timestamp': now_utc().isoformat(),
        'user_id': user_id,
        'action': action,
        'ip': request.remote_addr if request else None,
    }


def log_ai_call(user_id, provider, model, task_type, tokens_used=None, success=True):
    """Log an AI provider call."""
    entry = _base_entry(user_id, 'ai_call')
    entry.update({
        'provider': provider,
        'model': model,
        'task_type': task_type,
        'tokens_used': tokens_used,
        'success': success,
    })
    audit_logger.info(json.dumps(entry))


def log_data_export(user_id):
    """Log a GDPR data export (Art. 15)."""
    entry = _base_entry(user_id, 'data_export')
    audit_logger.info(json.dumps(entry))


def log_account_deletion(user_id):
    """Log an account deletion (Art. 17)."""
    entry = _base_entry(user_id, 'account_deletion')
    audit_logger.info(json.dumps(entry))


def log_consent_change(user_id, consent_type, granted):
    """Log a consent grant or revocation (Art. 7)."""
    entry = _base_entry(user_id, 'consent_change')
    entry.update({
        'consent_type': consent_type,
        'granted': granted,
    })
    audit_logger.info(json.dumps(entry))


def log_auth_event(user_id, event_type):
    """Log authentication events (login, logout, failed_login)."""
    entry = _base_entry(user_id, 'auth')
    entry['event_type'] = event_type
    audit_logger.info(json.dumps(entry))
