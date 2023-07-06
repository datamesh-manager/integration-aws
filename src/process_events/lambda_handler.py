import json
import logging
from datetime import datetime
from os import environ
from typing import TypeAlias

import boto3
import requests

DataContract: TypeAlias = dict[str, dict[str, str]]
Port: TypeAlias = dict[str, dict[str, str]]
DataProduct: TypeAlias = dict[str, dict[str, str] | list[Port]]
DMMEvent: TypeAlias = dict[str, str | dict]


def lambda_handler(event, context):
    logging.getLogger().setLevel(logging.INFO)

    # get configuration
    dmm_base_url = environ['dmm_base_url']
    dmm_api_key_secret_name = environ['dmm_api_key_secret_name']

    # create iam manager
    iam = boto3.client('iam')
    iam_manager = AWSIAMManager(iam)

    # create client for Data Mesh Manager
    secretsmanager = boto3.client('secretsmanager')
    secrets = Secrets(secretsmanager)
    dmm_api_key = secrets.get_secret(dmm_api_key_secret_name)
    dmm_client = DMMClient(dmm_base_url, dmm_api_key)

    # create event handler
    event_handler = EventHandler(dmm_client, iam_manager)

    # handle dmm events from lambda event
    dmm_events = list(map(lambda e: json.loads(e['body']), event['Records']))
    for dmm_event in dmm_events:
        event_handler.handle(dmm_event)

    return


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


class AWSIAMManager:
    def __init__(self, iam):
        self._iam = iam

    def remove_access(self, policy_arn: str):
        role_name = self._get_single_policy_role_name(policy_arn)
        self._iam.detach_role_policy(RoleName=role_name,
                                     PolicyArn=policy_arn)
        self._iam.delete_policy(PolicyArn=policy_arn)

    def _get_single_policy_role_name(self, policy_arn):
        response = self._iam.list_entities_for_policy(PolicyArn=policy_arn,
                                                      MaxItems=1)
        assert len(response['PolicyGroups']) == 0
        assert len(response['PolicyUsers']) == 0
        assert len(response['PolicyRoles']) == 1

        return response['PolicyRoles'][0]['RoleName']

    def grant_access(self,
        datacontract_id: str,
        consumer_role_name: str,
        output_port_arn: str) -> str:
        """Gives access to an AWS resource and returns the arn of the
        corresponding policy

        - works only for S3 buckets at this point -
        """
        policy = {
            'Version': '2012-10-17',
            'Statement': self._policy_statements(output_port_arn)
        }

        return self._grant_access(datacontract_id, consumer_role_name, policy)

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
        consumer_role_name: str,
        policy_document: dict) -> str:
        # create policy
        create_policy_result = self._iam.create_policy(
            PolicyName='DMM_Datacontract_{}'.format(datacontract_id),
            PolicyDocument=json.dumps(policy_document),
            Tags=[self._managed_by_tag(),
                  self._contract_id_tag(datacontract_id)]
        )

        # attach it to the consumer iam role
        self._iam.attach_role_policy(
            RoleName=consumer_role_name,
            PolicyArn=create_policy_result['Policy']['Arn']
        )

        return create_policy_result['Policy']['Arn']

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
    def _managed_by_tag() -> dict[str, str]:
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


class EventHandler:
    def __init__(self, dmm_client: DMMClient, aws_iam_manager: AWSIAMManager):
        self._dmm_client = dmm_client
        self._aws_iam_manager = aws_iam_manager

    def handle(self, event: DMMEvent) -> None:
        logging.info('Process event: {}'.format(event))
        match event['type']:
            case 'com.datamesh-manager.events.DataContractDeactivatedEvent':
                self._deactivated_event(event)
            case 'com.datamesh-manager.events.DataContractActivatedEvent':
                self._activated_event(event)

    def _deactivated_event(self, event: DMMEvent):
        datacontract = self._dmm_client.get_datacontract(event['data']['id'])
        if datacontract is not None:
            policy_arn = datacontract['custom']['aws-policy-arn']
            self._aws_iam_manager.remove_access(policy_arn)

    def _activated_event(self, event: DMMEvent):
        datacontract_id = event['data']['id']

        datacontract = self._dmm_client.get_datacontract(datacontract_id)

        if datacontract is not None:
            consumer_role_name = self._consumer_role_name(
                datacontract['consumer']['dataProductId'])

            output_port_arn = self._output_port_arn(
                datacontract['provider']['dataProductId'],
                datacontract['provider']['outputPortId'])

            self._aws_iam_manager.grant_access(datacontract_id,
                                               consumer_role_name,
                                               output_port_arn)

            logging.info('Activated: {}'.format(event['id']))

    def _consumer_role_name(self, consumer_dataproduct_id):
        consumer_dataproduct = self._dmm_client.get_dataproduct(
            consumer_dataproduct_id)

        try:
            consumer_role_name = consumer_dataproduct['custom']['aws-role-name']
        except KeyError as ke:
            raise RequiredCustomFieldNotSet(ke)

        return consumer_role_name

    def _output_port_arn(self,
        provider_dataproduct_id,
        provider_output_port_id) -> str:

        provider_dataproduct = self._dmm_client.get_dataproduct(
            provider_dataproduct_id)

        output_port = next(op
                           for op in provider_dataproduct['outputPorts']
                           if op['id'] == provider_output_port_id)

        try:
            output_port_arn = output_port['custom']['aws-arn']
        except KeyError as ke:
            raise RequiredCustomFieldNotSet(ke)

        return output_port_arn


class RequiredCustomFieldNotSet(Exception):
    def __init__(self, field_name):
        super().__init__("Custom field must be set: {}".format(field_name))
