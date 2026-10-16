from decimal import Decimal, InvalidOperation
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Budget, Category, Transaction
from app.utils.dates import local_today

bp = Blueprint("budgets", __name__, url_prefix="/budgets")


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    today = local_today()
    if request.method == "POST":
        try:
            category_id = int(request.form.get("category_id", ""))
            year = int(request.form.get("year", today.year))
            month = int(request.form.get("month", today.month))
            amount = Decimal(request.form.get("amount", ""))
            threshold = Decimal(request.form.get("warning_threshold", "80"))
        except (ValueError, InvalidOperation):
            abort(400)
        category = Category.query.filter_by(id=category_id, type="expense", is_active=True).first()
        if not category or not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99") or amount != amount.quantize(Decimal("0.01")) or not threshold.is_finite() or not 1 <= month <= 12 or not 2000 <= year <= 2200 or not Decimal("1") <= threshold <= Decimal("100"):
            abort(400)
        budget = Budget.query.filter_by(user_id=current_user.id, category_id=category_id, year=year, month=month).first()
        if budget is None:
            budget = Budget(user_id=current_user.id, category_id=category_id, year=year, month=month)
            db.session.add(budget)
        budget.amount, budget.warning_threshold = amount, threshold
        db.session.commit()
        flash("Budget saved.", "success")
        return redirect(url_for("budgets.index", year=year, month=month))

    try:
        year, month = int(request.args.get("year", today.year)), int(request.args.get("month", today.month))
    except ValueError:
        abort(400)
    if not 1 <= month <= 12 or not 2000 <= year <= 2200:
        abort(400)
    budgets = db.session.query(
        Budget, Category.name, func.coalesce(func.sum(Transaction.amount), 0)
    ).join(Category, Budget.category_id == Category.id).outerjoin(
        Transaction,
        (Transaction.user_id == Budget.user_id) & (Transaction.category_id == Budget.category_id)
        & (Transaction.type == "expense")
        & (Transaction.transaction_date >= date(year, month, 1))
        & (Transaction.transaction_date < date(year + (month == 12), 1 if month == 12 else month + 1, 1)),
    ).filter(Budget.user_id == current_user.id, Budget.year == year, Budget.month == month).group_by(Budget.id, Category.name).all()
    categories = Category.query.filter_by(type="expense", is_active=True).order_by(Category.name).all()
    return render_template("budgets/index.html", budgets=budgets, categories=categories, year=year, month=month)


@bp.post("/<int:budget_id>/delete")
@login_required
def delete(budget_id):
    budget = Budget.query.filter_by(id=budget_id, user_id=current_user.id).first_or_404()
    db.session.delete(budget)
    db.session.commit()
    flash("Budget deleted.", "info")
    return redirect(url_for("budgets.index", year=budget.year, month=budget.month))
