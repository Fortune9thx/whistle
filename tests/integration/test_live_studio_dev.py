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

NOTE: this file has not yet been executed against a real network in this
account's session (no funded DEPLOYER_PRIVATE_KEY was available) -- do
not treat its mere existence/apparent-correctness as proof it runs
cleanly (see genlayer-test-toolchain memory: get_contract_factory is a
plain importable function, not a pytest fixture, is a previously
documented recurring mistake on this account, caught here on review
before ever being run).
"""
import os
import time

import pytest
from gltest import get_contract_factory

pytestmark = pytest.mark.integration

TREASURY = os.environ.get("TREASURY_ADDRESS", "0xC6E6d3b2acCaECeCeB40Ad4bD3dF123DDCB4e537")


def _assert_succeeded(receipt) -> None:
    # Never trust gltest's own tx_execution_succeeded()/status.name helpers
    # alone -- check the raw execution-result field directly (a real
    # Bradbury/Studio receipt shape may not populate what those helpers
    # expect). Whitelist the one known-good value; anything else,
    # including a missing field, is a failure.
    result_name = receipt.get("tx_execution_result_name") or receipt.get("txExecutionResultName")
    assert result_name == "FINISHED_WITH_RETURN", f"write did not succeed: {receipt}"


def test_deploy_create_fixture_place_bet_live(accounts):
    factory = get_contract_factory("Whistle")
    contract = factory.deploy(args=[TREASURY])

    creator = accounts[0]
    kickoff = int(time.time()) + 7200 + 3600

    receipt = contract.connect(creator).create_fixture(
        "integration-smoke-1", "Home FC", "Away FC", kickoff, value=5 * 10**16
    ).transact()
    _assert_succeeded(receipt)

    fixture = contract.get_fixture("integration-smoke-1").call()
    assert fixture["state"] == "OPEN"
    assert fixture["kickoff_unix"] == kickoff

    bettor = accounts[1]
    bet_receipt = contract.connect(bettor).place_bet("integration-smoke-1", "HOME", value=10**18).transact()
    _assert_succeeded(bet_receipt)

    position = contract.get_position("integration-smoke-1", bettor.address).call()
    assert position["outcome"] == "HOME"
    assert position["amount"] == 10**18
