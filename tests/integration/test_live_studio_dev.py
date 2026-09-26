"""
Live Studio Next integration test. See tests/integration/README.md for
prerequisites -- run with `gltest tests/integration -v`, never plain
pytest (no RPC endpoint configured for direct-mode).

Deploys a fresh Whistle instance, creates one fixture with a near-future
kickoff, places one bet, and confirms the deploy + write path reaches a
real, queryable on-chain state. It deliberately does NOT try to exercise
resolve() against real desk data within the test's own runtime -- a real
match's kickoff + 105 minutes is not something a CI-less, on-demand test
run can wait for. Use a real fixture id with a kickoff already in the
past (RESOLVE_EARLIEST_OFFSET-elapsed) and manually call resolve()
against a live deployment for that end-to-end check instead.
"""
import os

import pytest

pytestmark = pytest.mark.integration

TREASURY = os.environ.get("TREASURY_ADDRESS", "0xC6E6d3b2acCaECeCeB40Ad4bD3dF123DDCB4e537")


def test_deploy_create_fixture_place_bet_live(get_contract_factory, accounts):
    import time

    factory = get_contract_factory("Whistle")
    contract = factory.deploy(args=[TREASURY])

    creator = accounts[0]
    kickoff = int(time.time()) + 7200 + 3600

    tx = contract.connect(creator).create_fixture(
        "integration-smoke-1", "Home FC", "Away FC", kickoff, value=5 * 10**16
    )
    assert tx.status.name in ("ACCEPTED", "FINALIZED")

    fixture = contract.get_fixture("integration-smoke-1")
    assert fixture["state"] == "OPEN"
    assert fixture["kickoff_unix"] == kickoff

    bettor = accounts[1]
    bet_tx = contract.connect(bettor).place_bet("integration-smoke-1", "HOME", value=10**18)
    assert bet_tx.status.name in ("ACCEPTED", "FINALIZED")

    position = contract.get_position("integration-smoke-1", bettor.address)
    assert position["outcome"] == "HOME"
    assert position["amount"] == 10**18
