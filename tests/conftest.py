from datetime import date

import pytest

from app import create_app
from app.extensions import db
from app.models import Category, Reason, User


@pytest.fixture()
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "WTF_CSRF_ENABLED": False,
        "SESSION_COOKIE_SECURE": False,
        "RATELIMIT_ENABLED": False,
        "SESSION_PROTECTION": None,
    })
    with app.app_context():
        db.create_all()
        expense = Category(type="expense", name="Food", is_active=True)
        income = Category(type="income", name="Salary", is_active=True)
        db.session.add_all([expense, income])
        db.session.flush()
        db.session.add_all([
            Reason(category_id=expense.id, name="Groceries", is_active=True),
            Reason(category_id=income.id, name="Pay", is_active=True),
        ])
        user = User(email="person@example.com", name="Test Person", role="user", is_active=True, date_of_birth=date(1990, 5, 4))
        user.set_password("correct-horse-battery-staple")
        admin = User(email="admin@example.com", name="Admin", role="admin", is_active=True)
        admin.set_password("correct-horse-battery-staple")
        other = User(email="other@example.com", name="Other", role="user", is_active=True)
        other.set_password("correct-horse-battery-staple")
        db.session.add_all([user, admin, other])
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def user_ids(app):
    with app.app_context():
        return {
            user.email: user.id for user in User.query.all()
        }


@pytest.fixture()
def login(client):
    def _login(email="person@example.com", password="correct-horse-battery-staple"):
        return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)
    return _login
