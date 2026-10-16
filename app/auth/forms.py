from flask_wtf import FlaskForm
from wtforms import DateField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError

from app.models import User


class RegistrationForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=254)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=12, max=128)])
    confirm_password = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password")])
    date_of_birth = DateField("Date of birth", validators=[Optional()])
    preferred_currency = SelectField("Preferred currency", choices=[("LKR", "LKR"), ("USD", "USD"), ("EUR", "EUR"), ("GBP", "GBP")])
    submit = SubmitField("Create account")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("An account with this email already exists.")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")


class ProfileForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    date_of_birth = DateField("Date of birth", validators=[Optional()])
    preferred_currency = SelectField("Preferred currency", choices=[("LKR", "LKR"), ("USD", "USD"), ("EUR", "EUR"), ("GBP", "GBP")])
    submit = SubmitField("Save profile")


class PasswordResetRequestForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send reset link")


class PasswordResetForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), Length(min=12, max=128)])
    confirm_password = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Reset password")
