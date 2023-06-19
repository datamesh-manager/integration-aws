import json
import logging

import boto3
from requests import get


def lambda_handler(event, context):
    logging.getLogger().setLevel(logging.INFO)

    dmm_events = list(map(lambda e: json.loads(e['body']), event['Records']))

    for dmm_event in dmm_events:
        process_event(dmm_event)

    return


def process_event(event):
    logging.info('Process event: {}'.format(event))

    match event['type']:
        case 'com.datamesh-manager.events.DataContractActivatedEvent':
            process_activated_event(event)
        case 'com.datamesh-manager.events.DataContractDeactivatedEvent':
            process_deactivated_event(event)


def process_activated_event(event):
    key = dmm_api_key('permissions__dmm_api_key')
    datacontract_id = event['data']['id']
    response = get(
        url='/api/datacontracts/{}'.format(datacontract_id),
        headers={
            'x-api-key': key,
            'accept': 'application/cloudevents-batch+json'
        })
    response.raise_for_status()

    logging.info('Activated: {}'.format(event['id']))


def process_deactivated_event(event):
    logging.info('Deactivated: {}'.format(event['id']))


def dmm_api_key(secret_name: str) -> str:
    client = boto3.client('secretsmanager')
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)

    return get_secret_value_response['SecretString']
