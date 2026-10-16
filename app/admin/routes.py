from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from app.extensions import db
from app.models import AuditLog, Transaction, User
from app.utils.audit import record_admin_action
from app.utils.dates import local_today
from app.utils.security import roles_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/")
@roles_required("admin")
def index():
    today = local_today()
    start = today.replace(day=1)
    active_users = User.query.filter_by(is_active=True).count()
    aggregates = db.session.query(
        Transaction.type, func.coalesce(func.sum(Transaction.amount), 0),
        func.count(Transaction.id),
    ).join(User, User.id == Transaction.user_id).filter(
        User.role == "user", User.is_active.is_(True),
        Transaction.transaction_date.between(start, today),
    ).group_by(Transaction.type).all()
    return render_template("admin/index.html", active_users=active_users, aggregates=aggregates)


@bp.get("/users")
@roles_required("admin")
def users():
    page_num = request.args.get("page", 1, type=int)
    if page_num < 1:
        abort(400)
    page = User.query.order_by(User.created_at.desc()).paginate(page=page_num, per_page=30, error_out=False)
    return render_template("admin/users.html", page=page)


@bp.post("/users/<int:user_id>/toggle")
@roles_required("admin")
def toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.role == "admin":
        flash("Administrator status cannot be changed here.", "warning")
    elif user.id == current_user.id:
        abort(400)
    else:
        user.is_active = not user.is_active
        record_admin_action("user.status_changed", "user", user.id, {"active": user.is_active})
        db.session.commit()
        flash("Account status updated.", "success")
    return redirect(url_for("admin.users"))


@bp.get("/audit")
@roles_required("admin")
def audit():
    entries = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return render_template("admin/audit.html", entries=entries)
