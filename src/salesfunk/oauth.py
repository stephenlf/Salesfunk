import os
import json
import threading
import webbrowser
import sys
from pathlib import Path
from flask import Flask, request, redirect, session
from requests_oauthlib import OAuth2Session
from getpass import getuser

# === Config ===
CLIENT_ID = os.getenv("SALESFORCE_CLIENT_ID")
REDIRECT_URI = "http://localhost:5000/callback"
AUTHORIZE_URL = "https://login.salesforce.com/services/oauth2/authorize"
TOKEN_URL = "https://login.salesforce.com/services/oauth2/token"
TOKEN_PATH = Path.home() / ".salesfunk" / f"token-{getuser()}.json"

# === Flask App ===
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret_key")

_oauth_session = None
_oauth_token = None
_shutdown_trigger = threading.Event()


@app.route("/login")
def login():
    global _oauth_session
    _oauth_session = OAuth2Session(
        CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        code_challenge_method="S256",  # Enables PKCE
    )
    authorization_url, state = _oauth_session.authorization_url(AUTHORIZE_URL)
    session["oauth_state"] = state
    print("🔑 Login here:", authorization_url)
    return redirect(authorization_url)


@app.route("/callback")
def callback():
    global _oauth_token
    sf = _oauth_session
    _oauth_token = sf.fetch_token(
        TOKEN_URL, authorization_response=request.url, include_client_id=True
    )

    _oauth_token = sf.fetch_token(
        TOKEN_URL,
        authorization_response=request.url,
        include_client_id=True,  # Required for PKCE
    )
    save_token(_oauth_token)
    _shutdown_trigger.set()
    return "Login complete! You can close this tab."

# === Entry Point for Main Thread ===
def run_oauth_flow():
    thread = threading.Thread(
        target=lambda: app.run(port=5000, debug=False, use_reloader=False)
    )
    thread.start()

    if not webbrowser.open(url="http://localhost:5000/login", new=1):
        print("⚠️ Could not open browser automatically. Please open the login URL manually:", file=sys.stderr)
        print("   http://localhost:5000/login", file=sys.stderr)
    _shutdown_trigger.wait()
    return _oauth_token or load_token()


# === Token Utilities ===
def save_token(token):
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        json.dump(token, f)

    os.chmod(TOKEN_PATH, 0o600)


def load_token():
    if TOKEN_PATH.exists():
        with open(TOKEN_PATH) as f:
            return json.load(f)
    return None


# def check_token_permissions():
#     if os.name != "nt":  # Unix-only
#         mode = os.stat(TOKEN_PATH).st_mode
#         if mode & 0o077:
#             print("⚠️ Token file permissions are too open. Consider running:")
#             print(f"   chmod 600 {TOKEN_PATH}")


def delete_token() -> bool:
    """
    Delete the salesforce session token.

    Returns:
        bool: `True` if the token existed, `False` if it didn't.
    """
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
        print("🧹 Token deleted successfully.")
    else:
        print("ℹ️ No token found to delete.")