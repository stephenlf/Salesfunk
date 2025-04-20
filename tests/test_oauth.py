import os
import json
import pytest
from pytest import MonkeyPatch
from pathlib import Path
from salesfunk import oauth
from unittest.mock import patch

@pytest.fixture
def temp_token_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "token-test.json"
    monkeypatch.setattr(oauth, "TOKEN_PATH", path)
    return path


def test_save_and_load_token(temp_token_path):
    token = {"access_token": "abc123", "instance_url": "https://test.salesforce.com"}

    oauth.save_token(token)
    assert temp_token_path.exists()

    loaded = oauth.load_token()
    assert loaded == token


def test_delete_token(temp_token_path: Path):
    token = {"access_token": "abc123"}
    oauth.save_token(token)

    assert temp_token_path.exists()
    deleted = oauth.delete_token()
    assert temp_token_path.exists() is False or deleted is None

def test_run_oauth_flow_mocks_all(monkeypatch: MonkeyPatch):
    fake_token = {"access_token": "xyz", "instance_url": "https://test.salesforce.com"}
    
    monkeypatch.setattr(oauth, "_oauth_token", fake_token)
    monkeypatch.setattr(oauth._shutdown_trigger, "wait", lambda: None)
    
    with patch("salesfunk.oauth.threading.Thread.start") as mock_thread, \
        patch("salesfunk.oauth.webbrowser.open", return_value=True) as mock_browser:
            
        token = oauth.run_oauth_flow()
        
        mock_thread.assert_called_once()
        mock_browser.assert_called_once()
        assert token == fake_token

def test_run_oauth_flow_browser_open_returns_false(monkeypatch: MonkeyPatch, capsys):
    fake_token = {"access_token": "xyz", "instance_url": "https://test.salesforce.com"}
    
    monkeypatch.setattr(oauth, "_oauth_token", fake_token)
    monkeypatch.setattr(oauth._shutdown_trigger, "wait", lambda: None)
    
    with patch("salesfunk.oauth.threading.Thread.start") as mock_thread, \
        patch("salesfunk.oauth.webbrowser.open", return_value=False) as mock_browser:
            
        token = oauth.run_oauth_flow()
        
        mock_thread.assert_called_once()
        mock_browser.assert_called_once()
        assert token == fake_token
        captured = capsys.readouterr()

        assert token == fake_token
        assert "Could not open browser" in captured.err