"""Smoke test for the dev workshop (D116) - proves the local CI ladder runs.

This is NOT an invariant test; the 27 constitutional invariants become
failing tests in LOT 2 (D109 ladder). This file only asserts that (a) the
package imports and (b) the D70 reference tree exists, so `make test` and the
pre-push hook have a green, truthful baseline to build on.
"""

from _invariants import REPO_ROOT

import mnemosyne

# The versioned directories of the D70 reference tree. The derived stores
# (.vectorstore / .graphstore) are intentionally absent: they are gitignored
# and recreated at bootstrap (D94), never committed.
D70_TREE = (
    "system/config",
    "system/lib",
    "system/skills",
    "system/workflows",
    "system/logs",
    "knowledge/raw",
    "knowledge/distilled",
    "projects",
)


def test_package_imports():
    assert mnemosyne.__version__ == "0.0.0"


def test_d70_reference_tree_present():
    missing = [d for d in D70_TREE if not (REPO_ROOT / d).is_dir()]
    assert not missing, f"missing D70 tree directories: {missing}"


def test_governance_artefacts_present():
    # Only the artefacts this repository actually ships. The governance layer's own
    # documents are optional fixtures, deliberately not distributed with this template
    # (see tests/conftest.py), so asserting their presence here would be a guaranteed
    # failure rather than a control.
    for artefact in (
        "README.md",
        "system/config/oss_registry.md",
    ):
        assert (REPO_ROOT / artefact).is_file(), f"missing artefact: {artefact}"
