from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_profile import REQUIRED_HEADINGS, validate


class ProfileContractTests(unittest.TestCase):
    def test_repository_readme_passes(self) -> None:
        self.assertEqual(validate(Path(__file__).resolve().parents[1] / "README.md"), [])

    def test_missing_heading_and_broken_local_link_fail(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            readme = Path(raw_root) / "README.md"
            readme.write_text(
                "\n\n".join([*REQUIRED_HEADINGS[:-1], "[missing](missing.md)"]) + "\n",
                encoding="utf-8",
            )

            errors = validate(readme)

        self.assertIn("missing heading: ## Stack", errors)
        self.assertIn("invalid local link: missing.md", errors)


if __name__ == "__main__":
    unittest.main()
