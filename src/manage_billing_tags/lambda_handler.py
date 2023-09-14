import datetime
import json
import logging
from os import environ
from typing import TypeAlias

import boto3
import requests

DataProduct: TypeAlias = dict[str, dict[str, str] | list[dict]]
DMMEvent: TypeAlias = dict[str, str | dict]
Tag: TypeAlias = (str, str)
Arn: TypeAlias = str


def lambda_handler(event, context):
    logging.getLogger().setLevel(logging.INFO)

    # get configuration
    dmm_base_url = environ['dmm_base_url']
    dmm_api_key_secret_name = environ['dmm_api_key_secret_name']

    cost_explorer = boto3.client('ce')
    cost_explorer_tagging = CostExplorerTagging(cost_explorer)

    # create client for Data Mesh Manager
    secretsmanager = boto3.client('secretsmanager')
    secrets = Secrets(secretsmanager)
    dmm_api_key = secrets.get_secret(dmm_api_key_secret_name)
    dmm_client = DMMClient(dmm_base_url, dmm_api_key)

    # create event handler
    event_handler = EventHandler(dmm_client, cost_explorer_tagging)

    # handle dmm events from lambda event
    dmm_events = list(map(lambda e: json.loads(e['body']), event['Records']))
    for dmm_event in dmm_events:
        event_handler.handle(dmm_event)

    return


class DMMClient:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url
        self._api_key = api_key

    def get_dataproduct(self, dataproduct_id) -> DataProduct | None:
        response = requests.get(
            url=self._dataproduct_url(dataproduct_id),
            headers={'x-api-key': self._api_key,
                     'accept': 'application/json'})

        if response.status_code == 404:
            logging.warning(
                'No dataproduct with id {}'.format(dataproduct_id))
            return None
        else:
            response.raise_for_status()
            return response.json()

    def _dataproduct_url(self, dataproduct_id) -> str:
        return '{base_url}/api/dataproducts/{id}'.format(
            base_url=self._base_url, id=dataproduct_id)


class Secrets:
    def __init__(self, secretsmanager):
        self._secretsmanager = secretsmanager

    def get_secret(self, secret_name: str) -> str:
        get_secret_value_response = \
            self._secretsmanager.get_secret_value(SecretId=secret_name)

        return get_secret_value_response['SecretString']


class CostExplorerTagging:
    def __init__(self, cost_explorer):
        self._cost_explorer = cost_explorer

    def list_values_for_tag_key(self, key: str) -> list[Arn]:
        result = self._cost_explorer.get_tags(
            TimePeriod={
                'Start': f'{datetime.date.today().replace(day=1)}',
                'End': f'{datetime.date.today()}'
            },
            TagKey=key
        )

        return result['Tags']

    def tag(self, resource: Arn, tag: Tag):
        pass

    def untag(self, resource: Arn, tag: Tag):
        pass


class EventHandler:
    def __init__(self, dmm_client: DMMClient, tagging: CostExplorerTagging):
        self._dmm_client = dmm_client
        self._tagging = tagging

    @staticmethod
    def handle(event: DMMEvent) -> None:
        logging.info('Handle event: {}'.format(event))

        # tag schema: ('data-product-{id}', '{arn}')

        # filter events
        # get resources from dmm
        # get tags from billing api
        # compare arn in tags with resources
        # delete unused tags
        # add missing tags

        pass
