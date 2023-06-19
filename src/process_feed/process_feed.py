import boto3
import logging

from botocore.client import ClientError
from requests import get, Response
from json import dumps


def lambda_handler(event, context):
    logging.getLogger().setLevel(logging.INFO)

    key = api_key('process_feed_dmm_api_key')

    last_event_id = get_last_event_id()
    account_id = context.invoked_function_arn.split(":")[4]

    logging.info('Starting from event {}'.format(last_event_id))

    sqs = boto3.client('sqs')
    queue_url = sqs.get_queue_url(
        QueueName='dmm-events.fifo',
        QueueOwnerAWSAccountId=account_id
    )['QueueUrl']

    while True:
        response_elements = get_events(key, last_event_id).json()

        if len(response_elements) == 0:
            break
        else:
            for element in response_elements:
                element_id = element['id']
                logging.info('Processing element {}'.format(element_id))

                json = dumps(element)

                sqs.send_message(
                    QueueUrl=queue_url,
                    MessageBody=json,
                    MessageDeduplicationId=element_id,
                    # use single message processor for now:
                    MessageGroupId='1'
                )

                last_event_id = element_id
                put_last_event_id(last_event_id)

                logging.info('Processed element {}'.format(element_id))

    return


def get_last_event_id() -> str | None:
    try:
        s3_object = boto3.client('s3').get_object(
            Bucket='dmm-permissions-extension',
            Key='process_feed/last_event_id'
        )

        return s3_object['Body'].read()
    except ClientError as e:
        # todo: better check if object exists or other client error occurred
        logging.warning(e.response)
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
