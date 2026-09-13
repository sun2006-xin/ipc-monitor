import pathlib
import unittest


class BuildPrivacyTests(unittest.TestCase):
    def test_build_does_not_bundle_user_data_or_release_only_files(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        script = (root / "build_exe.ps1").read_text(encoding="utf-8-sig")

        forbidden = (
            "data;data",
            "best.pt;.",
            "docs;docs",
            "README.md;.",
            "OPENSOURCE_GUIDE.md;.",
        )
        for value in forbidden:
            self.assertNotIn(value, script)


if __name__ == "__main__":
    unittest.main()
