from calendar import monthrange
from datetime import date
from decimal import Decimal

from sqlalchemy import case, extract, func

from app.analytics.services import AGE_BANDS, age_band_expression
from app.extensions import db
from app.models import Category, Transaction, User

COMMUNITY_CURRENCIES = ("LKR", "USD", "EUR", "GBP")
COMMUNITY_PERIODS = (
    "this_month",
    "last_month",
    "last_3_months",
    "last_6_months",
    "this_year",
    "last_year",
    "custom",
)
COMMUNITY_INTERVALS = ("monthly", "yearly")
COMMUNITY_AGE_LABELS = {
    "18-24": "18–24",
    "25-34": "25–34",
    "35-44": "35–44",
    "45-54": "45–54",
    "55+": "55 and above",
}


def month_bounds(year, month):
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def resolve_period(period, today, start_value=None, end_value=None):
    if period not in COMMUNITY_PERIODS:
        raise ValueError("Select a valid reporting period.")
    if period == "custom":
        try:
            start, end = date.fromisoformat(start_value), date.fromisoformat(end_value)
        except (TypeError, ValueError):
            raise ValueError("Enter a valid custom date range.") from None
        if start > end or (end - start).days > 3660 or end > today:
            raise ValueError("The custom date range is invalid.")
        return start, end

    this_start, this_end = month_bounds(today.year, today.month)
    if period == "this_month":
        return this_start, min(today, this_end)
    if period == "last_month":
        last_year, last_month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
        return month_bounds(last_year, last_month)
    if period in {"last_3_months", "last_6_months"}:
        count = 3 if period == "last_3_months" else 6
        month_index = today.year * 12 + today.month - count
        year, month = divmod(month_index, 12)
        return date(year, month + 1, 1), min(today, this_end)
    if period == "this_year":
        return date(today.year, 1, 1), today
    return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)


def classify_age(date_of_birth, as_of):
    """Classify age on the current report date; unknown ages stay unclassified."""
    if date_of_birth is None:
        return "unknown"
    age = as_of.year - date_of_birth.year - (
        (as_of.month, as_of.day) < (date_of_birth.month, date_of_birth.day)
    )
    if age < 18:
        return "under-18"
    if age < 25:
        return "18-24"
    if age < 35:
        return "25-34"
    if age < 45:
        return "35-44"
    if age < 55:
        return "45-54"
    return "55+"


def _period_keys(start, end, interval):
    if interval == "yearly":
        return [str(year) for year in range(start.year, end.year + 1)]
    keys = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        keys.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return keys


