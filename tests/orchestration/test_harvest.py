"""The harvest contract must carry what makes it different from "read the project and tell me".

Its whole value is in three properties. Each has a test that goes red if the property is dropped:
recruiting DOMAIN experts (not just code readers), ruling with a verdict that includes DUPLICATE,
and promoting nothing.
"""

from __future__ import annotations

import pytest

from mnemosyne.production.harvest import (
    HARVEST_VERDICTS,
    HarvestError,
    build_harvest_contract,
    known_projects,
)
from mnemosyne.runtime.harvest_run import main as harvest_main


def _flat(text: str) -> str:
    """The contract is wrapped for reading; search it flattened or match nothing."""
    return " ".join(text.split())


class TestTheContractRecruitsDomainExperts:
    """The point the operator made: an agent that only reads code judges what is well WRITTEN,
    never what is well THOUGHT. A macro rule needs someone who knows macro."""

    def test_a_harvest_without_a_domain_expert_is_refused(self) -> None:
        with pytest.raises(HarvestError, match="domain expert"):
            build_harvest_contract("projects/x", domain_agents=0)

    def test_the_contract_asks_for_BOTH_families(self) -> None:
        contract = build_harvest_contract("projects/x", domain_agents=4, mechanic_agents=2)
        assert "DOMAIN EXPERTS (at least 4)" in contract
        assert "MECHANICAL READERS (at least 2)" in contract
        assert "BOTH are required" in contract

    def test_the_orchestrator_is_told_NOT_to_judge_alone(self) -> None:
        contract = build_harvest_contract("projects/x")
        assert "is NOT to read this project yourself" in contract
        assert "RECRUIT" in contract

    def test_the_floors_are_floors_not_targets(self) -> None:
        """A number frozen in prose gets obeyed as a ceiling."""
        assert "at least 5" in build_harvest_contract("projects/x", domain_agents=5)


class TestTheFourVerdicts:
    def test_every_verdict_reaches_the_contract(self) -> None:
        contract = build_harvest_contract("projects/x")
        for verdict in HARVEST_VERDICTS:
            assert verdict.name in contract
            assert verdict.meaning[:40] in contract

    def test_DOUBLON_exists_and_is_named_the_most_useful(self) -> None:
        """Measured on another project: a whole secret-broker rebuilt from scratch while Mnemosyne's own sat
        four lines away in a file the project already imported. Nobody looks for this verdict."""
        contract = build_harvest_contract("projects/x")
        assert "DUPLICATE" in contract
        assert "MOST USEFUL" in contract

    def test_the_workflow_skill_distinction_is_carried_with_an_EMPIRICAL_criterion(self) -> None:
        """Whitespace is flattened before searching: the contract is wrapped, so a phrase that
        reads as one sentence spans two lines. Searching the raw text finds nothing and the test
        passes for the wrong reason — a pattern this repo has paid for five times."""
        contract = _flat(build_harvest_contract("projects/x"))
        assert "WORKFLOW = a TOOL" in contract
        assert "SKILL = a CAPABILITY" in contract
        assert "reinvented the same piece of code, the capability must become a tool" in contract


class TestTheHarvestPromotesNothing:
    def test_candidates_stay_inert_and_must_be_tried(self) -> None:
        contract = build_harvest_contract("projects/x")
        assert "You promote NOTHING" in contract
        assert "INERT PROPOSAL" in contract
        assert "make skill-eprouver" in contract

    def test_the_contract_asks_for_the_REJECTION_rate_not_a_target_count(self) -> None:
        """Asking for N candidates manufactures N candidates — a cause this repo has paid for."""
        contract = build_harvest_contract("projects/x")
        contract = _flat(contract)
        assert "the count REJECTED" in contract
        assert "Do not aim for ANY number of candidates kept" in contract
        assert "low rejection rate is a warning sign" in contract

    def test_the_producer_does_not_judge_its_own_candidate(self) -> None:
        flat = _flat(build_harvest_contract("projects/x"))
        assert "The agent that FINDS a piece is never the one who rules" in flat


class TestTheSurface:
    def test_an_unknown_project_is_refused_and_the_real_ones_are_listed(self, tmp_path, capsys) -> None:
        (tmp_path / "projects" / "saas" / "un-projet").mkdir(parents=True)
        assert harvest_main(["--projet", "projects/saas/absent", "--racine", str(tmp_path)]) == 2
        assert "projects/saas/un-projet" in capsys.readouterr().err

    def test_a_real_project_emits_the_contract(self, tmp_path, capsys) -> None:
        (tmp_path / "projects" / "saas" / "un-projet").mkdir(parents=True)
        assert harvest_main(["--projet", "projects/saas/un-projet", "--racine", str(tmp_path)]) == 0
        assert "PROJECT HARVEST" in capsys.readouterr().out

    def test_known_projects_reads_the_real_tree(self, tmp_path) -> None:
        (tmp_path / "projects" / "saas" / "a").mkdir(parents=True)
        (tmp_path / "projects" / "trading" / "b").mkdir(parents=True)
        assert known_projects(tmp_path) == ("projects/saas/a", "projects/trading/b")
        assert known_projects(tmp_path / "vide") == ()


class TestKnownProjectsExclutLeCache:
    """ BOTH LEVELS, AND THAT IS A MEASURED FAILURE, NOT A PRECAUTION.

 On 2026-09-08, the tick's `I2` source named **36 closed arcs all living inside throwaway
 mutation copies** (`projects/saas/.repo-layout-mutations-*`), burying the real arcs of that project.
 Measured that day: **51 directories enumerated, 16 hidden**, including `projects/.git/objects`
 and `projects/.git/refs` — the git store itself was being offered as a project bubble.

 The author of `_moisson_due` had WRITTEN DOWN this failure mode on 2026-08-15: *"none of
 them carries an arc, so none enters the population — but that is a property of their CONTENT,
 not a guarantee from the enumerator"*. 24 days later, the content changed. *A limit that
 depends on today's content is not a guarantee.*

 **TWO WITNESSES, ONE PER LEVEL**: the first draft of the fix could have filtered only one
 of the two, and the real noise showed up at BOTH (`projects/.git/` is a hidden family,
 `projects/saas/.repo-layout-*` a hidden bubble). *Checking one value does not protect the
 site that uses another.*
 """

    def test_une_FAMILLE_cachee_n_est_jamais_une_bulle(self, tmp_path) -> None:
        (tmp_path / "projects" / ".git" / "objects").mkdir(parents=True)
        (tmp_path / "projects" / "saas" / "vrai").mkdir(parents=True)
        assert known_projects(tmp_path) == ("projects/saas/vrai",)

    def test_une_BULLE_cachee_n_est_jamais_une_bulle(self, tmp_path) -> None:
        (tmp_path / "projects" / "saas" / ".repo-layout-mutations-abc123").mkdir(parents=True)
        (tmp_path / "projects" / "saas" / ".venv-local").mkdir(parents=True)
        (tmp_path / "projects" / "saas" / "vrai").mkdir(parents=True)
        assert known_projects(tmp_path) == ("projects/saas/vrai",)

    def test_le_cas_PASSANT_survit_au_filtre(self, tmp_path) -> None:
        """ Without it, an enumerator that ALWAYS returned () would pass the two witnesses
 above. *I never assert only the refusing case.*"""
        (tmp_path / "projects" / "saas" / "a").mkdir(parents=True)
        (tmp_path / "projects" / "trading" / "b").mkdir(parents=True)
        assert known_projects(tmp_path) == ("projects/saas/a", "projects/trading/b")
