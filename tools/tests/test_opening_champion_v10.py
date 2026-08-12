from SC2_Agent.human_skill_full_v10.prompt import V3_CONTRACT, V4_CONTRACT, contract_for_skill


def test_v10_keeps_race_native_contracts():
    assert contract_for_skill("TvP_O02") == V4_CONTRACT
    assert contract_for_skill("PvP_O01") == V4_CONTRACT
    assert contract_for_skill("ZvT_O04") == V3_CONTRACT
