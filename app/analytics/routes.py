from datetime import date

from flask import Blueprint, abort, current_app, jsonify, render_template, request
from sqlalchemy import func

from app.models import Category
from app.utils.dates import local_today, parse_date
from app.utils.security import roles_required
from app.analytics.services import AGE_BANDS, admin_analytics

bp = Blueprint("analytics", __name__, url_prefix="/admin/analytics")


def filters():
    today = local_today()
    start = parse_date(request.args.get("start")) or today.replace(day=1)
    end = parse_date(request.args.get("end")) or today
    if start > end or (end - start).days > 366:
        abort(400)
    band = request.args.get("age_group") or None
    if band and band not in AGE_BANDS:
        abort(400)
    category_arg = request.args.get("category_id")
    category_id = request.args.get("category_id", type=int)
    if category_arg and (category_id is None or category_id <= 0):
        abort(400)
    currency = request.args.get("currency", "LKR")
    if currency not in {"LKR", "USD", "EUR", "GBP"}:
        abort(400)
    return start, end, band, category_id, currency


@bp.get("/")
@roles_required("admin")
def index():
    start, end, band, category_id, currency = filters()
    data = admin_analytics(start, end, current_app.config["ADMIN_ANALYTICS_MIN_GROUP_SIZE"], currency, band, category_id)
    categories = Category.query.filter_by(type="expense").order_by(Category.name).all()
    return render_template("admin/analytics.html", data=data, start=start, end=end, band=band, category_id=category_id, currency=currency, categories=categories)


@bp.get("/api/data")
@roles_required("admin")
def data():
    start, end, band, category_id, currency = filters()
    result = admin_analytics(start, end, current_app.config["ADMIN_ANALYTICS_MIN_GROUP_SIZE"], currency, band, category_id)
    result["disclaimer"] = "Registered participating users only; results may not represent the wider population."
    return jsonify(result)
