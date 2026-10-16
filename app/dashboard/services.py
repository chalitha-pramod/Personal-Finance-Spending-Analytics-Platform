from datetime import timedelta
from decimal import Decimal

from sqlalchemy import case, extract, func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Budget, Transaction


def dashboard_summary(user_id, start, end):
    totals = db.session.query(
        Transaction.type, func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == user_id,
        Transaction.transaction_date.between(start, end),
    ).group_by(Transaction.type).all()
    totals = dict(totals)
    income, expenses = Decimal(str(totals.get("income", 0))), Decimal(str(totals.get("expense", 0)))

    if (end - start).days > 31:
        year_expr = extract("year", Transaction.transaction_date)
        month_expr = extract("month", Transaction.transaction_date)
        trend_query = db.session.query(
            year_expr.label("year"), month_expr.label("month"),
            func.sum(case((Transaction.type == "income", Transaction.amount), else_=0)),
            func.sum(case((Transaction.type == "expense", Transaction.amount), else_=0)),
        ).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date.between(start, end),
        ).group_by(year_expr, month_expr).order_by(year_expr, month_expr).all()
        trend = [{"date": f"{int(row[0]):04d}-{int(row[1]):02d}", "income": float(row[2]), "expense": float(row[3])} for row in trend_query]
    else:
        daily = db.session.query(
            Transaction.transaction_date,
        func.sum(case((Transaction.type == "income", Transaction.amount), else_=0)),
        func.sum(case((Transaction.type == "expense", Transaction.amount), else_=0)),
        ).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date.between(start, end),
        ).group_by(Transaction.transaction_date).order_by(Transaction.transaction_date).all()
        trend = [{"date": row[0].isoformat(), "income": float(row[1]), "expense": float(row[2])} for row in daily]
    categories = db.session.query(
        Transaction.category_id, func.max(Transaction.category_id),
        func.sum(Transaction.amount),
    ).filter(
        Transaction.user_id == user_id, Transaction.type == "expense",
        Transaction.transaction_date.between(start, end),
    ).group_by(Transaction.category_id).order_by(func.sum(Transaction.amount).desc()).limit(8).all()
    period_length = end - start + timedelta(days=1)
    previous_start, previous_end = start - period_length, start - timedelta(days=1)
    current_by_category = dict(db.session.query(
        Transaction.category_id, func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == user_id, Transaction.type == "expense",
        Transaction.transaction_date.between(start, end),
    ).group_by(Transaction.category_id).all())
    previous_by_category = dict(db.session.query(
        Transaction.category_id, func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == user_id, Transaction.type == "expense",
        Transaction.transaction_date.between(previous_start, previous_end),
    ).group_by(Transaction.category_id).all())

    budget_rows = db.session.query(
        Budget.id, Budget.amount, Budget.warning_threshold, Budget.category_id,
        func.coalesce(func.sum(Transaction.amount), 0),
    ).outerjoin(
        Transaction,
        (Transaction.user_id == Budget.user_id)
        & (Transaction.category_id == Budget.category_id)
        & (Transaction.type == "expense")
        & (Transaction.transaction_date >= start)
        & (Transaction.transaction_date <= end),
    ).filter(
        Budget.user_id == user_id, Budget.year == start.year, Budget.month == start.month,
    ).group_by(Budget.id).all()

    from app.models import Category, Reason
    reason_rows = db.session.query(
        Reason.name, func.sum(Transaction.amount)
    ).join(Transaction, Transaction.reason_id == Reason.id).filter(
        Transaction.user_id == user_id, Transaction.type == "expense",
        Transaction.transaction_date.between(start, end),
    ).group_by(Reason.id, Reason.name).order_by(func.sum(Transaction.amount).desc()).limit(8).all()
    income_rows = db.session.query(
        Category.name, func.sum(Transaction.amount)
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user_id, Transaction.type == "income",
        Transaction.transaction_date.between(start, end),
    ).group_by(Category.id, Category.name).order_by(func.sum(Transaction.amount).desc()).limit(5).all()
    category_names = dict(db.session.query(Category.id, Category.name).filter(Category.id.in_([row[0] for row in categories])).all()) if categories else {}
    insight_names = dict(db.session.query(Category.id, Category.name).filter(Category.id.in_(list(current_by_category))).all()) if current_by_category else {}
    budget_names = dict(db.session.query(Category.id, Category.name).filter(Category.id.in_([row[3] for row in budget_rows])).all()) if budget_rows else {}
    recent = Transaction.query.filter_by(user_id=user_id).options(
        joinedload(Transaction.category), joinedload(Transaction.reason)
    ).order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).limit(8).all()

    return {
        "income": income, "expenses": expenses, "net": income - expenses,
        "days": trend,
        "categories": [{"name": category_names[row[0]], "amount": float(row[2])} for row in categories],
        "reasons": [{"name": row[0], "amount": float(row[1])} for row in reason_rows],
        "income_sources": [{"name": row[0], "amount": float(row[1])} for row in income_rows],
        "insights": [
            {"name": insight_names[category_id], "current": float(amount), "previous": float(previous_by_category.get(category_id, 0))}
            for category_id, amount in current_by_category.items()
            if Decimal(str(amount)) > Decimal(str(previous_by_category.get(category_id, 0)))
        ],
        "budgets": [{
            "name": budget_names[row[3]], "amount": float(row[1]), "spent": float(row[4]),
            "utilization": float(Decimal(str(row[4])) / Decimal(str(row[1])) * 100),
            "threshold": float(row[2]),
            "remaining": float(Decimal(str(row[1])) - Decimal(str(row[4]))),
        } for row in budget_rows],
        "remaining_budget": sum((Decimal(str(row[1])) - Decimal(str(row[4])) for row in budget_rows), Decimal("0")),
        "recent": recent,
    }


