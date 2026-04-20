from flask_login import current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, MultipleFileField
from wtforms import (
    BooleanField,
    HiddenField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Optional,
    Regexp,
    ValidationError,
)

from app.constants.european_countries import european_dial_code_choices
from app.models import User


class LoginForm(FlaskForm):
    username = StringField("Benutzername", validators=[DataRequired()])
    password = PasswordField("Passwort", validators=[DataRequired()])
    submit = SubmitField("Anmelden")




class ForgotPasswordForm(FlaskForm):
    email = StringField("E-Mail", validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField("Reset-Link senden")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("Neues Passwort", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Neues Passwort bestätigen",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwörter stimmen nicht überein"),
        ],
    )
    submit = SubmitField("Passwort zurücksetzen")

class UserForm(FlaskForm):
    username = StringField("Benutzername", validators=[DataRequired(), Length(max=80)])
    email = StringField("E-Mail", validators=[DataRequired(), Email(), Length(max=120)])
    shortcode = StringField(
        "Persönliches Benutzerkürzel",
        validators=[
            DataRequired(),
            Length(min=3, max=3),
            Regexp(r"^[A-Za-z]{3}$", message="Kürzel muss aus genau 3 Buchstaben (A-Z) bestehen"),
        ],
    )
    role = SelectField("Rolle", choices=[("User", "User"), ("Admin", "Admin")])
    password = PasswordField("Passwort", validators=[Optional(), Length(min=8, max=128)])
    active = BooleanField("Aktiv", default=True)
    submit = SubmitField("Speichern")

    def validate_shortcode(self, field):
        normalized_shortcode = (field.data or "").strip().upper()
        field.data = normalized_shortcode

        if len(normalized_shortcode) != 3 or not normalized_shortcode.isalpha():
            raise ValidationError("Kürzel muss aus genau 3 Buchstaben (A-Z) bestehen")

        query = User.query.filter(User.shortcode == normalized_shortcode)
        if getattr(self, "user_id", None):
            query = query.filter(User.id != self.user_id)

        if query.first():
            raise ValidationError("Dieses Kürzel ist bereits vergeben")


class SelfProfileForm(FlaskForm):
    username = StringField("Benutzername", validators=[DataRequired(), Length(max=80)])
    email = StringField("E-Mail", validators=[DataRequired(), Email(), Length(max=120)])
    shortcode = StringField("Persönliches Benutzerkürzel")
    gitlab_token = PasswordField("GitLab API Token", validators=[Optional(), Length(max=255)])
    current_password = PasswordField("Aktuelles Passwort", validators=[Optional(), Length(min=8, max=128)])
    new_password = PasswordField("Neues Passwort", validators=[Optional(), Length(min=8, max=128)])
    confirm_new_password = PasswordField(
        "Neues Passwort bestätigen",
        validators=[Optional(), EqualTo("new_password", message="Passwörter stimmen nicht überein")],
    )
    submit = SubmitField("Speichern")

    def validate_shortcode(self, field):
        if not current_user.is_admin:
            return

        normalized_shortcode = (field.data or "").strip().upper()
        field.data = normalized_shortcode

        if normalized_shortcode and (len(normalized_shortcode) != 3 or not normalized_shortcode.isalpha()):
            raise ValidationError("Kürzel muss aus genau 3 Buchstaben (A-Z) bestehen")

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        password_fields = [
            self.current_password.data,
            self.new_password.data,
            self.confirm_new_password.data,
        ]
        password_change_requested = any(bool((value or "").strip()) for value in password_fields)

        if password_change_requested:
            if not (self.current_password.data or "").strip():
                self.current_password.errors.append("Bitte aktuelles Passwort eingeben.")
                return False
            if not (self.new_password.data or "").strip():
                self.new_password.errors.append("Bitte neues Passwort eingeben.")
                return False
            if not (self.confirm_new_password.data or "").strip():
                self.confirm_new_password.errors.append("Bitte Passwort-Bestätigung eingeben.")
                return False

        return True


