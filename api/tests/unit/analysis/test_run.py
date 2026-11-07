"""The CLI: `notebooks` is a no-op until notebooks exist, and then needs no analysis packages."""

import sys

from cinecircle_analysis import run


def test_no_notebooks_found(tmp_path, capsys):
    assert run.execute_notebooks(tmp_path) == []
    assert "no notebooks found" in capsys.readouterr().out
    assert "nbconvert" not in sys.modules  # imported lazily, only when there is a notebook


def test_parser_commands():
    parser = run.build_parser()
    assert parser.parse_args(["load"]).seed == 7
    assert parser.parse_args(["load", "--seed", "9"]).seed == 9
    assert parser.parse_args(["wipe"]).command == "wipe"
    assert parser.parse_args(["notebooks"]).command == "notebooks"
