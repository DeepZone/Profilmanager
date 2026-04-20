import unittest

from app import create_app


class UserRouteMethodsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()

    def test_me_route_allows_post(self):
        me_rule = next(rule for rule in self.app.url_map.iter_rules() if rule.endpoint == "users.me")

        self.assertIn("GET", me_rule.methods)
        self.assertIn("POST", me_rule.methods)


if __name__ == "__main__":
    unittest.main()
