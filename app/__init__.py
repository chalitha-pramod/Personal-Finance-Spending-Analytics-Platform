import logging
import os

import click
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, logout_user
from sqlalchemy import text

from app.extensions import csrf, db, limiter, login_manager, migrate


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object("config.Config")
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        if not app.testing:
            raise RuntimeError("Set SECRET_KEY in the environment before starting the application.")
        app.config["SECRET_KEY"] = "test-only-secret"
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"
    login_manager.session_protection = app.config.get("SESSION_PROTECTION", "strong")

    from app.models import AuditLog, Budget, Category, Reason, Transaction, User  # noqa: F401
    from app.admin.routes import bp as admin_bp
    from app.analytics.routes import bp as analytics_bp
    from app.auth.routes import bp as auth_bp
    from app.budgets.routes import bp as budgets_bp
    from app.categories.routes import bp as categories_bp
    from app.community.routes import bp as community_bp
    from app.dashboard.routes import bp as dashboard_bp
    from app.transactions.routes import bp as transactions_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(budgets_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(analytics_bp)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = db.session.get(User, int(user_id))
            return user if user and user.is_active else None
        except (TypeError, ValueError):
            return None

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        if "/api/" in request.path or request.accept_mimetypes.best == "application/json":
            return jsonify(error="Authentication required."), 401
        return redirect(url_for("auth.login", next=request.url))

    @app.context_processor
    def inject_context():
        return {"current_user": current_user}

    @app.before_request
    def reject_deactivated_sessions():
        if current_user.is_authenticated:
            db.session.refresh(current_user)
            if not current_user.is_active:
                logout_user()

    @app.errorhandler(400)
    def bad_request(error):
        if "/api/" in request.path or request.accept_mimetypes.best == "application/json":
            return jsonify(error="Invalid request."), 400
        return render_template("errors/400.html"), 400

    @app.errorhandler(401)
    def unauthorized(error):
        if "/api/" in request.path or request.accept_mimetypes.best == "application/json":
            return jsonify(error="Authentication required."), 401
        return render_template("errors/401.html"), 401

    @app.errorhandler(403)
    def forbidden(error):
        if "/api/" in request.path or request.accept_mimetypes.best == "application/json":
            return jsonify(error="Access denied."), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        if "/api/" in request.path or request.accept_mimetypes.best == "application/json":
            return jsonify(error="Not found."), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.exception("Unhandled application error")
        if "/api/" in request.path or request.accept_mimetypes.best == "application/json":
            return jsonify(error="An unexpected error occurred."), 500
        return render_template("errors/500.html"), 500

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt=True)
    @click.password_option()
    def create_admin(email, name, password):
        """Create an administrator without a hardcoded credential."""
        normalized_email = email.strip().lower()
        if User.query.filter_by(email=normalized_email).first():
            raise click.ClickException("An account with that email already exists.")
        user = User(email=normalized_email, name=name.strip(), role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo("Administrator account created.")

    @app.cli.command("seed-dev")
    def seed_dev():
        """Create only baseline categories and reasons for development."""
        defaults = {
            "expense": {
                "Food": ["Groceries", "Dining out"], "Transport": ["Public transit", "Fuel"],
                "Housing": ["Rent", "Maintenance"], "Utilities": ["Electricity", "Internet"],
                "Healthcare": ["Medical care"], "Education": ["Courses"], "Entertainment": ["Events"],
                "Shopping": ["Household"], "Savings and investments": ["Investment"], "Other": ["Other"],
            },
            "income": {
                "Salary": ["Primary employment"], "Freelancing": ["Contract work"],
                "Business": ["Business income"], "Investments": ["Returns"], "Other income": ["Other"],
            },
        }
        for kind, groups in defaults.items():
            for name, reasons in groups.items():
                category = Category.query.filter_by(type=kind, name=name).first()
                if category is None:
                    category = Category(type=kind, name=name, is_active=True)
                    db.session.add(category)
                    db.session.flush()
                for reason_name in reasons:
                    if not Reason.query.filter_by(category_id=category.id, name=reason_name).first():
                        db.session.add(Reason(category_id=category.id, name=reason_name, is_active=True))
        db.session.commit()
        click.echo("Development categories and reasons are ready.")

    @app.cli.command("db-check")
    def db_check():
        """Verify that the configured database can be reached."""
        db.session.execute(text("SELECT 1"))
        click.echo("Database connection successful.")

    logging.getLogger("werkzeug").setLevel(logging.INFO)
    return app
