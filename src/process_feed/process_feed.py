from requests import get, Response
from boto3.session import Session


def lambda_handler(event, context):
    key = api_key('process_feed_dmm_api_key', 'eu-central-1')

    last_event_id = None

    while True:
        response_elements = get_events(key, last_event_id).json()

        if len(response_elements) == 0:
            break
        else:
            for element in response_elements:
                print(element)
                last_event_id = element['id']

    return


def get_events(key: str, last_event_id: str) -> Response:
    response = get(
        url=events_url(last_event_id),
        headers={
            'x-api-key': key,
            'accept': 'application/cloudevents-batch+json'
        })
    response.raise_for_status()

    return response


def events_url(last_event_id: str) -> str:
    base_url = 'https://app.datamesh-manager.com/api/events'
    return base_url if last_event_id is None \
        else '{url}?lastEventId={id}'.format(url=base_url, id=last_event_id)


def api_key(secret_name: str, region_name: str) -> str:
    session = Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    get_secret_value_response = client.get_secret_value(
        SecretId=secret_name
    )

    return get_secret_value_response['SecretString']
