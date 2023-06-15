import requests
from boto3.session import Session
from botocore.exceptions import ClientError


def lambda_handler(event, context):
    print(event)


    api_key()
    return


def api_key() -> str:
    secret_name = "process_feed_dmm_api_key"
    region_name = "eu-central-1"

    # Create a Secrets Manager client
    session = Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    return get_secret_value_response['SecretString']
