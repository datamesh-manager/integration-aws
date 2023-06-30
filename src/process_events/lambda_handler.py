import json
import logging
from datetime import datetime
from typing import TypeAlias

import boto3
import requests

DataContract: TypeAlias = dict[str, dict[str, str]]
Port: TypeAlias = dict[str, dict[str, str]]
DataProduct: TypeAlias = dict[str, dict[str, str] | list[Port]]


def lambda_handler(event, context):
    logging.getLogger().setLevel(logging.INFO)

    resource_explorer = boto3.client('resource-explorer-2')
    iam = boto3.client('iam')

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


class AccessManager:
    def __init__(self, iam, resource_explorer):
        self._iam = iam
        self._resource_explorer = resource_explorer

    def remove_access(self, datacontract_id: str):
        pass

    # todo: add permissions based on output port (supports only s3 for now)
    def grant_access(self,
        datacontract_id: str,
        consumer_group_name: str,
        output_port_arn: str):

        policy = {
            'Version': self._policy_version(),
            'Statement': self._policy_statements(output_port_arn)
        }

        self._grant_access(datacontract_id, consumer_group_name, policy)

    # create required policy statements based on the service defined in arn
    def _policy_statements(self, output_port_arn):
        output_port_service_name = output_port_arn.split(':')[2]
        match output_port_service_name:
            case 's3':
                policy_statements = [self._s3_statement(output_port_arn)]
            case _:
                raise UnsupportedServiceException(output_port_service_name)
        return policy_statements

    def _grant_access(self,
        datacontract_id: str,
        consumer_group_name: str,
        policy_document: dict):

        # create policy
        create_policy_result = self._iam.create_policy(
            PolicyName='DMM Datacontract {}'.format(datacontract_id),
            PolicyDocument=json.dumps(policy_document),
            Tags=[self.managed_by_tag(), self._contract_id_tag(datacontract_id)]
        )
        # attach it to the consumer iam group
        self._iam.attach_group_policy(
            GroupName=consumer_group_name,
            PolicyArn=create_policy_result['Policy']['Arn']
        )

    @staticmethod
    def _s3_statement(output_port_arn: str) -> dict:
        return {
            'Effect': 'Allow',
            'Action': [
                's3:GetBucketLocation',
                's3:GetObject',
                's3:ListBucket'
            ],
            'Resource': [
                output_port_arn,
                '{}/*'.format(output_port_arn)
            ]
        }

    @staticmethod
    def managed_by_tag() -> dict[str, str]:
        return {
            'Key': 'managed-by',
            'Value': 'dmm-integration'
        }

    @staticmethod
    def _contract_id_tag(datacontract_id: str) -> dict[str, str]:
        return {
            'Key': 'dmm-integration-contract',
            'Value': datacontract_id
        }

    @staticmethod
    def _policy_version() -> str:
        return datetime.today().strftime('%Y-%m-%d')


class UnsupportedServiceException(Exception):
    def __init__(self, service_name):
        super().__init__("Unsupported service: {}".format(service_name))
