import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from labeler import match_labels  # noqa: E402

RULES = {
    "tests": ["*.test.js", "test_*.py"],
    "docs": ["*.md", "docs/**"],
    "frontend": ["frontend/**", "*.tsx"],
}


def test_no_files_matches_nothing():
    assert match_labels([], RULES) == set()


def test_single_match():
    assert match_labels(["README.md"], RULES) == {"docs"}


def test_multiple_labels_one_file_set():
    files = ["frontend/App.tsx", "test_app.py", "README.md"]
    assert match_labels(files, RULES) == {"frontend", "tests", "docs"}


def test_unmatched_file_produces_no_label():
    assert match_labels(["random_notes.txt"], RULES) == set()


def test_nested_glob_matches():
    assert match_labels(["docs/guide/setup.md"], RULES) == {"docs", "docs"} or \
        match_labels(["docs/guide/setup.md"], RULES) == {"docs"}