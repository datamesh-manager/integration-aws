import json
import logging
from datetime import datetime
from os import environ
from typing import TypeAlias

import boto3
import requests
from botocore.exceptions import ClientError

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
        response = self._get(self._datacontract_url(datacontract_id))

        if response.status_code == 404:
            logging.warning(
                'No datacontract with id {}'.format(datacontract_id))
            return None
        else:
            response.raise_for_status()
            return response.json()

    def patch_datacontract(self, datacontract_id: str, value: dict) -> None:
        current = self.get_datacontract(datacontract_id)
        self._put(self._datacontract_url(datacontract_id), {**current, **value})

    def _datacontract_url(self, datacontract_id) -> str:
        return '{base_url}/api/datacontracts/{id}'.format(
            base_url=self._base_url, id=datacontract_id)

    def get_dataproduct(self, dataproduct_id) -> DataProduct | None:
        response = self._get(self._dataproduct_url(dataproduct_id))

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

    def _get(self, url):
        return requests.get(
            url=url,
            headers={'x-api-key': self._api_key,
                     'accept': 'application/json'})

    def _put(self, url, body):
        return requests.put(
            url=url,
            headers={'x-api-key': self._api_key,
                     'accept': 'application/json',
                     'Content-Type': 'application/json'},
            body=body
        )


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

    def remove_access(self,
        datacontract_id: str,
        consumer_role_name: str):
        try:
            self._iam.delete_role_policy(
                RoleName=consumer_role_name,
                PolicyName=self._policy_name(datacontract_id), )
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntityException':
                logging.warning('Policy for {} not found.'
                                .format(datacontract_id))
            else:
                raise e

    def grant_access(self,
        datacontract_id: str,
        consumer_role_name: str,
        output_port_arn: str) -> str:
        """Gives access to an AWS resource and returns the name of the
        corresponding policy

        works only for S3 buckets at this point
        """

        policy_name = self._policy_name(datacontract_id)
        policy_document = self._policy_document(output_port_arn)

        self._iam.put_role_policy(
            RoleName=consumer_role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )

        return policy_name

    @staticmethod
    def _policy_name(datacontract_id: str) -> str:
        return 'DMM_Datacontract_{}'.format(datacontract_id)

    @staticmethod
    def _policy_document(output_port_arn):
        return {
            'Version': '2012-10-17',
            'Statement': AWSIAMManager._policy_statements(output_port_arn)
        }

    # create required policy statements based on the service defined in arn
    @staticmethod
    def _policy_statements(output_port_arn):
        output_port_service_name = output_port_arn.split(':')[2]
        match output_port_service_name:
            case 's3':
                policy_statements = [
                    AWSIAMManager._s3_statement(output_port_arn)]
            case _:
                raise UnsupportedServiceException(output_port_service_name)
        return policy_statements

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
                logging.info('Deactivate')
                self._deactivated_event(event)
            case 'com.datamesh-manager.events.DataContractActivatedEvent':
                logging.info('Activate')
                self._activated_event(event)

    def _deactivated_event(self, event: DMMEvent):
        datacontract = self._dmm_client.get_datacontract(event['data']['id'])
        # aws resource specific code from here
        # if datacontract is not None:
        self._aws_deactivated_event(datacontract)

    def _activated_event(self, event: DMMEvent):
        datacontract_id = event['data']['id']
        datacontract = self._dmm_client.get_datacontract(datacontract_id)

        if datacontract is not None:
            consumer_dataproduct = self._dmm_client.get_dataproduct(
                datacontract['consumer']['dataProductId'])
            provider_dataproduct = self._dmm_client.get_dataproduct(
                datacontract['provider']['dataProductId'])

            self._aws_activated_event(datacontract,
                                      consumer_dataproduct,
                                      provider_dataproduct)

            logging.info('Activated: {}'.format(event['id']))

    # aws resource specific code from here

    def _aws_deactivated_event(self, datacontract):
        policy_arn = datacontract['custom']['aws-policy-arn']
        self._aws_iam_manager.remove_access(policy_arn)

    def _aws_activated_event(self,
        datacontract: DataContract,
        consumer_dataproduct: DataProduct,
        provider_dataproduct: DataProduct):

        datacontract_id = datacontract['info']['id']
        policy_arn = None

        # grant access to aws_resource to consumer
        try:
            policy_arn = self._aws_grant_access(datacontract,
                                                consumer_dataproduct,
                                                provider_dataproduct)
        except ClientError as e:
            # todo: test
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                logging.info("Policy for contract {} already exists."
                             .format(datacontract_id))
            else:
                raise e

        # todo: test
        # update datacontract in DMM
        # if policy_arn is not None:
        #     try:
        #         self._aws_add_arn_to_datacontract(datacontract_id, policy_arn)
        #     except Exception as e:
        #         logging.warning('Failed to update DMM. Removing access ({}).'
        #                         .format(datacontract_id))
        #         # if anything goes wrong remove access and reraise exception
        #         self._aws_iam_manager.remove_access(policy_arn)
        #         raise e

    def _aws_grant_access(self,
        datacontract: DataContract,
        consumer_dataproduct: DataProduct,
        provider_dataproduct: DataProduct) -> str:

        datacontract_id = datacontract['info']['id']
        consumer_role_name = self._aws_consumer_role_name(consumer_dataproduct)
        output_port_arn = self._aws_output_port_arn(
            provider_dataproduct,
            datacontract['provider']['outputPortId'])

        return self._aws_iam_manager.grant_access(
            datacontract_id,
            consumer_role_name,
            output_port_arn)

    def _aws_add_arn_to_datacontract(self, datacontract_id, policy_arn):
        self._dmm_client.patch_datacontract(datacontract_id, {
            'custom': {'aws-policy-arn': policy_arn}})

    @staticmethod
    def _aws_consumer_role_name(consumer_dataproduct: DataProduct):
        try:
            consumer_role_name = consumer_dataproduct['custom']['aws-role-name']
        except KeyError as ke:
            raise RequiredCustomFieldNotSet(ke)

        return consumer_role_name

    @staticmethod
    def _aws_output_port_arn(
        provider_dataproduct: DataProduct,
        provider_output_port_id: str) -> str:
        output_port = \
            next(op for op in provider_dataproduct['outputPorts']
                 if op['id'] == provider_output_port_id)
        try:
            output_port_arn = output_port['custom']['aws-arn']
        except KeyError as ke:
            raise RequiredCustomFieldNotSet(ke)
        return output_port_arn


class RequiredCustomFieldNotSet(Exception):
    def __init__(self, field_name):
        super().__init__("Custom field must be set: {}".format(field_name))
