import urllib.parse
import urllib.request
from simple_salesforce import Salesforce
import subprocess
import re
import urllib
from typing import Optional


class Salesfunk(Salesforce):
    """
    Salesforce read/write client. Internally, this class calls the Salesforce
    REST and Bulk APIs for you. It handles batching, error handling, logging,
    and loading the results into a dataframe. Every method returns a `pandas`
    DataFrame.
    """

    def __init__(self, cli_org_alias: Optional[str], **kwargs):
        """
        Create a new Salesfunk client. Internally, grabs

        Args:
            - cli_org_alias (str): If specified, will attempt to connect to
            Salesforce by calling the [`sf`](https://developer.salesforce.com/tools/salesforcecli)
            cli.

            - **kwargs: get passed to the `simple_salesforce.Salesforce`
            constructor if `org_alias` is not specified.
        """
        if cli_org_alias:
            session_id, instance_url = _get_session_id(cli_org_alias)
            kwargs["session_id"] = session_id
            kwargs["instance_url"] = instance_url
        super(**kwargs)

    def connect(self, org_url: str = "https://login.salesforce.com/"):
        """
        Connects this instance to
        """
        pass


from collections import namedtuple

SessionId = namedtuple("SessionId", ["session_id", "instance_url"])


def _get_session_id(org_alias: str | None):
    """
    Runs cli command `sf org open --url-only [-o {org_alias}]` and scrapes for
    a session ID.

    Args:
        org_alias (str | None): org alias or org URL to sign into

    Returns:
        session_id, host: The session ID
    """
    cmd_args = [
        "sf",
        "org",
        "open",
        "--url-only",
    ]
    if org_alias:
        cmd_args.append("-o")
        cmd_args.append(str(org_alias))
    pipe = subprocess.run(cmd_args, capture_output=True)
    assert pipe.returncode == 0
    pipe = pipe.stdout.decode("utf-8")
    # Strip control characters
    pipe = "".join(i for i in pipe if 31 < ord(i) < 127)
    # Remove ansi color codes
    pipe = re.sub(r"\[[0-9]{1,2}m", "", pipe)
    words = [word for word in pipe.split() if word.startswith("https://")]
    assert len(words) == 1
    url = urllib.parse.urlparse(words[0])
    instance_url = url.hostname
    query = urllib.parse.parse_qs(url.query)
    session_id = query["sid"][0]
    return SessionId(session_id=session_id, instance_url=instance_url)
