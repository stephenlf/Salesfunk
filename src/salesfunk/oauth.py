import os
import json
import threading
import webbrowser
import sys
import logging
import dotenv
import requests
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from requests_oauthlib import OAuth2Session

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
        require_secure_callback=True,  # Dev mode only.
    ):
        """
        Create a new OAuthFlow client. Use this to sign into Salesforce with a browser-based flow,
        much like you would with the `sf` CLI.

        Args:
            instance_url (str, optional): Instance URL. Defaults to "https://login.salesforce.com".
            port (int, optional): Port to serve the auth server on. Defaults to 5000.
            alias (str, optional): Alias for your org. Allows you to have multiple active connections at once. Defaults to None.
            salesfunk_path (str, optional): Path to store your access tokens. Must be secured. Defaults to (Path.home() / ".salesfunk").
            timeout_sec (int, optional): Amount of time you have to complete the OAuth flow before it times out. Defaults to 120.
            require_secure_callback (bool, optional): If False, the OAuth server won't require HTTPs comms. For dev only.. Defaults to True.
        """
        if not require_secure_callback:
            err = 'https:// transport should be required, except in limit, dev environments'
            print(err, sys.stderr)
            logger.warning(err)
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        self._client_id = os.getenv("SF_CLIENT_ID")
        self.port = port
        self._instance_url = instance_url.rstrip("/")
        self.alias = alias
        self.salesfunk_path = salesfunk_path
        self.timeout_sec = timeout_sec

        self._oauth_session: OAuth2Session = None
        self._oauth_token = None
        self._shutdown_trigger = threading.Event()

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
    
    def connect(self):
        if not self._oauth_token:
            self._run()
        else:
            print('Already connected')

    @property
    def session_id(self):
        return self.get_token()['access_token']
    
    @property
    def instance_url(self):
        return self.get_token()['instance_url']

    @property
    def _redirect_uri(self):
        return f"http://localhost:{self.port}/callback"

    @property
    def _login_uri(self):
        return f"http://localhost:{self.port}/login"

    @property
    def _authorize_url(self):
        return f"{self._instance_url}/services/oauth2/authorize"

    @property
    def _token_url(self):
        return f"{self._instance_url}/services/oauth2/token"

    @property
    def token_path(self):
        connection_identifier = self.alias or self._instance_url.removeprefix("https://")
        return self.salesfunk_path / f"token-{connection_identifier}.json"

    def get_token(self):
        token = self._load_token() or self._run()
        return token

    def _run(self):
        self._oauth_session = OAuth2Session(
            self._client_id,
            redirect_uri=self._redirect_uri,
            auto_refresh_url=self._token_url,
            auto_refresh_kwargs={"client_id": self._client_id},
            token_updater=self._save_token,
            pkce="S256",
        )
        authorization_url, state = self._oauth_session.authorization_url(
            self._authorize_url
        )
        print("🔑 Login here:", authorization_url)
        webbrowser.open(authorization_url, new=1)
    
        # Start one-shot HTTP server to handle the callback
        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path != '/callback':
                    self.send_response(404)
                    self.end_headers()
                    return

                query = parse_qs(parsed.query)
                if 'code' not in query:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'Missing code in callback')
                    return
                
                received_state = query.get("state", [None])[0]
                if received_state != state:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Invalid state token (possible CSRF).")
                    return

                try:
                    flow: OAuthFlow = self.server.flow
                    authorization_response_url = f'http://localhost:{self.server.server_port}{self.path}'
                    print(authorization_response_url)
                    oauth_token = flow._oauth_session.fetch_token(
                        flow._token_url,
                        authorization_response=authorization_response_url,
                        include_client_id=True
                    )
                    flow._save_token(oauth_token)
                    
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'Login complete! You can close this tab.')
                except Exception as e:
                    logger.error(f'OAuth callback failed: {e}')
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b'OAuth error. Check your notebook logs')
                
                # Shut down server after handling
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            
        httpd = HTTPServer(('localhost', self.port), CallbackHandler)
        httpd.flow = self # Attach current flow instance to handler
        httpd.serve_forever()
        
        return self._oauth_token

        # thread = threading.Thread(
        #     target=lambda: self._app.run(
        #         port=self.port, debug=False, use_reloader=False
        #     ),
        #     daemon=True,
        # )
        # thread.start()

        # if not webbrowser.open(f"http://localhost:{self.port}/login", new=1):
        #     print(
        #         "Could not open browser automatically. Please open the login URL manually:",
        #         file=sys.stderr,
        #     )
        #     print(f"   http://localhost:{self.port}/login", file=sys.stderr)

        # success = self._shutdown_trigger.wait(timeout=self.timeout_sec)
        # if not success:
        #     err = f"OAuth flow timed out after {self.timeout_sec} seconds."
        #     logger.error(err)
        #     raise TimeoutError(err)

        # requests.get(f"http://localhost:{self.port}/__shutdown__")

        # return self._oauth_token or self._load_token()

    # def _setup_routes(self):
    #     @self._app.route("/login")
    #     def login():
    #         print(self._client_id)
    #         self._oauth_session = OAuth2Session(
    #             self._client_id,
    #             redirect_uri=self._redirect_uri,
    #             # code_challenge_method="S256",
    #             auto_refresh_url=self._token_url,
    #             auto_refresh_kwargs={"client_id": self._client_id},
    #             token_updater=self._save_token,
    #             pkce="S256",
    #         )
    #         authorization_url, state = self._oauth_session.authorization_url(
    #             self._authorize_url
    #         )
    #         session["oauth_state"] = state
    #         print("🔑 Login here:", authorization_url)
    #         return redirect(authorization_url)

    #     @self._app.route("/callback")
    #     def callback():
    #         print(self._oauth_session.token)
    #         print(self._oauth_session.client_id)
    #         self._oauth_token = self._oauth_session.fetch_token(
    #             self._token_url,
    #             authorization_response=request.url,
    #             include_client_id=True,
    #         )
    #         self._oauth_session.token = self._oauth_token
    #         self._save_token(self._oauth_token)
    #         self._shutdown_trigger.set()
    #         shutdown = request.environ.get("werkzeug.server.shutdown")
    #         if shutdown:
    #             shutdown()
    #         return "Login complete! You can close this tab."

    #     @self._app.route("/__shutdown__")
    #     def shutdown():
    #         func = request.environ.get("werkzeug.server.shutdown")
    #         if func is None:
    #             raise RuntimeError("Not running with the Werkzeug Server")
    #         func()
    #         return "Server shutting down"



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
