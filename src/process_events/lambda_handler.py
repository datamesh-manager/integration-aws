import json
import logging

import boto3
from requests import get


def lambda_handler(event, context):
    logging.getLogger().setLevel(logging.INFO)

    dmm_events = list(map(lambda e: json.loads(e['body']), event['Records']))
    api_key = dmm_api_key('dmm_integration__api_key')

    for dmm_event in dmm_events:
        process_event(api_key, dmm_event)

    return


def process_event(api_key: str, event: dict[str, str | dict]):
    logging.info('Process event: {}'.format(event))

    match event['type']:
        case 'com.datamesh-manager.events.DataContractActivatedEvent':
            process_activated_event(api_key, event)
        case 'com.datamesh-manager.events.DataContractDeactivatedEvent':
            process_deactivated_event(event)


def process_activated_event(api_key: str, event: dict[str, str | dict]):
    # datacontract_id = event['data']['id']
    # get_datacontract(api_key, datacontract_id)

    logging.info('Activated: {}'.format(event['id']))


def get_datacontract(
    api_key: str,
    datacontract_id: str
) -> dict[str, dict[str, str]]:
    response = get(
        url='/api/datacontracts/{}'.format(datacontract_id),
        headers={
            'x-api-key': api_key,
            'accept': 'application/cloudevents-batch+json'
        })
    response.raise_for_status()

    return response.json()


def process_deactivated_event(event):
    logging.info('Deactivated: {}'.format(event['id']))


class Secrets:
    def __init__(self, secretsmanager):
        self._secretsmanager = secretsmanager

    def get_secret(self, secret_name: str) -> str:
        get_secret_value_response = \
            self._secretsmanager.get_secret_value(SecretId=secret_name)

        return get_secret_value_response['SecretString']
