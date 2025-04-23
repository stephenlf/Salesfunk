import sf_oauth
from simple_salesforce import Salesforce
if __name__ == '__main__':
    flow = sf_oauth.OAuthClient(instance_url='https://test.salesforce.com')
    flow.connect()

    sf = Salesforce(session_id=flow.session_id, instance_url=flow.instance_url)
    print(sf.query_all('SELECT count() FROM Account'))