from flask import Blueprint, abort, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app.community.services import (
    COMMUNITY_CURRENCIES,
    COMMUNITY_INTERVALS,
    COMMUNITY_PERIODS,
    community_analytics,
    resolve_period,
)
from app.utils.dates import local_today

bp = Blueprint("community", __name__, url_prefix="/community")


def selected_filters():
    period = request.args.get("period", "this_month")
    interval = request.args.get("interval", "monthly")
    currency = request.args.get("currency", current_user.preferred_currency)
    if period not in COMMUNITY_PERIODS or interval not in COMMUNITY_INTERVALS:
        abort(400)
    if currency not in COMMUNITY_CURRENCIES:
        abort(400)
    try:
        start, end = resolve_period(
            period,
            local_today(),
            request.args.get("start"),
            request.args.get("end"),
        )
    except ValueError:
        abort(400)
    return {
        "start": start,
        "end": end,
        "period": period,
        "interval": interval,
        "currency": currency,
    }


def analytics_for(filters):
    return community_analytics(
        filters["start"],
        filters["end"],
        filters["currency"],
        filters["interval"],
        current_app.config["COMMUNITY_ANALYTICS_MIN_GROUP_SIZE"],
        current_app.config["COMMUNITY_ANALYTICS_CATEGORY_LIMIT"],
        local_today(),
    )


@bp.get("/")
@login_required
def index():
    filters = selected_filters()
    return render_template(
        "community/index.html",
        filters=filters,
        currencies=COMMUNITY_CURRENCIES,
        today=local_today(),
    )


@bp.get("/api/data")
@login_required
def data():
    filters = selected_filters()
    response = jsonify(analytics_for(filters))
    response.headers["Cache-Control"] = "private, no-store"
    return response
