import boto3
from botocore.client import ClientError
from requests import get, Response


def lambda_handler(event, context):
    key = api_key('process_feed_dmm_api_key')

    last_event_id = get_last_event_id()

    print(last_event_id)

    while True:
        response_elements = get_events(key, last_event_id).json()

        if len(response_elements) == 0:
            break
        else:
            for element in response_elements:
                last_event_id = element['id']
                print(last_event_id)
                put_last_event_id(last_event_id)

    return


def get_last_event_id() -> str:
    try:
        s3_object = boto3.client('s3').get_object(
            Bucket='dmm-permissions-extension',
            Key='process_feed/last_event_id'
        )

        return s3_object['Body'].read()
    except ClientError as e:
        # todo: better check if object exists or other client error occurred
        print(e.response)
        return None


def put_last_event_id(event_id: str):
    boto3.client('s3').put_object(
        Body=event_id,
        Bucket='dmm-permissions-extension',
        Key='process_feed/last_event_id'
    )


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


def api_key(secret_name: str) -> str:
    client = boto3.client('secretsmanager')
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)

    return get_secret_value_response['SecretString']
