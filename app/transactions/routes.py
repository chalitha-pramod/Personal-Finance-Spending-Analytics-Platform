import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, jsonify, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Category, Reason, Transaction
from app.transactions.forms import TransactionForm
from app.utils.dates import local_today, parse_date

bp = Blueprint("transactions", __name__, url_prefix="/transactions")


def filtered_query(args, paginate=False):
    query = Transaction.query.filter(Transaction.user_id == current_user.id)
    start, end = parse_date(args.get("start")), parse_date(args.get("end"))
    if (args.get("start") and not start) or (args.get("end") and not end):
        abort(400)
    if start:
        query = query.filter(Transaction.transaction_date >= start)
    if end:
        query = query.filter(Transaction.transaction_date <= end)
    if start and end and start > end:
        abort(400)
    if args.get("type") and args["type"] not in {"income", "expense"}:
        abort(400)
    if args.get("type") in {"income", "expense"}:
        query = query.filter(Transaction.type == args["type"])
    for key, field in (("category_id", Transaction.category_id), ("reason_id", Transaction.reason_id)):
        if args.get(key):
            try:
                identifier = int(args[key])
            except ValueError:
                abort(400)
            if identifier <= 0:
                abort(400)
            query = query.filter(field == identifier)
    if args.get("search"):
        query = query.filter(Transaction.description.ilike(f"%{args['search'][:100]}%"))
    amounts = {}
    for key, op in (("min_amount", "min"), ("max_amount", "max")):
        if args.get(key):
            try:
                amount = Decimal(args[key])
            except (InvalidOperation, ValueError):
                abort(400)
            if not amount.is_finite() or amount < 0:
                abort(400)
            amounts[op] = amount
            query = query.filter(Transaction.amount >= amount if op == "min" else Transaction.amount <= amount)
    if amounts.get("min") is not None and amounts.get("max") is not None and amounts["min"] > amounts["max"]:
        abort(400)
    if args.get("sort") == "oldest":
        query = query.order_by(Transaction.transaction_date.asc(), Transaction.id.asc())
    elif args.get("sort") == "amount":
        query = query.order_by(Transaction.amount.desc(), Transaction.transaction_date.desc())
    else:
        query = query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
    query = query.options(joinedload(Transaction.category), joinedload(Transaction.reason))
    if paginate:
        try:
            page = max(1, int(args.get("page", 1)))
        except ValueError:
            abort(400)
        return query.paginate(page=page, per_page=25, error_out=False)
    return query


@bp.get("/")
@login_required
def index():
    page = filtered_query(request.args, paginate=True)
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    pagination_args = request.args.to_dict()
    pagination_args.pop("page", None)
    return render_template("transactions/index.html", page=page, categories=categories, pagination_args=pagination_args)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = TransactionForm()
    form.set_choices(form.type.data or "expense", form.category_id.data)
    if form.validate_on_submit():
        transaction = Transaction(
            user_id=current_user.id, type=form.type.data,
            category_id=form.category_id.data, reason_id=form.reason_id.data,
            amount=form.amount.data, transaction_date=form.transaction_date.data,
            description=form.description.data or None, payment_method=form.payment_method.data or None,
        )
        db.session.add(transaction)
        db.session.commit()
        flash("Transaction saved.", "success")
        return redirect(url_for("transactions.index"))
    return render_template("transactions/form.html", form=form, title="Add transaction")


@bp.route("/<int:transaction_id>/edit", methods=["GET", "POST"])
@login_required
def edit(transaction_id):
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    form = TransactionForm(obj=transaction)
    form.set_choices(form.type.data or transaction.type, form.category_id.data or transaction.category_id, existing=transaction)
    if form.validate_on_submit():
        transaction.type, transaction.category_id, transaction.reason_id = form.type.data, form.category_id.data, form.reason_id.data
        transaction.amount, transaction.transaction_date = form.amount.data, form.transaction_date.data
        transaction.description, transaction.payment_method = form.description.data or None, form.payment_method.data or None
        db.session.commit()
        flash("Transaction updated.", "success")
        return redirect(url_for("transactions.index"))
    return render_template("transactions/form.html", form=form, title="Edit transaction")


@bp.post("/<int:transaction_id>/delete")
@login_required
def delete(transaction_id):
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    db.session.delete(transaction)
    db.session.commit()
    flash("Transaction deleted.", "info")
    return redirect(url_for("transactions.index"))


@bp.get("/export.csv")
@login_required
def export_csv():
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Date", "Type", "Category", "Reason", "Amount", "Currency", "Description", "Payment method"])
    def safe_cell(value):
        text_value = "" if value is None else str(value)
        if text_value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
            return f"'{text_value}"
        return text_value

    for item in filtered_query(request.args).all():
        writer.writerow([item.transaction_date.isoformat(), item.type, safe_cell(item.category.name), safe_cell(item.reason.name),
                         f"{item.amount:.2f}", current_user.preferred_currency, safe_cell(item.description), safe_cell(item.payment_method)])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=transactions.csv"
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/api/reasons")
@login_required
def reasons_api():
    try:
        category_id = int(request.args.get("category_id", ""))
    except ValueError:
        return jsonify(error="A valid category_id is required."), 400
    kind = request.args.get("type")
    if kind not in {"income", "expense"}:
        return jsonify(error="A valid transaction type is required."), 400
    category = Category.query.filter_by(id=category_id, type=kind, is_active=True).first()
    if category is None:
        return jsonify(error="Category not found."), 404
    return jsonify(reasons=[{"id": r.id, "name": r.name} for r in Reason.query.filter_by(category_id=category_id, is_active=True).order_by(Reason.name).all()])
