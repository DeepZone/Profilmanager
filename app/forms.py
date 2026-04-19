from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    BooleanField,
    HiddenField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional


class LoginForm(FlaskForm):
    username = StringField("Benutzername", validators=[DataRequired()])
    password = PasswordField("Passwort", validators=[DataRequired()])
    submit = SubmitField("Anmelden")


class UserForm(FlaskForm):
    username = StringField("Benutzername", validators=[DataRequired(), Length(max=80)])
    email = StringField("E-Mail", validators=[DataRequired(), Email(), Length(max=120)])
    role = SelectField("Rolle", choices=[("User", "User"), ("Admin", "Admin")])
    password = PasswordField("Passwort", validators=[Optional(), Length(min=8, max=128)])
    active = BooleanField("Aktiv", default=True)
    submit = SubmitField("Speichern")


class ProfileForm(FlaskForm):
    name = StringField("Profilname", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Beschreibung", validators=[Optional()])
    comment = TextAreaField("Kommentar", validators=[Optional()])
    upload = FileField(
        "Profildatei (.tar)",
        validators=[FileRequired(), FileAllowed(["tar"], "Nur .tar-Dateien erlaubt")],
    )
    submit = SubmitField("Hochladen")


class ProfileEditForm(FlaskForm):
    description = TextAreaField("Beschreibung", validators=[Optional()])
    comment = TextAreaField("Kommentar", validators=[Optional()])
    upload = FileField(
        "Neue Version (.tar)",
        validators=[Optional(), FileAllowed(["tar"], "Nur .tar-Dateien erlaubt")],
    )
    submit = SubmitField("Aktualisieren")


class GitLabConfigForm(FlaskForm):
    gitlab_url = StringField("GitLab URL", validators=[DataRequired(), Length(max=255)])
    gitlab_token = PasswordField("API Token", validators=[Optional(), Length(max=255)])
    gitlab_project_id = StringField(
        "Standard Projekt-ID", validators=[Optional(), Length(max=50)]
    )
    submit = SubmitField("Konfiguration speichern")


class AppVersionMajorForm(FlaskForm):
    major = IntegerField("Hauptversion (MAJOR)", validators=[DataRequired(), NumberRange(min=0)])
    submit_major = SubmitField("Hauptversion setzen")


class AppVersionMinorForm(FlaskForm):
    minor = IntegerField("Subversion (MINOR)", validators=[DataRequired(), NumberRange(min=0)])
    submit_minor = SubmitField("Subversion setzen")


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
