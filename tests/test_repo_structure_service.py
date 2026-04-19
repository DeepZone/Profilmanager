import unittest

from app.services.repo_structure_service import (
    build_branch_name,
    build_repo_paths,
    normalize_dial_code,
)


class RepoStructureServiceTestCase(unittest.TestCase):
    def test_normalize_dial_code(self):
        self.assertEqual(normalize_dial_code("+41"), "041")
        self.assertEqual(normalize_dial_code("49"), "049")
        self.assertEqual(normalize_dial_code("041"), "041")

    def test_build_branch_name(self):
        self.assertEqual(
            build_branch_name("ABC", "+49", "Telekom DE"),
            "abc_049_telekom-de",
        )

    def test_build_repo_paths(self):
        paths = build_repo_paths("+41", "Provider/CH", "profile_v1.tar")
        self.assertEqual(paths["base"], "providers-041/Provider-CH")
        self.assertEqual(
            paths["tar_path"],
            "providers-041/Provider-CH/providerprofile/profile_v1.tar",
        )


if __name__ == "__main__":
    unittest.main()
