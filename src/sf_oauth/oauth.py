import os
import json
import threading
import webbrowser
import logging
import dotenv
from datetime import datetime
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
        callback_url: str = "http://localhost",
        port: int = 5000,
        alias: str = None,
        token_storage_path: Path = (Path.home() / ".sf-oauth"),
        client_id: str = os.getenv("SF_OAUTH_CLIENT_ID"),
        refresh_interval_mili: float = 3600 * 1000,  # 1 hour, configurable in the Salesforce connected app
    ):
        """
        Create a new OAuthClient. Use this to sign into Salesforce with a browser-based flow,
        much like you would with the `sf` CLI.

        Args:
            instance_url (str, optional): Instance URL. Defaults to "https://login.salesforce.com".
            port (int, optional): Port to serve the auth server on. Defaults to 5000.
            alias (str, optional): Alias for your org. Allows you to have multiple active connections at once. Defaults to None.
            salesfunk_path (str, optional): Path to store your access tokens. Must be secured. Defaults to (Path.home() / ".salesfunk").
            client_id (str, optional): Consumer Key for External Client App in Salesforce. Defaults to env var `SF_CLIENT_ID`
            refresh_interval_mili (float, optional): Amount of time before an access token expires and should be refreshed. Defaults to 1 hr.
        """
        self._client_id = client_id
        self.callback_url = callback_url
        self.port = port
        self._instance_url = instance_url.rstrip("/")
        self.alias = alias
        self.salesfunk_path = token_storage_path
        self.refresh_interval_mili = refresh_interval_mili

        self._oauth_session: OAuth2Session = OAuth2Session(
            self._client_id,
            redirect_uri=self._redirect_uri,
            auto_refresh_url=self._token_url,
            auto_refresh_kwargs={"client_id": self._client_id},
            token_updater=self._save_token,
            pkce="S256",
        )
        self._oauth_token = None
        self._shutdown_trigger = threading.Event()

    def connect(self):
        token = self._load_token()
        if not token:
            return self._run()
        # Check if token is stale and refresh if necessary
        now_mili = datetime.now().timestamp() * 1000
        if 'issued_at' in token and now_mili - int(token['issued_at']) > self.refresh_interval_mili:
            token = self._refresh_token(token)
            
    def reconnect(self):
        self._delete_token()
        self.connect()
        
    def disconnect(self):
        self._delete_token()
        del self._oauth_token
    
    @property
    def session_id(self):
        return self._get_token()['access_token']
    
    @property
    def instance_url(self):
        return self._get_token()['instance_url']

    @property
    def _redirect_uri(self):
        return f"{self.callback_url}:{self.port}/callback"

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

    def _run(self):
        authorization_url, state = self._oauth_session.authorization_url(
            self._authorize_url
        )
        try:
            webbrowser.open(authorization_url, new=1)
        except:
            print("🔑 Login here:", authorization_url)
    
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

    def _get_token(self):
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

    def _refresh_token(self, token):
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

def _to_instance_url(domain: str = None, instance: str = None, instance_url: str = None):
    pass