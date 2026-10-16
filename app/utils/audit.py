from flask_login import current_user

from app.extensions import db
from app.models import AuditLog


def record_admin_action(action, target_type, target_id=None, details=None):
    actor_id = current_user.id if current_user.is_authenticated else None
    db.session.add(AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=details or {},
    ))
