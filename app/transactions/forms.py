from decimal import Decimal, InvalidOperation

from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from app.models import Category, Reason


class TransactionForm(FlaskForm):
    type = SelectField("Type", choices=[("expense", "Expense"), ("income", "Income")], validators=[DataRequired()])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    reason_id = SelectField("Reason", coerce=int, validators=[DataRequired()])
    amount = DecimalField("Amount", places=2, validators=[DataRequired(), NumberRange(min=Decimal("0.01"))])
    transaction_date = DateField("Date", validators=[DataRequired()])
    description = StringField("Description", validators=[Optional(), Length(max=500)])
    payment_method = SelectField("Payment method", choices=[("", "Not specified"), ("cash", "Cash"), ("card", "Card"), ("bank_transfer", "Bank transfer"), ("mobile", "Mobile payment"), ("other", "Other")], validators=[Optional()])
    submit = SubmitField("Save transaction")

    def set_choices(self, kind=None, selected_category=None, existing=None):
        query = Category.query.filter_by(is_active=True)
        if kind in {"income", "expense"}:
            query = query.filter_by(type=kind)
        categories = query.order_by(Category.name).all()
        self.original_category_id = existing.category_id if existing else None
        self.original_reason_id = existing.reason_id if existing else None
        if existing and existing.category.type == kind and existing.category_id not in {category.id for category in categories}:
            categories.append(existing.category)
        self.category_id.choices = [(c.id, c.name) for c in categories]
        reasons = Reason.query.join(Category).filter(Reason.is_active.is_(True), Category.is_active.is_(True))
        if selected_category:
            reasons = reasons.filter(Reason.category_id == selected_category)
        reason_list = reasons.order_by(Reason.name).all()
        if existing and existing.category_id == selected_category and existing.reason_id not in {reason.id for reason in reason_list}:
            reason_list.append(existing.reason)
        self.reason_id.choices = [(r.id, r.name) for r in reason_list]

    def validate_category_id(self, field):
        category = Category.query.filter_by(id=field.data, type=self.type.data).first()
        if category is None or (not category.is_active and field.data != self.original_category_id):
            raise ValidationError("Choose an active category for this transaction type.")

    def validate_reason_id(self, field):
        reason = Reason.query.join(Category).filter(
            Reason.id == field.data, Category.id == self.category_id.data,
            Category.type == self.type.data,
        ).first()
        if reason is None or (
            not reason.is_active and field.data != self.original_reason_id
        ) or (not reason.category.is_active and self.category_id.data != self.original_category_id):
            raise ValidationError("Choose an active reason belonging to the selected category.")

    def validate_amount(self, field):
        try:
            amount = Decimal(str(field.data))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("Enter a valid amount.")
        if not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99"):
            raise ValidationError("Amount must be greater than zero and within the supported limit.")
        if amount != amount.quantize(Decimal("0.01")):
            raise ValidationError("Amount cannot have more than two decimal places.")
