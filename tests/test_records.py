"""Run records keep a stable id when the clock is fixed."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from lunri.fixture import load_cases
from lunri.records import run_id_for, write_record
from lunri.run import execute_case


class RecordTests(unittest.TestCase):
    def test_same_clock_writes_the_same_bytes(self) -> None:
        case = next(item for item in load_cases() if item["id"] == "syn-001")
        moment = datetime(2026, 11, 18, 17, 0, tzinfo=timezone.utc)
        first = execute_case(case, created_at=moment)
        second = execute_case(case, created_at=moment)
        self.assertEqual(first, second)
        self.assertEqual(first["response_label"], "SIMULATED")
        self.assertEqual(first["energy"]["label"], "SIMULATED")
        self.assertIsNone(first["energy"]["joules"])
        self.assertFalse(first["benchmark"])
        self.assertEqual(run_id_for("mock-deterministic", case["raw"]), first["run_id"])
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path_a = write_record(directory, first)
            path_b = write_record(directory, second)
            self.assertEqual(path_a.read_bytes(), path_b.read_bytes())


if __name__ == "__main__":
    unittest.main()
