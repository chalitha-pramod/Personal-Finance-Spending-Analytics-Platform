from datetime import datetime, timezone

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Category, Reason
from app.utils.audit import record_admin_action
from app.utils.security import roles_required

bp = Blueprint("categories", __name__, url_prefix="/admin/categories")


@bp.get("/api/categories")
@login_required
def categories_api():
    from flask_login import current_user
    if current_user.role not in {"admin", "user"}:
        return jsonify(error="Forbidden"), 403
    kind = request.args.get("type")
    if kind not in {"income", "expense"}:
        return jsonify(error="A valid transaction type is required."), 400
    categories = Category.query.filter_by(type=kind, is_active=True).order_by(Category.name).all()
    return jsonify(categories=[{"id": item.id, "name": item.name} for item in categories])


@bp.get("/")
@roles_required("admin")
def index():
    categories = Category.query.order_by(Category.type, Category.name).all()
    return render_template("admin/categories.html", categories=categories)


@bp.post("/create")
@roles_required("admin")
def create():
    name = request.form.get("name", "").strip()
    kind = request.form.get("type", "")
    if not name or len(name) > 80 or kind not in {"income", "expense"}:
        flash("Enter a valid category name and type.", "danger")
    elif Category.query.filter(func.lower(Category.name) == name.lower(), Category.type == kind).first():
        flash("That category already exists for this type.", "warning")
    else:
        category = Category(name=name, type=kind, is_active=True)
        db.session.add(category)
        db.session.flush()
        record_admin_action("category.created", "category", category.id, {"type": kind})
        db.session.commit()
        flash("Category created.", "success")
    return redirect(url_for("categories.index"))


@bp.post("/<int:category_id>/edit")
@roles_required("admin")
def edit(category_id):
    category = db.get_or_404(Category, category_id)
    name = request.form.get("name", "").strip()
    if not name or len(name) > 80:
        flash("Enter a valid category name.", "danger")
    elif Category.query.filter(Category.id != category.id, Category.type == category.type, func.lower(Category.name) == name.lower()).first():
        flash("That category already exists for this type.", "warning")
    else:
        category.name = name
        record_admin_action("category.renamed", "category", category.id)
        db.session.commit()
        flash("Category updated.", "success")
    return redirect(url_for("categories.index"))


@bp.post("/<int:category_id>/toggle")
@roles_required("admin")
def toggle(category_id):
    category = db.get_or_404(Category, category_id)
    if category.archived_at:
        flash("Archived categories cannot be reactivated.", "warning")
    else:
        category.is_active = not category.is_active
        record_admin_action("category.status_changed", "category", category.id, {"active": category.is_active})
        db.session.commit()
        flash("Category status updated.", "success")
    return redirect(url_for("categories.index"))


@bp.post("/<int:category_id>/archive")
@roles_required("admin")
def archive(category_id):
    category = db.get_or_404(Category, category_id)
    if category.archived_at:
        flash("Category is already archived.", "info")
    else:
        category.is_active = False
        category.archived_at = datetime.now(timezone.utc)
        for reason in category.reasons:
            reason.is_active = False
            reason.archived_at = category.archived_at
        record_admin_action("category.archived", "category", category.id)
        db.session.commit()
        flash("Category archived. Historical transaction links remain intact.", "success")
    return redirect(url_for("categories.index"))


@bp.post("/<int:category_id>/reasons")
@roles_required("admin")
def create_reason(category_id):
    category = db.get_or_404(Category, category_id)
    name = request.form.get("name", "").strip()
    if not name or len(name) > 100:
        flash("Enter a valid reason name.", "danger")
    elif Reason.query.filter(Reason.category_id == category.id, func.lower(Reason.name) == name.lower()).first():
        flash("That reason already exists in this category.", "warning")
    else:
        reason = Reason(category_id=category.id, name=name, is_active=True)
        db.session.add(reason)
        db.session.flush()
        record_admin_action("reason.created", "reason", reason.id, {"category_id": category.id})
        db.session.commit()
        flash("Reason created.", "success")
    return redirect(url_for("categories.index"))


@bp.post("/reasons/<int:reason_id>/edit")
@roles_required("admin")
def edit_reason(reason_id):
    reason = db.get_or_404(Reason, reason_id)
    name = request.form.get("name", "").strip()
    if not name or len(name) > 100:
        flash("Enter a valid reason name.", "danger")
    elif Reason.query.filter(Reason.id != reason.id, Reason.category_id == reason.category_id, func.lower(Reason.name) == name.lower()).first():
        flash("That reason already exists in this category.", "warning")
    else:
        reason.name = name
        record_admin_action("reason.renamed", "reason", reason.id)
        db.session.commit()
        flash("Reason updated.", "success")
    return redirect(url_for("categories.index"))


@bp.post("/reasons/<int:reason_id>/toggle")
@roles_required("admin")
def toggle_reason(reason_id):
    reason = db.get_or_404(Reason, reason_id)
    if reason.archived_at:
        flash("Archived reasons cannot be reactivated.", "warning")
    else:
        reason.is_active = not reason.is_active
        record_admin_action("reason.status_changed", "reason", reason.id, {"active": reason.is_active})
        db.session.commit()
        flash("Reason status updated.", "success")
    return redirect(url_for("categories.index"))


@bp.post("/reasons/<int:reason_id>/archive")
@roles_required("admin")
def archive_reason(reason_id):
    reason = db.get_or_404(Reason, reason_id)
    if reason.archived_at:
        flash("Reason is already archived.", "info")
    else:
        reason.is_active = False
        reason.archived_at = datetime.now(timezone.utc)
        record_admin_action("reason.archived", "reason", reason.id)
        db.session.commit()
        flash("Reason archived. Historical transaction links remain intact.", "success")
    return redirect(url_for("categories.index"))
