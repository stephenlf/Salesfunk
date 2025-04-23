# SF-OAUTH
_A simple OAuth client for Salesforce_

This package lets you connect to Salesforce using a browser-based flow, much like you would with the `sf` cli or similar tools. It frees you from having to manage security tokens for all of your sandbox environments. It is intended to be used in Python Notebooks or CLI tools.

## Usage

Use an `OAuthFlow` object to generate an `instance_url` and `session_id` to pass to a simple_salesforce `Salesforce` client.

```python
from sf_oauth import OAuthFlow
from simple_salesforce import Salesforce

flow = OAuthFlow(domain='test')
flow.connect() # This will open a browser window to 'https://test.salesforce.com' for you to sign in

sf = Salesforce(instance_url=flow.instance_url, session_id=flow.session_id)
```

Instantiate multiple clients to connect to different orgs at the same time

```python
from sf_oauth import OAuthFlow
from simple_salesforce import Salesforce

prod_flow = OAuthFlow(alias='prod')
sandbox_flow = OAuthFlow(alias='sandbox', domain='test')

prod = Salesforce(instance_url=prod_flow.instance_url, session_id=prod_flow.session_id)
sandbox = Salesforce(instance_url=sandbox_flow.instance_url, session_id=sandbox_flow.session_id)
```

Access tokens are cached by default. You can `disconnect` to log out and delete your access tokens.

```python
from sf_oauth import OAuthFlow
flow = OAuthFlow(domain='test')
flow.connect() # We already connected once, so it loads access from the cache rather than opening a browser
flow.disconnect() # Log out and forget cached token
```

## Setting up your External Client App

The OAuthFlow needs an External Client App configured in your org to work. You can easily set this up yourself.

1. Go to Setup and use the Quick Find box to find the "External Client App Manager"
2. Click "New External Client App"
3. Fill out the "New External Client App" form
  1. Enter a Name and Email as appropriate
  2. Set the "Distribution State" to "Local"
  3. Check the "Enable OAuth"
  4. Set the "Callback URL" to "http://localhost:5000" (remote notebook environments may need to be configured differently)
  5. Select the OAuth Scopes you need. For trusted, internal usage, you can use `full`.
  6. Select "Enable Authorization Code and Credentials Flow"
  7. Select "Require Proof Key for Code Exchange (PKCE) extension for Supported Authorization Flows"
  8. Click "Create"
4. Open the newly created Client App, go to the "Settings" tab, and click "Consumer Key and Secret." You will save the "Consumer Key" to the `SF_OAUTH_CLIENT_ID` environment variable or pass it into the `OAuthFlow` constructor.