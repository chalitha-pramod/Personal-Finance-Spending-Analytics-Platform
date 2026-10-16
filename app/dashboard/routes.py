from datetime import date, timedelta
from decimal import Decimal

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from app.dashboard.services import dashboard_summary, report_summary
from app.extensions import db
from app.models import Transaction
from app.utils.dates import local_today, month_bounds, parse_date

bp = Blueprint("dashboard", __name__)


def selected_range():
    today = local_today()
    period = request.args.get("period", "month")
    if period == "today":
        return today, today, "today"
    if period == "year":
        return date(today.year, 1, 1), date(today.year, 12, 31), "year"
    if period == "custom":
        start, end = parse_date(request.args.get("start")), parse_date(request.args.get("end"))
        if not start or not end or start > end or (end - start).days > 366:
            abort(400)
        return start, end, "custom"
    if period != "month":
        abort(400)
    start, end = month_bounds(today.year, today.month)
    return start, end, "month"


@bp.get("/")
@login_required
def index():
    start, end, period = selected_range()
    summary = dashboard_summary(current_user.id, start, end)
    return render_template("dashboard/index.html", summary=summary, start=start, end=end, period=period)


@bp.get("/api/chart-data")
@login_required
def chart_data():
    start, end, _ = selected_range()
    summary = dashboard_summary(current_user.id, start, end)
    return jsonify(
        labels=[day["date"] for day in summary["days"]],
        income=[day["income"] for day in summary["days"]],
        expenses=[day["expense"] for day in summary["days"]],
        category_labels=[row["name"] for row in summary["categories"]],
        category_values=[row["amount"] for row in summary["categories"]],
        reason_labels=[row["name"] for row in summary["reasons"]],
        reason_values=[row["amount"] for row in summary["reasons"]],
        currency=current_user.preferred_currency,
    )


@bp.get("/reports")
@login_required
def reports():
    today = local_today()
    start_arg, end_arg = request.args.get("start"), request.args.get("end")
    start = parse_date(start_arg) if start_arg else month_bounds(today.year, today.month)[0]
    end = parse_date(end_arg) if end_arg else today
    grouping = request.args.get("grouping", "day")
    if not start or not end or start > end or (end - start).days > 3660 or grouping not in {"day", "month", "year"}:
        abort(400)
    report = report_summary(current_user.id, start, end, grouping)
    income = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == current_user.id, Transaction.type == "income",
        Transaction.transaction_date.between(start, end),
    ).scalar()
    expenses = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == current_user.id, Transaction.type == "expense",
        Transaction.transaction_date.between(start, end),
    ).scalar()
    previous_start, previous_end = start - (end - start + timedelta(days=1)), start - timedelta(days=1)
    previous = db.session.query(
        Transaction.type, func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date.between(previous_start, previous_end),
    ).group_by(Transaction.type).all()
    previous_totals = dict(previous)
    previous_income = Decimal(str(previous_totals.get("income", 0)))
    previous_expenses = Decimal(str(previous_totals.get("expense", 0)))
    return render_template(
        "dashboard/reports.html", start=start, end=end, grouping=grouping, report=report,
        income=Decimal(str(income)), expenses=Decimal(str(expenses)),
        savings_rate=(Decimal(str(income - expenses)) / Decimal(str(income)) * 100) if income > 0 else None,
        previous_income=previous_income, previous_expenses=previous_expenses,
        expense_change=(Decimal(str(expenses - previous_expenses)) / previous_expenses * 100) if previous_expenses > 0 else None,
    )