def community_analytics(start, end, currency, interval, min_group_size, category_limit, as_of):
    """Build aggregate-only statistics for active adult contributors in one currency.

    A contributor is an active, non-administrator account with a recorded date of
    birth showing age 18+ and at least one transaction in the selected date range.
    Age averages divide each contributor's total by distinct contributors, not
    by transaction count. People with no transactions in the selected period are
    excluded from that period's denominators.
    """
    if currency not in COMMUNITY_CURRENCIES or interval not in COMMUNITY_INTERVALS:
        raise ValueError("Invalid community analytics filter.")

    age_bands = age_band_expression(as_of)
    eligible_user = db.session.query(User.id).filter(
        User.role == "user",
        User.is_active.is_(True),
        User.preferred_currency == currency,
        User.date_of_birth.is_not(None),
        User.date_of_birth <= as_of.replace(
            year=as_of.year - 18,
            day=min(as_of.day, monthrange(as_of.year - 18, as_of.month)[1]),
        ),
    )
    scoped_transactions = db.session.query(Transaction).join(
        User, User.id == Transaction.user_id
    ).filter(
        Transaction.user_id.in_(eligible_user),
        Transaction.transaction_date.between(start, end),
    )
    contributors = scoped_transactions.with_entities(Transaction.user_id).distinct().subquery()
    contributor_count = db.session.query(func.count()).select_from(contributors).scalar() or 0

    period_keys = _period_keys(start, end, interval)
    period_year = extract("year", Transaction.transaction_date)
    period_month = extract("month", Transaction.transaction_date)
    period_expression = (
        period_year
        if interval == "yearly"
        else period_year * 100 + period_month
    )
    period_rows = scoped_transactions.with_entities(
        period_expression.label("period_key"),
        func.sum(case((Transaction.type == "income", Transaction.amount), else_=0)).label("income"),
        func.sum(case((Transaction.type == "expense", Transaction.amount), else_=0)).label("expenses"),
        func.count(func.distinct(Transaction.user_id)).label("contributors"),
    ).group_by(period_expression).order_by(period_expression).all()
    period_totals = {}
    for row in period_rows:
        key = str(int(row.period_key)) if interval == "yearly" else f"{int(row.period_key) // 100:04d}-{int(row.period_key) % 100:02d}"
        period_totals[key] = row
    safe_periods = all(
        key in period_totals and period_totals[key].contributors >= min_group_size
        for key in period_keys
    )
    monthly = {
        "available": safe_periods,
        "points": [
            {
                "period": key,
                "income": float(period_totals[key].income or 0),
                "expenses": float(period_totals[key].expenses or 0),
            }
            for key in period_keys
        ] if safe_periods else [],
        "message": None if safe_periods else "Not enough community data to display this time series.",
    }

    user_totals = scoped_transactions.with_entities(
        Transaction.user_id.label("user_id"),
        age_bands.label("age_band"),
        func.sum(case((Transaction.type == "income", Transaction.amount), else_=0)).label("income"),
        func.sum(case((Transaction.type == "expense", Transaction.amount), else_=0)).label("expenses"),
    ).group_by(Transaction.user_id, age_bands).subquery()
    age_rows = db.session.query(
        user_totals.c.age_band,
        func.count().label("contributors"),
        func.avg(user_totals.c.income).label("average_income"),
        func.avg(user_totals.c.expenses).label("average_expenses"),
    ).group_by(user_totals.c.age_band).all()
    safe_age_rows = {
        row.age_band: row
        for row in age_rows
        if row.age_band in AGE_BANDS and row.contributors >= min_group_size
    }
    has_suppressed_age_groups = any(
        row.age_band in AGE_BANDS and row.contributors < min_group_size
        for row in age_rows
    )
    age_groups = [
        {
            "key": band,
            "label": COMMUNITY_AGE_LABELS[band],
            "average_income": float(safe_age_rows[band].average_income or 0),
            "average_expenses": float(safe_age_rows[band].average_expenses or 0),
        }
        for band in AGE_BANDS
        if band in safe_age_rows
    ]
    highest_spending = max(age_groups, key=lambda row: row["average_expenses"]) if age_groups else None
    lowest_spending = min(age_groups, key=lambda row: row["average_expenses"]) if age_groups else None
    highest_income = max(age_groups, key=lambda row: row["average_income"]) if age_groups else None
    lowest_income = min(age_groups, key=lambda row: row["average_income"]) if age_groups else None

    category_rows = scoped_transactions.join(
        Category, Category.id == Transaction.category_id
    ).filter(
        Transaction.type == "expense",
        Category.type == "expense",
    ).with_entities(
        Category.id.label("category_id"),
        Category.name.label("name"),
        func.sum(Transaction.amount).label("amount"),
        func.count(func.distinct(Transaction.user_id)).label("contributors"),
    ).group_by(Category.id, Category.name).order_by(func.sum(Transaction.amount).desc()).all()
    safe_categories = [
        row for row in category_rows if row.contributors >= min_group_size
    ]
    categories_safe = len(safe_categories) == len(category_rows) and bool(category_rows)
    category_total = sum((Decimal(str(row.amount or 0)) for row in safe_categories), Decimal("0"))
    categories = []
    if categories_safe:
        visible = safe_categories[:category_limit]
        categories = [
            {
                "name": row.name,
                "amount": float(row.amount or 0),
                "percentage": float((Decimal(str(row.amount or 0)) / category_total * 100) if category_total else 0),
            }
            for row in visible
        ]
        if len(safe_categories) > category_limit:
            other_amount = sum(
                (Decimal(str(row.amount or 0)) for row in safe_categories[category_limit:]),
                Decimal("0"),
            )
            categories.append({
                "name": "Other",
                "amount": float(other_amount),
                "percentage": float(other_amount / category_total * 100) if category_total else 0,
            })

    category_period_expression = period_year * 100 + period_month
    category_period_keys = _period_keys(start, end, "monthly")
    category_period_rows = scoped_transactions.join(
        Category, Category.id == Transaction.category_id
    ).filter(
        Transaction.type == "expense",
        Category.type == "expense",
    ).with_entities(
        Category.id.label("category_id"),
        Category.name.label("name"),
        category_period_expression.label("period_key"),
        func.sum(Transaction.amount).label("amount"),
        func.count(func.distinct(Transaction.user_id)).label("contributors"),
    ).group_by(Category.id, Category.name, category_period_expression).all()
    grouped_category_periods = {
        (row.category_id, f"{int(row.period_key) // 100:04d}-{int(row.period_key) % 100:02d}"): row
        for row in category_period_rows
    }
    category_trend_safe = categories_safe and all(
        row.contributors >= min_group_size
        for row in category_period_rows
    )
    category_trends = {"available": category_trend_safe, "labels": category_period_keys, "datasets": []}
    if category_trend_safe:
        trend_categories = safe_categories[:category_limit]
        for index, category in enumerate(trend_categories):
            category_trends["datasets"].append({
                "label": category.name,
                "data": [
                    float(grouped_category_periods[(category.category_id, key)].amount or 0)
                    if (category.category_id, key) in grouped_category_periods else 0
                    for key in category_period_keys
                ],
            })
        if len(safe_categories) > category_limit:
            other_ids = {row.category_id for row in safe_categories[category_limit:]}
            category_trends["datasets"].append({
                "label": "Other",
                "data": [
                    float(sum(
                        (Decimal(str(row.amount or 0)) for (category_id, period_key), row in grouped_category_periods.items()
                         if category_id in other_ids and period_key == key),
                        Decimal("0"),
                    ))
                    for key in category_period_keys
                ],
            })
    category_trends["message"] = (
        None if category_trend_safe
        else "Not enough community data to display monthly category patterns."
    )

    overview = {"available": contributor_count >= min_group_size and safe_periods}
    if overview["available"]:
        totals = scoped_transactions.with_entities(
            func.sum(case((Transaction.type == "income", Transaction.amount), else_=0)).label("income"),
            func.sum(case((Transaction.type == "expense", Transaction.amount), else_=0)).label("expenses"),
        ).one()
        income, expenses = Decimal(str(totals.income or 0)), Decimal(str(totals.expenses or 0))
        overview.update({
            "income": float(income),
            "expenses": float(expenses),
            "difference": float(income - expenses),
            "spending_ratio": float(expenses / income * 100) if income > 0 else None,
        })
        overview["message"] = None if income > 0 else "Spending-to-income ratio is not meaningful when recorded income is zero."
    else:
        overview.update({
            "income": None,
            "expenses": None,
            "difference": None,
            "spending_ratio": None,
            "message": "Not enough community data to display this overview.",
        })

    return {
        "currency": currency,
        "minimum_cohort_size": min_group_size,
        "eligibility": "Active non-administrator adults with a date of birth and at least one transaction in this period, using the selected preferred currency. Users with no transactions in the period are excluded from contributor averages.",
        "overview": overview,
        "categories": {
            "available": categories_safe,
            "items": categories if categories_safe else [],
            "message": None if categories_safe else "Not enough community data to display category spending.",
        },
        "age_groups": {
            "available": bool(age_groups),
            "items": age_groups,
            "has_suppressed_groups": has_suppressed_age_groups,
            "highest_spending": highest_spending["label"] if highest_spending else None,
            "lowest_spending": lowest_spending["label"] if lowest_spending else None,
            "highest_income": highest_income["label"] if highest_income else None,
            "lowest_income": lowest_income["label"] if lowest_income else None,
            "message": None if age_groups else "Not enough community data to display age-group comparisons.",
        },
        "trends": monthly,
        "category_trends": category_trends,
        "period": {"start": start.isoformat(), "end": end.isoformat(), "interval": interval},
    }
