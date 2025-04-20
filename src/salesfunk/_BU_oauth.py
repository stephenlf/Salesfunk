"""
An Oauth2.0 server
"""

import os
from flask import Flask, request, redirect, session, jsonify
from requests_oauthlib import OAuth2Session
import json
from pathlib import Path

# Salesforce App credentials
client_id = os.environ.get("SF_CLIENT_ID")
redirect_uri = "http://localhost:5000/callback"
default_base_uri = "https://test.salesforce.com/services/oauth2/authorize"
token_url = "https://test.salesforce.com/services/oauth2/token"
verify_url = "https://test.salesforce.com/services/oauth2/userinfo"

app = Flask(__name__)
app.secret_key = "123abcasdf12easdf1we"

_oauth_session = None
_oauth_token = None


@app.route("/login")
def login():
    """
    Query params:
    - uri (optional): the URL to sign into. Defaults to
    """
    global _oauth_session
    _oauth_session = OAuth2Session(
        client_id,
        redirect_uri=redirect_uri,
        code_challenge_method="S256",  # Enables PKCE
    )
    authorization_base_url = default_base_uri
    sf = _oauth_session.authorization_url(default_base_uri)
    authorization_url, state = sf.authorization_url(authorization_base_url)
    session["oauth_state"] = state
    print(f"{session['oauth_state']=}")
    return redirect(authorization_url)


@app.route("/callback")
def callback():
    global _oauth_token
    sf = _oauth_session
    _oauth_token = sf.fetch_token(
        token_url=token_url,
        authorization_response=request.url,
        include_client_id=True,  # For PKCE
    )

    # Save token securely
    save_token(token)
    return "Login complete"


TOKEN_PATH = Path.home() / ".salesfunk" / "token.json"


def save_token(token):
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        json.dump(token, f)


def load_token():
    with open(TOKEN_PATH) as f:
        return json.load(f)


app.run()
