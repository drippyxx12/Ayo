"""Offline specification consistency tests (not proof that integrations work)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_market_configuration_labels_unshipped_providers():
    cfg = json.loads((ROOT / "architecture/country_capabilities.json").read_text())
    assert cfg["release_status"] == "design_config_not_live_integration"
    assert cfg["markets"]["NG"]["currency"] == "NGN"
    assert cfg["markets"]["GH"]["currency"] == "GHS"
    for market in cfg["markets"].values():
        assert market["timezone_default"]
        for adapter in market.get("candidate_adapters", []):
            assert adapter["status"] not in ("connected", "live", "verified_live")

def test_no_real_write_capability_enabled_by_spec():
    cfg = json.loads((ROOT / "architecture/skill_registry.json").read_text())
    assert len({s["id"] for s in cfg["skills"]}) == len(cfg["skills"])
    for skill in cfg["skills"]:
        assert skill["status"] in {"planned", "alpha_mock_tests_only", "not_implemented_blocked"}
        if skill["mode"] == "write":
            assert skill["requires_merchant_approval"] is True
            assert skill["status"] == "not_implemented_blocked"

def test_draft_and_execution_are_different_routes():
    cfg = json.loads((ROOT / "architecture/specimen_api_contracts.json").read_text())
    paths={(e["method"],e["path"]) for e in cfg["endpoints"]}
    assert ("POST", "/leads/{id}/pitch-drafts") in paths
    assert ("POST", "/outreach/{id}/approve") in paths
    assert ("POST", "/outreach/{id}/execute") in paths
    assert cfg["status"] == "planning_contracts_not_live_api"

def test_founder_instructions_reachable():
    read_first=(ROOT/"START_CODEX_HERE.md").read_text()
    assert "Ayo is Ayo" in read_first
    for number in range(11,24):
        assert list((ROOT/"docs").glob(f"{number:02d}_*.md")), number


def test_founding_500_user_policy_is_all_features_free():
    policy = json.loads((ROOT / "architecture/founding_500_entitlements.json").read_text())
    assert policy["cap"] == 500
    assert policy["unit"] == "distinct_customer_user_account"
    assert policy["rule"] == "all_released_ayo_features_free"
    assert policy["premium_feature_gating_for_cohort"] is False
    assert policy["includes_future_released_features"] is True
    assert policy["feature_entitlement_requires_payment"] is False
    assert policy["count_separate_businesses_again"] is False
    assert policy["automatic_expiry_or_downgrade"] is False
    assert policy["state"] == "founder_confirmed_requirement_not_implemented"
