import unittest

from app import create_app
from app.routes.gitlab_mr import (
    _collect_files_for_delete,
    _collect_main_profiles,
    _main_branch_request_flags,
    _merge_was_successful,
)
from app.forms import MainBranchActionForm, MainBranchDeletePathForm


class MergeStateTestCase(unittest.TestCase):
    def test_detects_merged_by_state(self):
        self.assertTrue(_merge_was_successful({"state": "merged"}))

    def test_detects_merged_by_timestamp(self):
        self.assertTrue(
            _merge_was_successful({"state": "opened", "merged_at": "2026-04-19T10:00:00Z"})
        )

    def test_detects_merged_by_commit_sha(self):
        self.assertTrue(_merge_was_successful({"state": "opened", "merge_commit_sha": "abc123"}))

    def test_non_merged_response(self):
        self.assertFalse(_merge_was_successful({"state": "opened"}))


class MainBranchProfileCollectionTestCase(unittest.TestCase):
    def test_collects_profiles_below_providers_prefix(self):
        tree_entries = [
            {"path": "README.md", "type": "blob"},
            {"path": "providers-049/provider-a", "type": "tree"},
            {"path": "providers-049/provider-a/providerprofile/p1.cfg", "type": "blob"},
            {"path": "providers-049/provider-a/gui_importe/a.export", "type": "blob"},
            {"path": "providers-043/provider-b/providerprofile/p2.cfg", "type": "blob"},
            {"path": "providers-043/provider-b/tr069_nachlader", "type": "tree"},
        ]

        result = _collect_main_profiles(tree_entries)

        self.assertEqual(2, len(result))
        self.assertEqual("providers-043/provider-b", result[0]["path"])
        self.assertEqual("043", result[0]["dial_code"])
        self.assertEqual("provider-b", result[0]["provider"])
        self.assertEqual(1, result[0]["file_count"])

        self.assertEqual("providers-049/provider-a", result[1]["path"])
        self.assertEqual(2, result[1]["file_count"])


class MainBranchDeleteCollectionTestCase(unittest.TestCase):
    def setUp(self):
        self.tree_entries = [
            {"path": "providers-049/provider-a", "type": "tree"},
            {"path": "providers-049/provider-a/providerprofile", "type": "tree"},
            {"path": "providers-049/provider-a/providerprofile/p1.cfg", "type": "blob"},
            {"path": "providers-049/provider-a/gui_importe/file.export", "type": "blob"},
            {"path": "README.md", "type": "blob"},
        ]

    def test_collects_single_file_for_blob(self):
        result = _collect_files_for_delete(self.tree_entries, "README.md", "blob")
        self.assertEqual(["README.md"], result)

    def test_collects_all_nested_files_for_tree(self):
        result = _collect_files_for_delete(self.tree_entries, "providers-049/provider-a", "tree")
        self.assertEqual(
            [
                "providers-049/provider-a/gui_importe/file.export",
                "providers-049/provider-a/providerprofile/p1.cfg",
            ],
            result,
        )

    def test_returns_empty_for_missing_path(self):
        result = _collect_files_for_delete(self.tree_entries, "providers-999/provider-x", "tree")
        self.assertEqual([], result)


class MainBranchFormDetectionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    def test_detects_delete_submission_without_submit_button_field(self):
        with self.app.test_request_context(
            "/merge-requests/main-branch",
            method="POST",
            data={
                "main_delete-project_id": "123",
                "main_delete-path": "providers-049/provider-a",
                "main_delete-entry_type": "tree",
            },
        ):
            form = MainBranchActionForm(prefix="main")
            delete_form = MainBranchDeletePathForm(prefix="main_delete")

            action_request, delete_request = _main_branch_request_flags(form, delete_form)

            self.assertFalse(action_request)
            self.assertTrue(delete_request)


if __name__ == "__main__":
    unittest.main()
