import json
import logging
from typing import TypeAlias

import boto3
import requests
from botocore.client import ClientError

DMMEvent: TypeAlias = dict[str, str | dict[str]]


def lambda_handler(event, context) -> None:
    logging.getLogger().setLevel(logging.INFO)

    # parameters: todo: pass from outside
    dmm_base_url = 'https://app.datamesh-manager.com/api/events'
    dmm_api_key_secret_name = 'dmm_integration__api_key'
    aws_account_id = context.invoked_function_arn.split(":")[4]
    sqs_queue_name = 'dmm-events.fifo'

    # create client for target queue in sqs
    sqs = boto3.client('sqs')
    target_queue_client = TargetQueueClient(sqs, sqs_queue_name, aws_account_id)

    # create repo for last processed event
    s3 = boto3.client('s3')
    last_processed_event_repo = LastProcessedEventIdRepo(
        s3,
        'dmm-integration',
        'process_feed/last_event_id'
    )

    # create client for Data Mesh Manager
    secretsmanager = boto3.client('secretsmanager')
    secrets = Secrets(secretsmanager)
    dmm_api_key = secrets.get_secret(dmm_api_key_secret_name)
    dmm_events_client = DMMEventsClient(dmm_base_url, dmm_api_key)

    # create feed processor
    feed_processor = FeedProcessor(
        last_processed_event_repo,
        dmm_events_client,
        target_queue_client
    )

    # start processing new events
    feed_processor.process_new_events()

    return


class TargetQueueClient:
    def __init__(self, sqs, queue_name: str, aws_account_id: str):
        self._sqs = sqs
        self._queue_name = queue_name
        self._aws_account_id = aws_account_id

    def send_message(self, message: dict, message_id: str) -> None:
        self._sqs.send_message(
            QueueUrl=self._get_queue_url(),
            MessageBody=json.dumps(message),
            MessageDeduplicationId=message_id,
            # use single message processor for now
            MessageGroupId='1'
        )

    def _get_queue_url(self) -> str:
        return self._sqs.get_queue_url(
            QueueName=self._queue_name,
            QueueOwnerAWSAccountId=self._aws_account_id
        )['QueueUrl']


class LastProcessedEventIdRepo:
    def __init__(self, s3, bucket: str, key: str):
        self._s3 = s3
        self._bucket = bucket
        self._key = key

    def get_last_event_id(self) -> str | None:
        try:
            s3_object = self._s3.get_object(Bucket=self._bucket, Key=self._key)
            return s3_object['Body'].read().decode('utf-8')
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                # no id exists yet, so return None
                return None
            else:
                # otherwise raise the error
                raise e

    def put_last_event_id(self, event_id: str):
        self._s3.put_object(
            Body=event_id,
            Bucket=self._bucket,
            Key=self._key
        )


class DMMEventsClient:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url
        self._api_key = api_key

    def get_events(
        self,
        last_event_id: str | None
    ) -> list[DMMEvent]:
        response = requests.get(
            url=self._events_url(last_event_id),
            headers={
                'x-api-key': self._api_key,
                'accept': 'application/cloudevents-batch+json'
            })
        response.raise_for_status()
        return response.json()

    def _events_url(self, last_event_id: str | None) -> str:
        return self._base_url if last_event_id is None \
            else '{url}?lastEventId={id}'.format(url=self._base_url,
                                                 id=last_event_id)


class Secrets:
    def __init__(self, secretsmanager):
        self._secretsmanager = secretsmanager

    def get_secret(self, secret_name: str) -> str:
        get_secret_value_response = \
            self._secretsmanager.get_secret_value(SecretId=secret_name)

        return get_secret_value_response['SecretString']


class FeedProcessor:
    def __init__(
        self,
        last_process_event_id_repo: LastProcessedEventIdRepo,
        dmm_events_client: DMMEventsClient,
        target_queue_client: TargetQueueClient
    ):
        self._last_process_event_id_repo = last_process_event_id_repo
        self._dmm_events_client = dmm_events_client
        self._target_queue_client = target_queue_client

    def process_new_events(self) -> None:
        last_event_id = self._last_process_event_id_repo.get_last_event_id()
        logging.info('Starting from event {}'.format(last_event_id))
        while True:
            elements = self._dmm_events_client.get_events(last_event_id)
            if len(elements) == 0:
                break
            else:
                last_event_id = self._process_batch(elements)

    # todo: process batches of 10 elements to reduce iops
    def _process_batch(self, elements: list[DMMEvent]) -> str | None:
        element_id = None
        for element in elements:
            element_id = element['id']
            self._process_element(element, element_id)
        return element_id

    def _process_element(self, element: DMMEvent, element_id: str) -> None:
        logging.info('Processing event {}'.format(element_id))
        self._target_queue_client.send_message(element, element_id)
        self._last_process_event_id_repo.put_last_event_id(element_id)
        logging.info('Processed event {}'.format(element_id))