def report_summary(user_id, start, end, granularity):
    year_expr = extract("year", Transaction.transaction_date)
    month_expr = extract("month", Transaction.transaction_date)
    if granularity == "day":
        grouping = (Transaction.transaction_date,)
    elif granularity == "month":
        grouping = (year_expr, month_expr)
    else:
        grouping = (year_expr,)

    income_expr = func.sum(case((Transaction.type == "income", Transaction.amount), else_=0))
    expense_expr = func.sum(case((Transaction.type == "expense", Transaction.amount), else_=0))
    period_query = db.session.query(
        *grouping, income_expr.label("income"), expense_expr.label("expense")
    ).filter(
        Transaction.user_id == user_id,
        Transaction.transaction_date.between(start, end),
    ).group_by(*grouping)
    period_query = period_query.order_by(*grouping)
    periods = []
    for row in period_query.all():
        if granularity == "day":
            label = row[0].isoformat()
        elif granularity == "month":
            label = f"{int(row[0]):04d}-{int(row[1]):02d}"
        else:
            label = str(int(row[0]))
        periods.append({"period": label, "income": Decimal(str(row[-2] or 0)), "expenses": Decimal(str(row[-1] or 0))})

    from app.models import Category, Reason
    category_rows = db.session.query(
        Category.name, func.sum(Transaction.amount).label("amount")
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user_id, Transaction.type == "expense",
        Transaction.transaction_date.between(start, end),
    ).group_by(Category.id, Category.name).order_by(func.sum(Transaction.amount).desc()).all()
    reason_rows = db.session.query(
        Reason.name, func.sum(Transaction.amount).label("amount")
    ).join(Transaction, Transaction.reason_id == Reason.id).filter(
        Transaction.user_id == user_id, Transaction.type == "expense",
        Transaction.transaction_date.between(start, end),
    ).group_by(Reason.id, Reason.name).order_by(func.sum(Transaction.amount).desc()).limit(10).all()

    daily_expenses = db.session.query(
        Transaction.transaction_date.label("day"), func.sum(Transaction.amount).label("expenses")
    ).filter(
        Transaction.user_id == user_id, Transaction.type == "expense",
        Transaction.transaction_date.between(start, end),
    ).group_by(Transaction.transaction_date).subquery()
    monthly_expenses = db.session.query(
        year_expr.label("year"), month_expr.label("month"), func.sum(Transaction.amount).label("expenses")
    ).filter(
        Transaction.user_id == user_id, Transaction.type == "expense",
        Transaction.transaction_date.between(start, end),
    ).group_by(year_expr, month_expr).subquery()
    highest_days = db.session.query(daily_expenses.c.day, daily_expenses.c.expenses).order_by(
        daily_expenses.c.expenses.desc(), daily_expenses.c.day.desc()
    ).limit(5).all()
    highest_months = db.session.query(monthly_expenses.c.year, monthly_expenses.c.month, monthly_expenses.c.expenses).order_by(
        monthly_expenses.c.expenses.desc(), monthly_expenses.c.year.desc(), monthly_expenses.c.month.desc()
    ).limit(5).all()
    average_day = db.session.query(func.avg(daily_expenses.c.expenses)).scalar()
    average_month = db.session.query(func.avg(monthly_expenses.c.expenses)).scalar()
    return {
        "periods": periods,
        "categories": [{"name": row.name, "amount": Decimal(str(row.amount))} for row in category_rows],
        "reasons": [{"name": row.name, "amount": Decimal(str(row.amount))} for row in reason_rows],
        "highest_days": [{"date": row.day, "amount": Decimal(str(row.expenses))} for row in highest_days],
        "highest_months": [{"period": f"{int(row.year):04d}-{int(row.month):02d}", "amount": Decimal(str(row.expenses))} for row in highest_months],
        "average_daily_expense": Decimal(str(average_day or 0)),
        "average_monthly_expense": Decimal(str(average_month or 0)),
    }
