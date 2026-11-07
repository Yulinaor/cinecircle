"""The CLI: `notebooks` is a no-op until notebooks exist, and then needs no analysis packages."""

import sys

import pytest

from cinecircle_analysis import run
from cinecircle_analysis.load import FakeTitleInUse


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


def _no_engine(monkeypatch):
    """Fail the test if the CLI makes an engine, runs the loader or executes notebooks."""

    def boom(*args, **kwargs):
        raise AssertionError("the CLI touched the database")

    monkeypatch.setattr(run, "make_engine", boom)
    monkeypatch.setattr(run, "load", boom)
    monkeypatch.setattr(run, "wipe", boom)
    monkeypatch.setattr(run, "execute_notebooks", boom)


@pytest.mark.parametrize("app_env", ["production", "test"])
@pytest.mark.parametrize("command", ["load", "wipe", "notebooks"])
def test_refuses_unless_app_env_is_local(command, app_env, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://postgres:x@127.0.0.1:55322/postgres")
    monkeypatch.setenv("APP_ENV", app_env)
    _no_engine(monkeypatch)
    assert run.main([command]) == 2
    out = capsys.readouterr().out
    assert "APP_ENV" in out
    assert "local" in out


def test_runs_when_app_env_is_local(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://postgres:x@127.0.0.1:55322/postgres")
    monkeypatch.setenv("APP_ENV", "local")
    calls = []

    class Engine:
        def dispose(self):
            calls.append("dispose")

    monkeypatch.setattr(run, "make_engine", lambda url: Engine())
    monkeypatch.setattr(run, "wipe", lambda engine: calls.append("wipe"))
    assert run.main(["wipe"]) == 0
    assert calls == ["wipe", "dispose"]
    assert "fake data removed" in capsys.readouterr().out


def test_a_blocked_wipe_prints_why_and_exits_2(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://postgres:x@127.0.0.1:55322/postgres")
    monkeypatch.setenv("APP_ENV", "local")

    class Engine:
        def dispose(self):
            pass

    def blocked(engine):
        raise FakeTitleInUse("2 post(s) of real accounts reference fake titles")

    monkeypatch.setattr(run, "make_engine", lambda url: Engine())
    monkeypatch.setattr(run, "wipe", blocked)
    assert run.main(["wipe"]) == 2
    assert "2 post(s) of real accounts" in capsys.readouterr().out
