from __future__ import annotations

import unittest


class CliSeamTests(unittest.TestCase):
    def test_core_and_solver_are_library_modules_without_argparse_entrypoints(self) -> None:
        from formation_graphics import core, solver

        self.assertFalse(hasattr(core, "parse_args"))
        self.assertFalse(hasattr(solver, "parse_args"))


if __name__ == "__main__":
    unittest.main()
