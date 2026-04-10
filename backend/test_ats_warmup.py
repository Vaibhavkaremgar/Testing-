import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.ats_warmup import run_ats_warmup  # noqa: E402


class AtsWarmupTests(unittest.TestCase):
    def test_warmup_registers_layout_detection_component(self):
        state = run_ats_warmup(force=True)

        self.assertIn("layout_detection", state["components"])
        self.assertTrue(state["components"]["layout_detection"]["ok"])
        self.assertIn("details", state["components"]["layout_detection"])


if __name__ == "__main__":
    unittest.main()
