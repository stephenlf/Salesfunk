import os
import json
import pytest
from pytest import MonkeyPatch
from pathlib import Path
from salesfunk.oauth import OAuthFlow
from unittest.mock import patch


@pytest.fixture
def flow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    flow = OAuthFlow(
        instance_url="https://test.salesforce.com", port=5050, salesfunk_path=tmp_path
    )
    return flow


def test_save_and_load_token(flow: OAuthFlow):
    token = {"access_token": "abc123", "instance_url": "https://test.salesforce.com"}
    flow._save_token(token)

    assert flow.token_path.exists()

    loaded = flow._load_token()
    assert loaded == token


def test_delete_token(flow: OAuthFlow):
    token = {"access_token": "abc123"}
    flow._save_token(token)

    assert flow.token_path.exists()
    deleted = flow._delete_token()
    assert deleted is True
    assert not flow.token_path.exists()


def test_delete_token_when_none(flow: OAuthFlow):
    if flow.token_path.exists():
        flow.token_path.unlink()
    delete = flow._delete_token()
    assert delete == False


def test_run_mocked(flow: OAuthFlow):
    fake_token = {"access_token": "xyz", "instance_url": "https://test.salesforce.com"}
    flow._oauth_token = fake_token
    flow._shutdown_trigger.wait = lambda: None

    with (
        patch.object(flow, "_run") as mock_run,
        patch.object(flow, "_load_token") as mock_load,
    ):
        mock_load.return_value = False
        mock_run.return_value = fake_token
        token = flow.get_token()
        mock_load.assert_called_once()
        mock_run.assert_called_once()
        assert token == fake_token


def test_run_oauth_flow_browser_open_returns_false(flow: OAuthFlow, capsys):
    flow._oauth_token = {
        "access_token": "mock",
        "instance_url": "https://test.salesforce.com",
    }
    flow._shutdown_trigger.wait = lambda: None

    with patch("webbrowser.open", return_value=False), patch.object(flow._app, "run"):
        flow._run()
        captured = capsys.readouterr()
        assert "Could not open browser" in captured.err
