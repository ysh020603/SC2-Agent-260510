from SC2_Agent.human_skill_full_v7.prompt import V3_CONTRACT, V4_CONTRACT, contract_for_skill


def test_v7_preserves_native_contract_per_branch():
    assert contract_for_skill("PvP_O01") == V4_CONTRACT
    assert contract_for_skill("TvZ_O05") == V4_CONTRACT
    assert contract_for_skill("PvT_O03") == V3_CONTRACT
    assert contract_for_skill("ZvT_O04") == V3_CONTRACT
