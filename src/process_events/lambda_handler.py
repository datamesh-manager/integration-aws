import json
import logging
from typing import TypeAlias

import boto3
import requests

DataContract: TypeAlias = dict[str, dict[str, str]]
Port: TypeAlias = dict[str, dict[str, str]]
DataProduct: TypeAlias = dict[str, dict[str, str] | list[Port]]


def lambda_handler(event, context):
    logging.getLogger().setLevel(logging.INFO)

    dmm_events = list(map(lambda e: json.loads(e['body']), event['Records']))

    secrets = Secrets(boto3.client('secretsmanager'))
    api_key = secrets.get_secret('dmm_integration__api_key')

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
    datacontract_id = event['data']['id']
    # get_datacontract(api_key, datacontract_id)
    client = DMMClient('https://app.datamesh-manager.com/api/events',
                       api_key)
    client.get_datacontract(datacontract_id)

    logging.info('Activated: {}'.format(event['id']))


def process_deactivated_event(event):
    logging.info('Deactivated: {}'.format(event['id']))


class DMMClient:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url
        self._api_key = api_key

    def get_datacontract(self, datacontract_id: str) -> DataContract | None:
        response = self._get(self._get_datacontract_url(datacontract_id))

        if response.status_code == 404:
            logging.warning(
                'No datacontract with id {}'.format(datacontract_id))
            return None
        else:
            response.raise_for_status()
            return response.json()

    def _get_datacontract_url(self, datacontract_id) -> str:
        return '{base_url}/api/datacontracts/{id}'.format(
            base_url=self._base_url, id=datacontract_id)

    def get_dataproduct(self, dataproduct_id) -> DataProduct | None:
        response = self._get(self._get_dataproduct_url(dataproduct_id))

        if response.status_code == 404:
            logging.warning(
                'No dataproduct with id {}'.format(dataproduct_id))
            return None
        else:
            response.raise_for_status()
            return response.json()

    def _get_dataproduct_url(self, dataproduct_id) -> str:
        return '{base_url}/api/dataproducts/{id}'.format(
            base_url=self._base_url, id=dataproduct_id)

    def _get(self, url):
        return requests.get(
            url=url,
            headers={'x-api-key': self._api_key,
                     'accept': 'application/json'})


class Secrets:
    def __init__(self, secretsmanager):
        self._secretsmanager = secretsmanager

    def get_secret(self, secret_name: str) -> str:
        get_secret_value_response = \
            self._secretsmanager.get_secret_value(SecretId=secret_name)

        return get_secret_value_response['SecretString']
