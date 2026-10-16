from datetime import date

from sqlalchemy import and_, case, func

from app.extensions import db
from app.models import Category, Transaction, User


AGE_BANDS = ("18-24", "25-34", "35-44", "45-54", "55+")


def age_band_expression(as_of):
    def cutoff(years):
        year = as_of.year - years
        try:
            return as_of.replace(year=year)
        except ValueError:
            return as_of.replace(year=year, day=28)

    at_least_18, at_least_25, at_least_35 = cutoff(18), cutoff(25), cutoff(35)
    at_least_45, at_least_55 = cutoff(45), cutoff(55)
    return case(
        (User.date_of_birth.is_(None), "unknown"),
        (User.date_of_birth > at_least_18, "under-18"),
        (User.date_of_birth > at_least_25, "18-24"),
        (User.date_of_birth > at_least_35, "25-34"),
        (User.date_of_birth > at_least_45, "35-44"),
        (User.date_of_birth > at_least_55, "45-54"),
        else_="55+",
    )


def admin_analytics(start, end, min_group_size, currency, selected_band=None, category_id=None):
    bands = age_band_expression(end)
    totals = db.session.query(
        Transaction.user_id,
        func.sum(case((Transaction.type == "income", Transaction.amount), else_=0)).label("income"),
        func.sum(case((Transaction.type == "expense", Transaction.amount), else_=0)).label("expense"),
    ).filter(Transaction.transaction_date.between(start, end)).group_by(Transaction.user_id).subquery()
    base = db.session.query(
        bands.label("band"), totals.c.income, totals.c.expense,
    ).join(totals, totals.c.user_id == User.id).filter(
        User.is_active.is_(True), User.role == "user",
        User.date_of_birth.is_not(None),
        User.preferred_currency == currency,
    ).subquery()
    ranked = db.session.query(
        base.c.band, base.c.income, base.c.expense,
        func.row_number().over(partition_by=base.c.band, order_by=base.c.income).label("income_rank"),
        func.count().over(partition_by=base.c.band).label("group_count"),
        func.row_number().over(partition_by=base.c.band, order_by=base.c.expense).label("expense_rank"),
    ).subquery()
    grouped = db.session.query(
        ranked.c.band, func.count().label("participants"),
        func.avg(ranked.c.income).label("avg_income"),
        func.avg(ranked.c.expense).label("avg_expense"),
        func.avg(case((and_(ranked.c.income_rank * 2 >= ranked.c.group_count,
                            ranked.c.income_rank * 2 <= ranked.c.group_count + 2), ranked.c.income))).label("median_income"),
        func.avg(case((and_(ranked.c.expense_rank * 2 >= ranked.c.group_count,
                            ranked.c.expense_rank * 2 <= ranked.c.group_count + 2), ranked.c.expense))).label("median_expense"),
    ).group_by(ranked.c.band).all()
    allowed = {row.band: row for row in grouped if row.participants >= min_group_size and row.band in AGE_BANDS}

    category_query = db.session.query(
        Category.name, func.sum(Transaction.amount).label("amount"),
        func.count(func.distinct(Transaction.user_id)).label("participants"),
    ).join(Transaction, Transaction.category_id == Category.id).join(User, User.id == Transaction.user_id).filter(
        Transaction.type == "expense", Transaction.transaction_date.between(start, end),
        User.role == "user", User.is_active.is_(True),
        User.preferred_currency == currency,
    )
    if category_id:
        category_query = category_query.filter(Category.id == category_id)
    if selected_band in AGE_BANDS:
        category_query = category_query.filter(bands == selected_band)
    category_rows = category_query.group_by(Category.id, Category.name).order_by(func.sum(Transaction.amount).desc()).limit(12).all()
    category_data = [
        {"name": row.name, "amount": float(row.amount)}
        for row in category_rows if row.participants >= min_group_size
    ]

    age_category_query = db.session.query(
        bands.label("band"), Category.name, func.sum(Transaction.amount).label("amount"),
        func.count(func.distinct(Transaction.user_id)).label("participants"),
    ).join(Transaction, Transaction.category_id == Category.id).join(User, User.id == Transaction.user_id).filter(
        Transaction.type == "expense", Transaction.transaction_date.between(start, end),
        User.role == "user", User.is_active.is_(True), User.date_of_birth.is_not(None),
        User.preferred_currency == currency,
    )
    age_category_rows = age_category_query.group_by("band", Category.id, Category.name).all()
    age_categories = [
        {"band": row.band, "name": row.name, "amount": float(row.amount)}
        for row in age_category_rows
        if row.band in allowed and row.participants >= min_group_size
    ]

    reasons = db.session.query(
        func.max(Category.name), func.max(Transaction.reason_id), func.count(Transaction.id),
        func.count(func.distinct(Transaction.user_id)),
    ).join(Category, Category.id == Transaction.category_id).join(User, User.id == Transaction.user_id).filter(
        Transaction.type == "expense", Transaction.transaction_date.between(start, end),
        User.role == "user", User.is_active.is_(True),
        User.preferred_currency == currency,
    ).group_by(Transaction.reason_id).order_by(func.count(Transaction.id).desc()).limit(10).all()
    from app.models import Reason
    reason_names = dict(db.session.query(Reason.id, Reason.name).filter(Reason.id.in_([r[1] for r in reasons])).all()) if reasons else {}
    safe_reasons = [
        {"category": row[0], "reason": reason_names[row[1]], "count": row[2]}
        for row in reasons if row[3] >= min_group_size
    ]
    from sqlalchemy import extract
    year_expr, month_expr = extract("year", Transaction.transaction_date), extract("month", Transaction.transaction_date)
    monthly_rows = db.session.query(
        year_expr.label("year"), month_expr.label("month"),
        func.sum(case((Transaction.type == "income", Transaction.amount), else_=0)).label("income"),
        func.sum(case((Transaction.type == "expense", Transaction.amount), else_=0)).label("expense"),
        func.count(func.distinct(Transaction.user_id)).label("participants"),
    ).join(User, User.id == Transaction.user_id).filter(
        Transaction.transaction_date.between(start, end), User.role == "user", User.is_active.is_(True),
        User.preferred_currency == currency,
    ).group_by(year_expr, month_expr).order_by(year_expr, month_expr).all()
    monthly = [
        {"period": f"{int(row.year):04d}-{int(row.month):02d}", "income": float(row.income),
         "expense": float(row.expense)}
        for row in monthly_rows if row.participants >= min_group_size
    ]
    income_rows = db.session.query(
        Category.name, func.sum(Transaction.amount).label("amount"),
        func.count(func.distinct(Transaction.user_id)).label("participants"),
    ).join(Transaction, Transaction.category_id == Category.id).join(User, User.id == Transaction.user_id).filter(
        Category.type == "income", Transaction.type == "income",
        Transaction.transaction_date.between(start, end),
        User.role == "user", User.is_active.is_(True),
        User.preferred_currency == currency,
    ).group_by(Category.id, Category.name).order_by(func.sum(Transaction.amount).desc()).limit(10).all()
    income_sources = [
        {"name": row.name, "amount": float(row.amount)}
        for row in income_rows if row.participants >= min_group_size
    ]
    return {
        "groups": [
            {"band": band, "participants": row.participants,
             "avg_income": float(row.avg_income or 0), "avg_expense": float(row.avg_expense or 0),
             "median_income": float(row.median_income or 0), "median_expense": float(row.median_expense or 0)}
            for band, row in allowed.items()
        ],
        "categories": category_data,
        "age_categories": age_categories,
        "reasons": safe_reasons,
        "monthly": monthly,
        "income_sources": income_sources,
        "total_users": User.query.filter_by(is_active=True, role="user", preferred_currency=currency).count(),
        "covered_users": sum(row.participants for row in allowed.values()),
        "min_group_size": min_group_size,
        "currency": currency,
    }
