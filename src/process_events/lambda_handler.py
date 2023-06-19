import json
import logging


def lambda_handler(event, context):
    logging.getLogger().setLevel(logging.INFO)

    dmm_events = list(map(lambda e: json.loads(e['body']), event['Records']))

    for dmm_event in dmm_events:
        process_dmm_event(dmm_event)

    return


def process_dmm_event(event):
    logging.info(event)

    match event['type']:
        case 'com.datamesh-manager.events.DataContractActivatedEvent':
            logging.info('Activate {}'.format(event['id']))
        case 'com.datamesh-manager.events.DataContractDeactivatedEvent':
            logging.info('Deactivate {}'.format(event['id']))
