import logging
import sys
import simple_salesforce
import pandas as pd
from simple_salesforce import Salesforce
from typing import Literal
from pathlib import Path
from .oauth import OAuthFlow
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class Salesfunk:
    """
    Salesforce read/write client. Internally, this class calls the Salesforce
    REST and Bulk APIs for you. It handles batching, error handling, logging,
    and loading the results into a dataframe. Every method returns a `pandas`
    DataFrame.
    """

    sf: Salesforce = None
    _connected: bool = False
    _oauth: OAuthFlow

    def __init__(
        self,
        instance_url: str = None,
        instance: str = None,
        domain: str = None,
        connect=False,
        **kwargs,
    ):
        """
        Initialize a SalesFunk client.

        You may either:
        - Provide credentials for direct login (e.g., username/password/security_token), or
        - Provide nothing and use the OAuth browser flow via `connect()`.

        Keyword Arguments:
            Salesforce Authentication:
                username (str): (Optional) Salesforce username
                password (str): (Optional) Corresponding password
                security_token (str): (Optional) Salesforce security token
                session_id (str): (Optional) Pre-authenticated session token
                instance_url (str): (Optional) Full Salesforce org URL (e.g., https://login.salesforce.com)
                instance (str): (Optional) Org URL without schema (e.g., "login.salesforce.com")
                domain (str): (Optional)

            SalesFunk OAuth Flow:
                instance_url (str): (Optional) Override OAuth login URL (e.g., https://login.salesforce.com)
                instance (str): (Optional) Shortcut for login domains (e.g., "test" for sandbox)
                domain (str): (Optional) Org domain (e.g. "login", "test", or a custom org domain)

            Universal:
                version (str): API version to use (default: latest supported)
                proxies (dict): Proxy mapping for HTTP requests
                session (requests.Session): Custom requests session
                connect (bool): Eagerly connect at instantiation, without explicitly calling `.connect()` first

        Notes:
            If login with credentials fails or is not provided, the client
            will fall back to browser-based OAuth authentication on first call to `.connect()`.
        """

        self.kwargs = kwargs
        self._connected = False
        if connect:
            self.connect()

    def connect(self):
        if self.sf:
            return
        try:
            self._connect_with_kwargs()
        except (
            simple_salesforce.exceptions.SalesforceAuthenticationFailed,
            TypeError,
        ) as e:
            logger.info(f"Falling back to browser login (OAuth): {e}")
            self._connect_with_web()

    def query(
        self, query: str = None, file_path: str | Path = None, **kwargs
    ) -> pd.DataFrame:
        """
        Execute a SOQL query and return the results as a pandas DataFrame.
        Args:
            query (str): The SOQL query to execute. If provided, this will override the `query` argument.
            file_path (Path): The path to a file containing the SOQL query. You must provide either a query string or a file path.
        Returns:
            pandas.DataFrame: The results of the query.
        Raises:
            ValueError: If neither `query` nor `file_path` is provided.
        """
        pass

    def query_sosl(self, query: str = None, file_path: Path = None, **kwargs):
        """
        Execute a SOSL query and return the results as a pandas DataFrame.
        Args:
            query (str): The SOSL query to execute. If provided, this will override the `query` argument.
            file_path (Path): The path to a file containing the SOSL query. You must provide either a query string or a file path.
        Returns:
            pandas.DataFrame: The results of the query.
        Raises:
            ValueError: If neither `query` nor `file_path` is provided.
        """
        pass

    def load(
        self,
        object: str,
        data: pd.DataFrame,
        operation: Literal["insert", "update", "upsert", "delete"],
        batch_size=9500,
        external_id: str = None,
    ) -> pd.DataFrame:
        """
        Load data into Salesforce using the Bulk API.
        Args:
            object (str): The API name of the Salesforce object to load data into.
            data (pd.DataFrame): The data to load.
            operation (str): The operation to perform (e.g., "insert", "update", "upsert", "delete").
            batch_size (int): The size of each batch to send to Salesforce. Defaults to 9500.
            external_id (str): The name of the external ID field to use for upsert operations. Required if `operation` is "upsert".
        Returns:
            pandas.DataFrame: The results of the load operation.
        Raises:
            ValueError: If the `operation` is not one of the supported operations.
            ValueError: If `external_id` is provided but `operation` is not "upsert".
        """
        pass

    def _connect_with_web(self):
        self._oauth = OAuthFlow(
            instance_url=_to_instance_url(**self.kwargs),
            port=self.kwargs.get("port", 5000),
        )
        token = self._oauth.get_token()
        self.sf = Salesforce(
            session_id=token["access_token"], instance_url=token["instance_url"]
        )

    def _connect_with_kwargs(self):
        self.sf = Salesforce(**self.kwargs)


def _to_instance_url(*_, domain=None, instance=None, instance_url=None):
    """
    Validates and transforms kwargs into an instance URL. If no args are passed,
    defaults to "https://login.salesforce.com". Preferentially uses the value of
    `instance_url`, then `instance`, then `domain`.

    Args:
        domain (str, optional): Instance domain, e.g. "test" or "login".
        instance (str, optional): Instance url without the schema, e.g. "login.salesforce.com".
        instance_url (str, optional): Instance url, e.g. "https://login.salesforce.com".

    Raises:
        ValueError: If the supplied

    Returns:
        str: instance url formatted as "https://{domain}.salesforce.com"
    """
    if instance_url is not None:
        parse = urlparse(instance_url)
        if not str(parse.netloc).endswith("salesforce.com"):
            raise ValueError(
                f'Expected `instance_url` to end in ".salesforce.com", got {parse.netloc}'
            )
        if not str(parse.scheme) == "https":
            raise ValueError(
                f'Expected `instance_url` to start with "https://". Did you mean to specify `instance`?'
            )
        if parse.path != "":
            err = "URL path parameters will be stripped from instance_url"
            logger.warning(err)
            print(err)
        return f"https://{parse.netloc}"
    if instance is not None:
        if not str(parse.netloc).endswith("salesforce.com"):
            raise ValueError(
                f'Expected `instance` to end in ".salesforce.com", got {instance}'
            )
        return f"https://{instance}"
    if domain is not None:
        if ":" in domain:
            raise ValueError('Unexpected value in `domain`: ":"')
        if "/" in domain:
            raise ValueError('Unexpected value in `domain`: "/"')
        return f"https://{domain}.salesforce.com"
    return "https://login.salesforce.com"
