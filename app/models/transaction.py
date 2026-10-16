from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db


class Transaction(db.Model):
    __tablename__ = "transactions"
    __table_args__ = (
        db.CheckConstraint("amount > 0", name="ck_transaction_amount_positive"),
        db.CheckConstraint("type IN ('income', 'expense')", name="ck_transaction_type"),
        db.Index("ix_transaction_user_date", "user_id", "transaction_date"),
        db.Index("ix_transaction_user_type_date", "user_id", "type", "transaction_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = db.Column(db.String(8), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    reason_id = db.Column(db.Integer, db.ForeignKey("reasons.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2, asdecimal=True), nullable=False)
    transaction_date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(500), nullable=True)
    payment_method = db.Column(db.String(40), nullable=True)
    recurring_reference = db.Column(db.String(64), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="transactions")
    category = db.relationship("Category", back_populates="transactions")
    reason = db.relationship("Reason", back_populates="transactions")

    def __init__(self, **kwargs):
        if "amount" in kwargs:
            kwargs["amount"] = Decimal(str(kwargs["amount"]))
        super().__init__(**kwargs)
