import unittest

from app.routes.gitlab_mr import _merge_was_successful


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


if __name__ == "__main__":
    unittest.main()
