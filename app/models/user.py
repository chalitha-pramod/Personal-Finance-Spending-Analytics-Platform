from datetime import date, datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint("role IN ('user', 'admin')", name="ck_user_role"),
        db.CheckConstraint("preferred_currency IN ('LKR', 'USD', 'EUR', 'GBP')", name="ck_user_currency"),
    )
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="user", index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    password_reset_version = db.Column(db.Integer, nullable=False, default=0, server_default=db.text("0"))
    name = db.Column(db.String(120), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=True)
    preferred_currency = db.Column(db.String(3), nullable=False, default="LKR")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    transactions = db.relationship("Transaction", back_populates="user", lazy="dynamic")
    budgets = db.relationship("Budget", back_populates="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.password_reset_version = (self.password_reset_version or 0) + 1

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def age_on(self, on_date=None):
        if not self.date_of_birth:
            return None
        on_date = on_date or date.today()
        return on_date.year - self.date_of_birth.year - (
            (on_date.month, on_date.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def get_reset_token(self):
        from flask import current_app
        from itsdangerous import URLSafeTimedSerializer

        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset-v1")
        return serializer.dumps({"user_id": self.id, "version": self.password_reset_version})

    @staticmethod
    def verify_reset_token(token, max_age=None):
        from flask import current_app
        from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset-v1")
        try:
            payload = serializer.loads(
                token,
                max_age=max_age or current_app.config["PASSWORD_RESET_TOKEN_MAX_AGE"],
            )
        except (BadSignature, SignatureExpired):
            return None
        user = db.session.get(User, payload.get("user_id"))
        if user is None or payload.get("version") != user.password_reset_version:
            return None
        return user
