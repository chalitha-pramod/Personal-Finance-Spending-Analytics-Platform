from datetime import datetime, timezone

from app.extensions import db


class Category(db.Model):
    __tablename__ = "categories"
    __table_args__ = (
        db.UniqueConstraint("type", "name", name="uq_category_type_name"),
        db.CheckConstraint("type IN ('income', 'expense')", name="ck_category_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    type = db.Column(db.String(8), nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    reasons = db.relationship("Reason", back_populates="category", lazy="select", cascade="all, delete-orphan")
    transactions = db.relationship("Transaction", back_populates="category")


class Reason(db.Model):
    __tablename__ = "reasons"
    __table_args__ = (db.UniqueConstraint("category_id", "name", name="uq_reason_category_name"),)

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    category = db.relationship("Category", back_populates="reasons")
    transactions = db.relationship("Transaction", back_populates="reason")
