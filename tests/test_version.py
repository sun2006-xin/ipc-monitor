import unittest

from core.version import APP_VERSION


class VersionTests(unittest.TestCase):
    def test_version_is_a_nonempty_release_style_string(self):
        self.assertRegex(APP_VERSION, r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


if __name__ == "__main__":
    unittest.main()
