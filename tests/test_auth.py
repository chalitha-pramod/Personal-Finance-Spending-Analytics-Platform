from app.models import User


def test_registration_hashes_password_and_logs_in(client, app):
    response = client.post("/auth/register", data={
        "name": "New Person", "email": "new@example.com",
        "password": "very-secure-password-123", "confirm_password": "very-secure-password-123",
        "preferred_currency": "LKR",
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="new@example.com").one()
        assert user.password_hash != "very-secure-password-123"
        assert user.check_password("very-secure-password-123")


def test_login_failure_and_deactivated_user(client, app):
    response = client.post("/auth/login", data={"email": "person@example.com", "password": "wrong-password"})
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="person@example.com").one()
        user.is_active = False
        from app.extensions import db
        db.session.commit()
    response = client.post("/auth/login", data={"email": "person@example.com", "password": "correct-horse-battery-staple"})
    assert b"Invalid email or password" in response.data


def test_reset_token_expires_and_changes_password(app, client):
    with app.app_context():
        user = User.query.filter_by(email="person@example.com").one()
        token = user.get_reset_token()
    response = client.post(f"/auth/reset-password/{token}", data={
        "password": "a-new-very-secure-password", "confirm_password": "a-new-very-secure-password",
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="person@example.com").one()
        assert user.check_password("a-new-very-secure-password")
        assert User.verify_reset_token(token) is None


def test_regular_user_cannot_access_admin(client, login):
    login()
    assert client.get("/admin/").status_code == 403


def test_deactivated_existing_session_is_rejected(client, login, app):
    login()
    with app.app_context():
        user = User.query.filter_by(email="person@example.com").one()
        user.is_active = False
        from app.extensions import db
        db.session.commit()
    response = client.get("/transactions/")
    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_login_rejects_external_redirect(client):
    response = client.post(
        "/auth/login?next=https://attacker.example/steal",
        data={"email": "person@example.com", "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 302
    assert response.location == "/"


def test_preferred_currency_cannot_relabel_existing_records(client, login, app):
    from datetime import date
    from decimal import Decimal

    from app.extensions import db
    from app.models import Category, Reason, Transaction

    login()
    with app.app_context():
        category = Category.query.filter_by(name="Food").one()
        reason = Reason.query.filter_by(name="Groceries").one()
        item = Transaction(user_id=User.query.filter_by(email="person@example.com").one().id,
                           type="expense", category_id=category.id, reason_id=reason.id,
                           amount=Decimal("25.00"), transaction_date=date(2026, 10, 1))
        db.session.add(item)
        db.session.commit()
    response = client.post("/auth/profile", data={
        "name": "Test Person", "date_of_birth": "1990-05-04", "preferred_currency": "USD",
    })
    assert response.status_code == 200
    assert b"Currency cannot be changed" in response.data
    with app.app_context():
        assert User.query.filter_by(email="person@example.com").one().preferred_currency == "LKR"
