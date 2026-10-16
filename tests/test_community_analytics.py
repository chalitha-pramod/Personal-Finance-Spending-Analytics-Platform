from datetime import date, timedelta
from decimal import Decimal

from app.community.services import (
    COMMUNITY_AGE_LABELS,
    classify_age,
    community_analytics,
    resolve_period,
)
from app.extensions import db
from app.models import Category, Reason, Transaction, User


def add_contributors(count, date_of_birth=date(1990, 1, 1), currency="LKR"):
    category = Category.query.filter_by(name="Food", type="expense").one()
    reason = Reason.query.filter_by(name="Groceries").one()
    users = []
    for index in range(count):
        user = User(
            email=f"community-{index}-{date_of_birth.isoformat()}-{currency}@example.com",
            name=f"Private Name {index}",
            role="user",
            is_active=True,
            date_of_birth=date_of_birth,
            preferred_currency=currency,
        )
        user.set_password("community-test-secure-password")
        db.session.add(user)
        db.session.flush()
        db.session.add_all([
            Transaction(
                user_id=user.id,
                type="income",
                category_id=category.id,
                reason_id=reason.id,
                amount=Decimal("100.00"),
                transaction_date=date.today(),
                description=f"private income note {index}",
            ),
            Transaction(
                user_id=user.id,
                type="expense",
                category_id=category.id,
                reason_id=reason.id,
                amount=Decimal(20 + index),
                transaction_date=date.today(),
                description=f"private expense note {index}",
            ),
        ])
        users.append(user)
    db.session.commit()
    return users


def test_age_boundaries_and_period_resolution():
    as_of = date(2026, 10, 16)
    assert classify_age(None, as_of) == "unknown"
    assert classify_age(date(2009, 10, 17), as_of) == "under-18"
    assert classify_age(date(2008, 10, 16), as_of) == "18-24"
    assert classify_age(date(2001, 10, 16), as_of) == "25-34"
    assert classify_age(date(1991, 10, 16), as_of) == "35-44"
    assert classify_age(date(1981, 10, 16), as_of) == "45-54"
    assert classify_age(date(1971, 10, 16), as_of) == "55+"
    assert resolve_period("last_3_months", as_of) == (date(2026, 8, 1), as_of)
    assert resolve_period("last_year", as_of) == (date(2025, 1, 1), date(2025, 12, 31))
    assert resolve_period("this_month", as_of) == (date(2026, 10, 1), as_of)


def test_community_page_and_api_require_authentication(client):
    page = client.get("/community/")
    assert page.status_code == 302
    api = client.get("/community/api/data")
    assert api.status_code == 401
    assert api.get_json() == {"error": "Authentication required."}


def test_small_cohorts_are_suppressed_without_exact_counts(client, login, app):
    login()
    page = client.get("/community/")
    assert page.status_code == 200
    assert b"Community insights" in page.data
    assert b"Custom range" in page.data
    with app.app_context():
        category = Category.query.filter_by(name="Food").one()
        reason = Reason.query.filter_by(name="Groceries").one()
        user = User.query.filter_by(email="person@example.com").one()
        db.session.add(Transaction(
            user_id=user.id,
            type="expense",
            category_id=category.id,
            reason_id=reason.id,
            amount=Decimal("9876.54"),
            transaction_date=date.today(),
            description="must never reach community API",
        ))
        db.session.commit()
    response = client.get("/community/api/data?period=this_month")
    assert response.status_code == 200
    data = response.get_json()
    assert data["overview"]["available"] is False
    assert data["overview"]["income"] is None
    assert data["categories"]["available"] is False
    assert data["categories"]["items"] == []
    assert data["age_groups"]["items"] == []
    assert "must never reach" not in response.text
    assert "9876.54" not in response.text
    assert "person@example.com" not in response.text
    assert "contributors" not in data
    assert response.headers["Cache-Control"] == "private, no-store"


def test_community_averages_and_categories_use_distinct_eligible_users(app):
    with app.app_context():
        add_contributors(10)
        today = date.today()
        result = community_analytics(
            today.replace(day=1), today, "LKR", "monthly", 10, 6, today
        )
        assert result["overview"]["available"] is True
        assert result["overview"]["income"] == 1000.0
        assert result["overview"]["expenses"] == 245.0
        assert result["overview"]["difference"] == 755.0
        assert result["overview"]["spending_ratio"] == 24.5
        age_group = next(item for item in result["age_groups"]["items"] if item["key"] == "35-44")
        assert age_group["average_income"] == 100.0
        assert age_group["average_expenses"] == 24.5
        assert result["age_groups"]["highest_spending"] == COMMUNITY_AGE_LABELS["35-44"]
        assert result["categories"]["available"] is True
        assert result["categories"]["items"] == [
            {"name": "Food", "amount": 245.0, "percentage": 100.0}
        ]
        assert result["trends"]["available"] is True
        assert len(result["trends"]["points"]) == 1
        assert result["category_trends"]["available"] is True


