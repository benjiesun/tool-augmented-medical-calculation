import contextlib
import io
import sys
import unittest
from unittest.mock import MagicMock, patch

from toolmed_agent import pipeline


class PipelineCliTests(unittest.TestCase):
    def test_hyphenated_start_row_is_forwarded(self):
        host = MagicMock()
        host.run_dataset.return_value = {"summary": {}}
        argv = [
            "toolmed-run",
            "--root-dir",
            ".",
            "--env-file",
            "example.env",
            "--limit",
            "2",
            "--start-row",
            "7",
        ]
        with (
            patch.object(sys, "argv", argv),
            patch.object(pipeline, "load_env_file") as load_env,
            patch.object(pipeline, "CentralHost", return_value=host),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            pipeline.main()

        load_env.assert_called_once_with("example.env")
        host.run_dataset.assert_called_once_with(limit=2, start_row=7)

    def test_underscore_start_row_alias_is_supported(self):
        host = MagicMock()
        host.run_dataset.return_value = {"summary": {}}
        argv = ["toolmed-run", "--start_row", "9"]
        with (
            patch.object(sys, "argv", argv),
            patch.object(pipeline, "load_env_file"),
            patch.object(pipeline, "CentralHost", return_value=host),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            pipeline.main()

        host.run_dataset.assert_called_once_with(limit=0, start_row=9)


if __name__ == "__main__":
    unittest.main()
