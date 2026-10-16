from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.analytics.services import age_band_expression
from app.extensions import db
from app.models import Budget, Category, Reason, Transaction, User


def test_budget_threshold_and_category_spending(client, login, app, user_ids):
    login()
    with app.app_context():
        user_id = user_ids["person@example.com"]
        category = Category.query.filter_by(name="Food").one()
        reason = Reason.query.filter_by(name="Groceries").one()
        category_id, reason_id = category.id, reason.id
    assert client.post("/budgets/", data={
        "category_id": category_id, "amount": "100.00", "year": "2026", "month": "10",
        "warning_threshold": "80",
    }).status_code == 302
    assert client.post("/transactions/new", data={
        "type": "expense", "category_id": category_id, "reason_id": reason_id,
        "amount": "85.00", "transaction_date": "2026-10-01",
    }).status_code == 302
    response = client.get("/budgets/?year=2026&month=10")
    assert response.status_code == 200
    assert b"warning threshold" in response.data
    with app.app_context():
        assert Budget.query.filter_by(user_id=user_id).one().amount == Decimal("100.00")


def test_admin_analytics_suppresses_small_groups(client, login, app):
    login("admin@example.com")
    page = client.get("/admin/analytics/?currency=USD")
    assert page.status_code == 200
    assert b"Currency: USD" in page.data
    assert client.get("/admin/categories/").status_code == 200
    response = client.get("/admin/analytics/api/data?start=2026-10-01&end=2026-10-15")
    assert response.status_code == 200
    data = response.get_json()
    assert data["groups"] == []
    assert data["categories"] == []
    assert data["reasons"] == []


def test_admin_analytics_shows_aggregate_medians_at_threshold(client, login, app):
    with app.app_context():
        category = Category.query.filter_by(name="Food").one()
        reason = Reason.query.filter_by(name="Groceries").one()
        for index in range(10):
            user = User(email=f"sample{index}@example.com", name=f"Sample {index}", role="user",
                        is_active=True, date_of_birth=date(1990, 1, 1))
            user.set_password("sample-only-very-secure-password")
            db.session.add(user)
            db.session.flush()
            db.session.add_all([
                Transaction(user_id=user.id, type="income", category_id=category.id, reason_id=reason.id,
                            amount=Decimal((index + 1) * 10), transaction_date=date(2026, 10, 1)),
                Transaction(user_id=user.id, type="expense", category_id=category.id, reason_id=reason.id,
                            amount=Decimal((index + 1) * 5), transaction_date=date(2026, 10, 2)),
            ])
        db.session.commit()
    login("admin@example.com")
    response = client.get("/admin/analytics/api/data?start=2026-10-01&end=2026-10-15")
    assert response.status_code == 200
    data = response.get_json()
    band = next(row for row in data["groups"] if row["band"] == "35-44")
    assert band["participants"] == 10
    assert band["median_income"] == 55
    assert band["median_expense"] == 27.5
    assert "Sample 0" not in response.text
    assert data["categories"][0]["name"] == "Food"


def test_age_group_calculated_from_dob(app):
    with app.app_context():
        result = db.session.query(age_band_expression(date(2026, 10, 15))).select_from(User).filter(User.email == "person@example.com").scalar()
        assert result == "35-44"


def test_money_check_constraint(app):
    with app.app_context():
        user = User.query.filter_by(email="person@example.com").one()
        category = Category.query.filter_by(name="Food").one()
        reason = Reason.query.filter_by(name="Groceries").one()
        db.session.add(Transaction(user_id=user.id, type="expense", category_id=category.id,
                                   reason_id=reason.id, amount=Decimal("0"), transaction_date=date.today()))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
