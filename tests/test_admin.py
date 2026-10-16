from app.extensions import db
from app.models import Category, Reason, User


def test_admin_category_lifecycle_and_audit(client, login, app):
    login("admin@example.com")
    assert client.post("/admin/categories/create", data={"name": "Travel", "type": "expense"}).status_code == 302
    with app.app_context():
        category = Category.query.filter_by(name="Travel").one()
        category_id = category.id
    assert client.post(f"/admin/categories/{category_id}/reasons", data={"name": "Holiday"}).status_code == 302
    with app.app_context():
        reason_id = Reason.query.filter_by(name="Holiday").one().id
    assert client.post(f"/admin/categories/{category_id}/toggle").status_code == 302
    assert client.post(f"/admin/categories/reasons/{reason_id}/toggle").status_code == 302
    assert client.post(f"/admin/categories/{category_id}/archive").status_code == 302
    assert client.get("/admin/audit").status_code == 200
    with app.app_context():
        assert db.session.get(Category, category_id).archived_at is not None
        assert db.session.get(Reason, reason_id).archived_at is not None


def test_user_can_only_view_own_dashboard_and_admin_users_restricted(client, login):
    login()
    assert client.get("/admin/users").status_code == 403
    assert client.get("/").status_code == 200
    assert client.get("/api/chart-data").get_json()["labels"] == []


def test_admin_can_deactivate_regular_account(client, login, app):
    login("admin@example.com")
    with app.app_context():
        user_id = User.query.filter_by(email="other@example.com").one().id
    assert client.post(f"/admin/users/{user_id}/toggle").status_code == 302
    with app.app_context():
        assert not db.session.get(User, user_id).is_active
