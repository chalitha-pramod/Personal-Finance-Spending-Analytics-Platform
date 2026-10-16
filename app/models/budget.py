from datetime import datetime, timezone

from app.extensions import db


class Budget(db.Model):
    __tablename__ = "budgets"
    __table_args__ = (
        db.UniqueConstraint("user_id", "category_id", "year", "month", name="uq_budget_user_category_period"),
        db.CheckConstraint("amount > 0", name="ck_budget_amount_positive"),
        db.CheckConstraint("month BETWEEN 1 AND 12", name="ck_budget_month"),
        db.CheckConstraint("warning_threshold BETWEEN 1 AND 100", name="ck_budget_warning_threshold"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(12, 2, asdecimal=True), nullable=False)
    warning_threshold = db.Column(db.Numeric(5, 2, asdecimal=True), nullable=False, default=80)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", back_populates="budgets")
    category = db.relationship("Category")
