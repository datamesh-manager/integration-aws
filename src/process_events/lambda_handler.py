import logging


def lambda_handler(event, context):
    logging.getLogger().setLevel(logging.INFO)
    logging.info(event)
    return
