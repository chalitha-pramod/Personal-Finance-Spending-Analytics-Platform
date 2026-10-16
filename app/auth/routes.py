from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from urllib.parse import urljoin, urlparse

from app.auth.forms import LoginForm, PasswordResetForm, PasswordResetRequestForm, ProfileForm, RegistrationForm
from app.extensions import db, limiter
from app.models import User
from app.utils.dates import local_today

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        if form.date_of_birth.data and form.date_of_birth.data >= local_today():
            form.date_of_birth.errors.append("Date of birth must be in the past.")
            return render_template("auth/register.html", form=form)
        user = User(
            email=form.email.data.strip().lower(),
            name=form.name.data.strip(),
            date_of_birth=form.date_of_birth.data,
            preferred_currency=form.preferred_currency.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Your account is ready. Please sign in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter(func.lower(User.email) == form.email.data.strip().lower()).first()
        if user and user.is_active and user.check_password(form.password.data):
            login_user(user, remember=False, fresh=True)
            destination = request.args.get("next")
            base = urlparse(request.host_url)
            target = urlparse(urljoin(request.host_url, destination)) if destination else None
            if target and target.scheme in {"http", "https"} and target.netloc == base.netloc:
                return redirect(target.path + (f"?{target.query}" if target.query else "") + (f"#{target.fragment}" if target.fragment else ""))
            return redirect(url_for("dashboard.index"))
        flash("Invalid email or password, or the account is inactive.", "danger")
    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        if form.date_of_birth.data and form.date_of_birth.data >= local_today():
            form.date_of_birth.errors.append("Date of birth must be in the past.")
        elif form.preferred_currency.data != current_user.preferred_currency and (
            current_user.transactions.first() or current_user.budgets.first()
        ):
            form.preferred_currency.errors.append(
                "Currency cannot be changed after financial records exist because no exchange-rate conversion is applied."
            )
        else:
            current_user.name = form.name.data.strip()
            current_user.date_of_birth = form.date_of_birth.data
            current_user.preferred_currency = form.preferred_currency.data
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html", form=form)


@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter(func.lower(User.email) == form.email.data.strip().lower()).first()
        if user and user.is_active:
            token = user.get_reset_token()
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            if current_app.config.get("MAIL_HOST") and current_app.config.get("MAIL_FROM"):
                from app.auth.email import send_reset_email
                send_reset_email(user.email, reset_url)
            else:
                current_app.logger.warning("Password reset requested but email delivery is not configured.")
        flash("If an active account matches that email, a reset link will be sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def reset_password(token):
    user = User.verify_reset_token(token)
    if user is None or not user.is_active:
        flash("This password reset link is invalid or expired.", "danger")
        return redirect(url_for("auth.forgot_password"))
    form = PasswordResetForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been reset. Please sign in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)
