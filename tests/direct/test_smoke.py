from conftest import CONTRACT_PATH, TREASURY_HEX


def test_deploy_and_read_config(direct_deploy):
    contract = direct_deploy(CONTRACT_PATH, TREASURY_HEX)
    config = contract.get_config()
    assert config["fee_bps"] == 200
    assert config["competition"] == "UCL_LP"
    assert config["result_type"] == "FT_90"
    assert config["market"] == "1X2"
    assert config["treasury"].lower() == TREASURY_HEX.lower()
    assert config["total_fixtures"] == 0
