"""The command line: `python -m cinecircle_analysis load | wipe | notebooks`.

Always the database in `DATABASE_URL`, which `load.py` insists is on this machine.
"""

import argparse
from pathlib import Path

from cinecircle_analysis.fakedata import generate
from cinecircle_analysis.load import NotLocal, count_rows, load, wipe
from cinecircle_api.db import make_engine
from cinecircle_api.settings import Settings

NOTEBOOKS_DIR = Path(__file__).resolve().parents[3] / "analysis"  # <repo>/analysis
TIMEOUT_SECONDS = 600


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cinecircle_analysis", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_ in (
        ("load", "replace the fake data in the local database"),
        ("notebooks", "load the fake data, then execute every analysis/*.ipynb in place"),
    ):
        command = commands.add_parser(name, help=help_)
        command.add_argument("--seed", type=int, default=7)
    commands.add_parser("wipe", help="remove the fake data from the local database")
    return parser


def execute_notebooks(directory: Path = NOTEBOOKS_DIR) -> list[Path]:
    """Run each notebook in `directory` top to bottom and save it with its outputs. The notebook
    packages only exist in the `analysis` dependency group, so they load only when needed."""
    paths = sorted(directory.glob("*.ipynb"))
    if not paths:
        print("no notebooks found")
        return []
    import nbformat
    from nbconvert.preprocessors import ExecutePreprocessor

    runner = ExecutePreprocessor(timeout=TIMEOUT_SECONDS, kernel_name="python3")
    for path in paths:
        print(f"running {path.name}")
        notebook = nbformat.read(path, as_version=4)
        runner.preprocess(notebook, {"metadata": {"path": str(path.parent)}})
        nbformat.write(notebook, path)
    return paths


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    engine = make_engine(Settings().database_url)
    try:
        if args.command == "wipe":
            wipe(engine)
            print("fake data removed")
            return 0
        counts = load(engine, generate(args.seed))
        print(f"fake data loaded (seed {args.seed}):")
        print(count_rows(counts.items()))
        if args.command == "notebooks":
            execute_notebooks()
        return 0
    except NotLocal as refused:
        print(refused)
        return 2
    finally:
        engine.dispose()
