from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models import Category, Reason, Transaction


def test_create_edit_delete_transaction_scoped_to_owner(client, login, app, user_ids):
    login()
    with app.app_context():
        category = Category.query.filter_by(name="Food").one()
        reason = Reason.query.filter_by(name="Groceries").one()
        category_id, reason_id = category.id, reason.id
    response = client.post("/transactions/new", data={
        "type": "expense", "category_id": category_id, "reason_id": reason_id,
        "amount": "125.50", "transaction_date": "2026-10-01", "description": "Weekly food",
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        transaction = Transaction.query.one()
        transaction_id = transaction.id
        assert transaction.user_id == user_ids["person@example.com"]
        assert transaction.amount == Decimal("125.50")
    assert client.post(f"/transactions/{transaction_id}/edit", data={
        "type": "expense", "category_id": category_id, "reason_id": reason_id,
        "amount": "99.00", "transaction_date": "2026-10-02",
    }).status_code == 302
    assert client.post(f"/transactions/{transaction_id}/delete").status_code == 302
    with app.app_context():
        assert Transaction.query.count() == 0


def test_rejects_invalid_amount_and_mismatched_reason(client, login, app):
    login()
    with app.app_context():
        expense = Category.query.filter_by(name="Food").one()
        income = Category.query.filter_by(name="Salary").one()
        food_reason = Reason.query.filter_by(category_id=expense.id).one()
        salary_reason = Reason.query.filter_by(category_id=income.id).one()
        expense_id, income_id = expense.id, income.id
        food_reason_id, salary_reason_id = food_reason.id, salary_reason.id
    for amount in ("0", "-2", "NaN", "1.239"):
        response = client.post("/transactions/new", data={
            "type": "expense", "category_id": expense_id, "reason_id": food_reason_id,
            "amount": amount, "transaction_date": "2026-10-01",
        })
        assert response.status_code == 200
    response = client.post("/transactions/new", data={
        "type": "expense", "category_id": expense_id, "reason_id": salary_reason_id,
        "amount": "12.00", "transaction_date": "2026-10-01",
    })
    assert response.status_code == 200
    with app.app_context():
        assert Transaction.query.count() == 0


def test_transaction_owner_isolation_and_csv(client, app):
    with app.app_context():
        category = Category.query.filter_by(name="Food").one()
        reason = Reason.query.filter_by(name="Groceries").one()
        other = __import__("app.models", fromlist=["User"]).User.query.filter_by(email="other@example.com").one()
        item = Transaction(user_id=other.id, type="expense", category_id=category.id, reason_id=reason.id,
                           amount=Decimal("14.25"), transaction_date=date(2026, 10, 1), description="private")
        db.session.add(item)
        db.session.commit()
        transaction_id = item.id
    login = client.post("/auth/login", data={"email": "person@example.com", "password": "correct-horse-battery-staple"})
    assert login.status_code == 302
    assert client.get(f"/transactions/{transaction_id}/edit").status_code == 404
    exported = client.get("/transactions/export.csv")
    assert exported.status_code == 200
    assert b"private" not in exported.data


def test_reports_and_chart_data_use_own_records(client, login):
    assert client.get("/api/chart-data").status_code == 401
    login()
    assert client.get("/reports?start=bad-date").status_code == 400
    assert client.get("/reports?grouping=month").status_code == 200
    assert client.get("/reports?grouping=year").status_code == 200
    assert client.get("/api/chart-data?period=month").status_code == 200
    assert client.get("/transactions/?type=unknown").status_code == 400