def test_zero_income_ratio_and_yearly_time_series(app):
    with app.app_context():
        users = add_contributors(10)
        user_ids = [user.id for user in users]
        Transaction.query.filter(
            Transaction.user_id.in_(user_ids),
            Transaction.type == "income",
        ).delete(synchronize_session=False)
        db.session.commit()
        today = date.today()
        result = community_analytics(
            today.replace(day=1), today, "LKR", "yearly", 10, 6, today
        )
        assert result["overview"]["available"] is True
        assert result["overview"]["income"] == 0
        assert result["overview"]["spending_ratio"] is None
        assert result["trends"]["available"] is True
        assert result["trends"]["points"][0]["period"] == str(today.year)
        assert result["trends"]["points"][0]["income"] == 0
        assert result["category_trends"]["available"] is True
        assert result["category_trends"]["labels"] == [today.strftime("%Y-%m")]
        assert result["category_trends"]["datasets"][0]["data"] == [245.0]


def test_underage_unknown_admin_and_inactive_accounts_are_excluded(app):
    with app.app_context():
        add_contributors(10)
        category = Category.query.filter_by(name="Food").one()
        reason = Reason.query.filter_by(name="Groceries").one()
        underage = User(
            email="underage-community@example.com", name="Underage", role="user",
            is_active=True, date_of_birth=date.today() - timedelta(days=16 * 365),
        )
        unknown = User(email="unknown-community@example.com", name="Unknown", role="user", is_active=True)
        inactive = User(
            email="inactive-community@example.com", name="Inactive", role="user",
            is_active=False, date_of_birth=date(1990, 1, 1),
        )
        admin = User(
            email="admin-community@example.com", name="Admin", role="admin",
            is_active=True, date_of_birth=date(1990, 1, 1),
        )
        for user in (underage, unknown, inactive, admin):
            user.set_password("community-test-secure-password")
            db.session.add(user)
            db.session.flush()
            db.session.add(Transaction(
                user_id=user.id, type="income", category_id=category.id,
                reason_id=reason.id, amount=Decimal("10000.00"),
                transaction_date=date.today(),
            ))
        db.session.commit()
        today = date.today()
        result = community_analytics(today.replace(day=1), today, "LKR", "monthly", 10, 6, today)
        assert result["overview"]["income"] == 1000.0
        assert result["overview"]["expenses"] == 245.0


def test_category_and_month_subgroups_trigger_complementary_suppression(app):
    with app.app_context():
        users = add_contributors(10)
        food = Category.query.filter_by(name="Food").one()
        reason = Reason.query.filter_by(name="Groceries").one()
        rare = Category(type="expense", name="Rare category", is_active=True)
        db.session.add(rare)
        db.session.flush()
        rare_reason = Reason(category_id=rare.id, name="Rare reason", is_active=True)
        db.session.add(rare_reason)
        db.session.add(Transaction(
            user_id=users[0].id, type="expense", category_id=rare.id,
            reason_id=rare_reason.id, amount=Decimal("5.00"),
            transaction_date=date.today(),
        ))
        db.session.commit()
        today = date.today()
        start = today.replace(day=1)
        result = community_analytics(start, today, "LKR", "monthly", 10, 6, today)
        assert result["categories"]["available"] is False
        assert result["categories"]["items"] == []
        assert result["category_trends"]["available"] is False

        previous_month_end = start - timedelta(days=1)
        db.session.add(Transaction(
            user_id=users[0].id, type="expense", category_id=food.id,
            reason_id=Reason.query.filter_by(category_id=food.id).one().id,
            amount=Decimal("1.00"), transaction_date=previous_month_end,
        ))
        db.session.commit()
        cross_month = community_analytics(
            previous_month_end.replace(day=1), today, "LKR", "monthly", 10, 6, today
        )
        assert cross_month["trends"]["available"] is False
        assert cross_month["trends"]["points"] == []
        assert cross_month["overview"]["available"] is False


def test_api_rejects_invalid_filters_and_returns_aggregates_only(client, login, app):
    login()
    assert client.get("/community/api/data?period=invalid").status_code == 400
    assert client.get("/community/api/data?currency=JPY").status_code == 400
    assert client.get("/community/api/data?interval=raw_sql").status_code == 400
    assert client.get("/community/api/data?period=custom&start=bad&end=bad").status_code == 400
    with app.app_context():
        add_contributors(10)
    response = client.get("/community/api/data?period=this_month")
    assert response.status_code == 200
    body = response.get_json()
    assert set(body) == {
        "currency", "minimum_cohort_size", "eligibility", "overview",
        "categories", "age_groups", "trends", "category_trends", "period",
    }
    assert "Private Name" not in response.text
    assert "community-0-" not in response.text
    assert "private expense note" not in response.text
    assert "user_id" not in response.text
