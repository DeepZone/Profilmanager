import unittest

from app.routes.gitlab_mr import _collect_main_profiles, _merge_was_successful


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


if __name__ == "__main__":
    unittest.main()
