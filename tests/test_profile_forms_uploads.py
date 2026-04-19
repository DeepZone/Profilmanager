import io
import os
import unittest

from werkzeug.datastructures import FileStorage, MultiDict

os.environ["DATABASE_URL"] = "sqlite:///test_profile_forms_uploads.db"
os.environ["SECRET_KEY"] = "test-secret"

from app import create_app
from app.forms import ProfileEditForm, ProfileForm


class ProfileUploadFormsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def _build_upload(self, filename: str) -> FileStorage:
        return FileStorage(stream=io.BytesIO(b"dummy"), filename=filename, content_type="application/octet-stream")

    def _profile_form(self, uploads: list[FileStorage]) -> ProfileForm:
        form = ProfileForm(
            formdata=MultiDict(
                {
                    "name": "Testprofil",
                    "provider": "Provider",
                    "country_code": "DE",
                    "upload": uploads,
                }
            ),
            meta={"csrf": False},
        )
        return form

    def _profile_edit_form(self, uploads: list[FileStorage]) -> ProfileEditForm:
        form = ProfileEditForm(
            formdata=MultiDict(
                {
                    "provider": "Provider",
                    "country_code": "DE",
                    "upload": uploads,
                }
            ),
            meta={"csrf": False},
        )
        return form

    def test_profile_form_accepts_tar_and_export_together(self):
        form = self._profile_form([self._build_upload("foo.tar"), self._build_upload("bar.export")])
        self.assertTrue(form.validate())

    def test_profile_form_rejects_other_extensions(self):
        form = self._profile_form([self._build_upload("foo.zip")])
        self.assertFalse(form.validate())
        self.assertIn("Nur .tar- oder .export-Dateien erlaubt", form.upload.errors[0])

    def test_profile_edit_form_accepts_multiple_files(self):
        form = self._profile_edit_form([self._build_upload("foo.tar"), self._build_upload("bar.export")])
        self.assertTrue(form.validate())


if __name__ == "__main__":
    unittest.main()