class ProfileForm(FlaskForm):
    name = StringField("Profilname", validators=[DataRequired(), Length(max=200)])
    provider = StringField("Provider", validators=[DataRequired(), Length(max=120)])
    country_code = SelectField(
        "Landesvorwahl",
        choices=european_dial_code_choices(),
        validators=[DataRequired(message="Bitte eine Landesvorwahl auswählen")],
    )
    description = TextAreaField("Beschreibung", validators=[Optional()])
    comment = TextAreaField("Kommentar", validators=[Optional()])
    upload = MultipleFileField("Profildateien (.tar, .export)")
    create_mr = BooleanField("Nach Upload direkt Merge Request erstellen", default=False)
    submit = SubmitField("Hochladen")

    def validate_upload(self, field):
        files = [file for file in (field.data or []) if getattr(file, "filename", "")]
        if not files:
            raise ValidationError("Bitte mindestens eine .tar- oder .export-Datei auswählen")

        for file in files:
            suffix = (file.filename.rsplit(".", 1)[-1] or "").lower() if "." in file.filename else ""
            if suffix not in {"tar", "export"}:
                raise ValidationError("Nur .tar- oder .export-Dateien erlaubt")


class ProfileEditForm(FlaskForm):
    provider = StringField("Provider", validators=[DataRequired(), Length(max=120)])
    country_code = SelectField(
        "Landesvorwahl",
        choices=european_dial_code_choices(),
        validators=[DataRequired(message="Bitte eine Landesvorwahl auswählen")],
    )
    description = TextAreaField("Beschreibung", validators=[Optional()])
    comment = TextAreaField("Kommentar", validators=[Optional()])
    upload = MultipleFileField("Neue Version(en) (.tar, .export)", validators=[Optional()])
    submit = SubmitField("Aktualisieren")

    def validate_upload(self, field):
        files = [file for file in (field.data or []) if getattr(file, "filename", "")]
        for file in files:
            suffix = (file.filename.rsplit(".", 1)[-1] or "").lower() if "." in file.filename else ""
            if suffix not in {"tar", "export"}:
                raise ValidationError("Nur .tar- oder .export-Dateien erlaubt")


class GitLabConfigForm(FlaskForm):
    gitlab_url = StringField("GitLab URL", validators=[DataRequired(), Length(max=255)])
    gitlab_project_id = StringField(
        "Standard Projekt-ID", validators=[Optional(), Length(max=50)]
    )
    submit = SubmitField("Konfiguration speichern")


class PushToGitLabForm(FlaskForm):
    profile_file_id = HiddenField(validators=[DataRequired()])
    branch_name = StringField("Branch Name", validators=[DataRequired(), Length(max=255)])
    target_branch = StringField("Target Branch", validators=[DataRequired()], default="main")
    commit_message = StringField("Commit Message", validators=[DataRequired(), Length(max=255)])
    mr_title = StringField("MR Titel", validators=[DataRequired(), Length(max=255)])
    project_id = StringField("Projekt-ID", validators=[Optional(), Length(max=50)])
    submit = SubmitField("Push & Merge Request")


class MergeActionForm(FlaskForm):
    squash = BooleanField("Squash beim Merge", default=False)
    submit = SubmitField("Merge ausführen")


class DeleteMergeRequestForm(FlaskForm):
    submit = SubmitField("Merge Request löschen")


class MainBranchActionForm(FlaskForm):
    action = HiddenField(validators=[DataRequired()])
    project_id = HiddenField(validators=[DataRequired()])
    mr_iid = HiddenField(validators=[DataRequired()])
    submit = SubmitField("Ausführen")


class MainBranchDeletePathForm(FlaskForm):
    project_id = HiddenField(validators=[DataRequired()])
    path = HiddenField(validators=[DataRequired()])
    entry_type = HiddenField(validators=[DataRequired()])
    submit = SubmitField("Löschen")
