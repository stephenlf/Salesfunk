from salesfunk.oauth import OAuthFlow

if __name__ == '__main__':
    from simple_salesforce import Salesforce
    flow = OAuthFlow(instance_url='https://test.salesforce.com', require_secure_callback=False)
    flow.connect()

    sf = Salesforce(session_id=flow.session_id, instance_url=flow.instance_url)
    print(sf.query_all('SELECT count() FROM Account'))