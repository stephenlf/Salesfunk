import os
import json
import threading
import webbrowser
import sys
import logging
import dotenv
import requests
from pathlib import Path
from flask import Flask, request, redirect, session
from requests_oauthlib import OAuth2Session
from getpass import getuser

logger = logging.getLogger(__name__)
dotenv.load_dotenv()


class OAuthFlow:
    alias: None

    def __init__(
        self,
        instance_url: str = "https://login.salesforce.com",
        port: int = 5000,
        alias: str = None,
        salesfunk_path: Path = (Path.home() / ".salesfunk"),
        timeout_sec: int = 120,
        require_secure_callback=False,  # Dev mode only.
    ):
        if not require_secure_callback:
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        self._client_id = os.getenv("SF_CLIENT_ID")
        self._secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret_key_123456")
        self.port = port
        self.instance_url = instance_url.rstrip("/")
        self.alias = alias
        self.salesfunk_path = salesfunk_path
        self.timeout_sec = timeout_sec

        self._oauth_session: OAuth2Session = None
        self._oauth_token = None
        self._shutdown_trigger = threading.Event()

        self._app = Flask(__name__)
        self._app.secret_key = self._secret_key
        self._setup_routes()

    def get_token(self):
        token = self._load_token() or self._run()
        return token

    def refresh_token(self):
        token = self._load_token()
        if not token or "refresh_token" not in token:
            raise RuntimeError("No refresh token available. Please re-authenticate.")
        self._oauth_session.token = token
        new_token = self._oauth_session.refresh_token(
            self._token_url, refresh_token=token["refresh_token"]
        )
        self._save_token(new_token)
        self._oauth_token = new_token
        logger.info("Salesforce token refreshed.")
        return new_token

    @property
    def _redirect_uri(self):
        return f"http://localhost:{self.port}/callback"

    @property
    def _login_uri(self):
        return f"http://localhost:{self.port}/login"

    @property
    def _authorize_url(self):
        return f"{self.instance_url}/services/oauth2/authorize"

    @property
    def _token_url(self):
        return f"{self.instance_url}/services/oauth2/token"

    @property
    def token_path(self):
        connection_identifier = self.alias or self.instance_url.removeprefix("https://")
        return self.salesfunk_path / f"token-{connection_identifier}.json"

    def _setup_routes(self):
        @self._app.route("/login")
        def login():
            print(self._client_id)
            self._oauth_session = OAuth2Session(
                self._client_id,
                redirect_uri=self._redirect_uri,
                # code_challenge_method="S256",
                auto_refresh_url=self._token_url,
                auto_refresh_kwargs={"client_id": self._client_id},
                token_updater=self._save_token,
                pkce="S256",
            )
            authorization_url, state = self._oauth_session.authorization_url(
                self._authorize_url
            )
            session["oauth_state"] = state
            print("🔑 Login here:", authorization_url)
            return redirect(authorization_url)

        @self._app.route("/callback")
        def callback():
            print(self._oauth_session.token)
            print(self._oauth_session.client_id)
            self._oauth_token = self._oauth_session.fetch_token(
                self._token_url,
                authorization_response=request.url,
                include_client_id=True,
            )
            self._oauth_session.token = self._oauth_token
            self._save_token(self._oauth_token)
            self._shutdown_trigger.set()
            shutdown = request.environ.get("werkzeug.server.shutdown")
            if shutdown:
                shutdown()
            return "Login complete! You can close this tab."

        @self._app.route("/__shutdown__")
        def shutdown():
            func = request.environ.get("werkzeug.server.shutdown")
            if func is None:
                raise RuntimeError("Not running with the Werkzeug Server")
            func()
            return "Server shutting down"

    def _run(self):
        thread = threading.Thread(
            target=lambda: self._app.run(
                port=self.port, debug=False, use_reloader=False
            ),
            daemon=True,
        )
        thread.start()

        if not webbrowser.open(f"http://localhost:{self.port}/login", new=1):
            print(
                "Could not open browser automatically. Please open the login URL manually:",
                file=sys.stderr,
            )
            print(f"   http://localhost:{self.port}/login", file=sys.stderr)

        success = self._shutdown_trigger.wait(timeout=self.timeout_sec)
        if not success:
            err = f"OAuth flow timed out after {self.timeout_sec} seconds."
            logger.error(err)
            raise TimeoutError(err)

        requests.get(f"http://localhost:{self.port}/__shutdown__")

        return self._oauth_token or self._load_token()

    def _save_token(self, token):
        self._oauth_token = token
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_path, "w") as f:
            json.dump(token, f)
        os.chmod(self.token_path, 0o600)

    def _load_token(self):
        if self._oauth_token:
            return self._oauth_token
        if self.token_path.exists():
            with open(self.token_path) as f:
                return json.load(f)
        return None

    def _delete_token(self) -> bool:
        if self._oauth_token:
            del self._oauth_token
        if self.token_path.exists():
            self.token_path.unlink()
            logger.info("Token deleted successfully.")
            return True
        else:
            logger.info("No token found to delete.")
            return False
