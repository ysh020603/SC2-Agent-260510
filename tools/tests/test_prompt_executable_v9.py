from SC2_Agent.human_skill_full_v9.agent import HumanSkillFullV9Agent
from SC2_Agent.human_skill_full_v9.prompt import contract_for_skill


def test_v9_preserves_branch_contract_and_adds_single_pass_guidance():
    terran = contract_for_skill("TvP_O02")
    zerg = contract_for_skill("ZvT_O04")
    assert "V4" in terran and "execution checks" in terran
    assert "positive/default adaptive graph" in zerg
    assert "one response" in terran and "one response" in zerg
    assert "not runtime rejection rules" in zerg


def test_v9_does_not_override_variant_rejection_hook():
    assert HumanSkillFullV9Agent._variant_decision_error is not None
    assert "return \"\"" in __import__("inspect").getsource(HumanSkillFullV9Agent._variant_decision_error)
