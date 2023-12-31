import json
import logging
from datetime import datetime
from os import environ
from typing import TypeAlias

import boto3
import requests
from botocore.exceptions import ClientError

DataUsageAgreement: TypeAlias = dict[str, dict[str, str]]
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

    def get_data_usage_agreement(self, data_usage_agreement_id: str) -> DataUsageAgreement | None:
        response = self._get(self._data_usage_agreement_url(data_usage_agreement_id))

        if response.status_code == 404:
            logging.warning(
                'No data_usage_agreement with id {}'.format(data_usage_agreement_id))
            return None
        else:
            response.raise_for_status()
            return response.json()

    def patch_data_usage_agreement(self, data_usage_agreement_id: str, value: dict) -> None:
        current = self.get_data_usage_agreement(data_usage_agreement_id)
        self._put(self._data_usage_agreement_url(data_usage_agreement_id), {**current, **value})

    def _data_usage_agreement_url(self, data_usage_agreement_id) -> str:
        return '{base_url}/api/datausageagreements/{id}'.format(
            base_url=self._base_url, id=data_usage_agreement_id)

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
            json=body
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
        data_usage_agreement_id: str,
        consumer_role_name: str):
        try:
            self._iam.delete_role_policy(
                RoleName=consumer_role_name,
                PolicyName=self._policy_name(data_usage_agreement_id), )
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                logging.warning('Policy for {} not found.'
                                .format(data_usage_agreement_id))
            else:
                raise e

    def grant_access(self,
        data_usage_agreement_id: str,
        consumer_role_name: str,
        output_port_type: str,
        output_port_arn: [str]) -> str:
        """Gives access to an AWS resource and returns the name of the
        corresponding policy

        works only for S3 buckets at this point
        """

        policy_name = self._policy_name(data_usage_agreement_id)
        policy_statements = self._policy_statements(output_port_type,
                                                    output_port_arn)
        policy_document = self._policy_document(policy_statements)

        self._iam.put_role_policy(
            RoleName=consumer_role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )

        return policy_name

    @staticmethod
    def _policy_name(data_usage_agreement_id: str) -> str:
        return 'DMM_DataUsageAgreement_{}'.format(data_usage_agreement_id)

    @staticmethod
    def _policy_document(policy_statements: [dict]) -> dict:
        return {
            'Version': '2012-10-17',
            'Statement': policy_statements
        }

    # create required policy statements based on the service defined in arn
    @staticmethod
    def _policy_statements(output_port_type: str, output_port_arn: [str]):
        match output_port_type:
            case 's3_bucket':
                policy_statements = AWSIAMManager._s3_bucket_statements(
                    output_port_arn)
            case 'glue_table':
                policy_statements = AWSIAMManager._glue_table_statements(
                    output_port_arn)
            case _:
                raise UnsupportedOutputPortException(output_port_type)
        return policy_statements

    @staticmethod
    def _s3_bucket_statements(output_port_arn):
        s3_arn = AWSIAMManager._filter_arn_by_service(output_port_arn, 's3')
        policy_statements = [AWSIAMManager._s3_bucket_statement(s3_arn)]
        return policy_statements

    @staticmethod
    def _s3_bucket_statement(bucket_arn: [str]) -> dict:
        return {
            'Effect': 'Allow',
            'Action': [
                's3:GetBucketLocation',
                's3:GetObject',
                's3:ListBucket'
            ],
            'Resource': [
                *bucket_arn,
                *list(map(lambda a: '{}/*'.format(a), bucket_arn))
            ]
        }

    @staticmethod
    # access to glue tables by using an athena query
    def _glue_table_statements(output_port_arn):
        s3_arn = AWSIAMManager._filter_arn_by_service(output_port_arn, 's3')
        glue_arn = AWSIAMManager._filter_arn_by_service(output_port_arn, 'glue')
        athena_arn = AWSIAMManager._filter_arn_by_service(output_port_arn,
                                                          'athena')

        policy_statements = [
            *AWSIAMManager._s3_folder_statements(s3_arn),
            AWSIAMManager._glue_statement(glue_arn),
            AWSIAMManager._athena_statement(athena_arn)]
        return policy_statements

    @staticmethod
    def _s3_folder_statements(s3_arn):
        bucket_statement = {
            'Effect': 'Allow',
            'Action': [
                's3:ListBucket'
            ],
            'Resource': list(map(lambda a: a.split('/')[0], s3_arn))
        }
        folder_statement = {
            'Effect': 'Allow',
            'Action': [
                's3:GetObject'
            ],
            'Resource': list(map(lambda a: '{}/*'.format(a), s3_arn))
        }
        return bucket_statement, folder_statement

    @staticmethod
    def _glue_statement(arn: [str]) -> dict:
        return {
            'Effect': 'Allow',
            'Action': ['glue:GetTable'],
            'Resource': arn
        }

    @staticmethod
    def _athena_statement(workgroup_arn: [str]) -> dict:
        return {
            'Effect': 'Allow',
            'Action': ['athena:StartQueryExecution'],
            'Resource': workgroup_arn
        }

    @staticmethod
    def _filter_arn_by_service(arn_list: [str], service_name: str) -> [str]:
        return list(arn for arn in arn_list if
                    arn.startswith('arn:aws:{}'.format(service_name)))

    @staticmethod
    def _managed_by_tag() -> dict[str, str]:
        return {
            'Key': 'managed-by',
            'Value': 'dmm-integration'
        }

    @staticmethod
    def _contract_id_tag(data_usage_agreement_id: str) -> dict[str, str]:
        return {
            'Key': 'dmm-integration-contract',
            'Value': data_usage_agreement_id
        }

    @staticmethod
    def _policy_version() -> str:
        return datetime.today().strftime('%Y-%m-%d')


class UnsupportedOutputPortException(Exception):
    def __init__(self, service_name):
        super().__init__("Unsupported output port: {}".format(service_name))


class EventHandler:
    def __init__(self, dmm_client: DMMClient, aws_iam_manager: AWSIAMManager):
        self._dmm_client = dmm_client
        self._aws_iam_manager = aws_iam_manager

    def handle(self, event: DMMEvent) -> None:
        logging.info('Handle event: {}'.format(event))
        match event['type']:
            case 'com.datamesh-manager.events.DataUsageAgreementDeactivatedEvent':
                logging.info('Deactivate')
                self._deactivated_event(event)
            case 'com.datamesh-manager.events.DataUsageAgreementActivatedEvent':
                logging.info('Activate')
                self._activated_event(event)

    def _deactivated_event(self, event: DMMEvent):
        data_usage_agreement = self._dmm_client.get_data_usage_agreement(event['data']['id'])
        # aws resource specific code from here
        if data_usage_agreement is not None:
            consumer_dataproduct = self._dmm_client.get_dataproduct(
                data_usage_agreement['consumer']['dataProductId'])
            self._aws_deactivated_event(data_usage_agreement, consumer_dataproduct)

            logging.info('Deactivated: {}'.format(event['id']))

    def _activated_event(self, event: DMMEvent):
        data_usage_agreement_id = event['data']['id']
        data_usage_agreement = self._dmm_client.get_data_usage_agreement(data_usage_agreement_id)

        if data_usage_agreement is not None:
            consumer_dataproduct = self._dmm_client.get_dataproduct(
                data_usage_agreement['consumer']['dataProductId'])
            provider_dataproduct = self._dmm_client.get_dataproduct(
                data_usage_agreement['provider']['dataProductId'])

            self._aws_activated_event(data_usage_agreement,
                                      consumer_dataproduct,
                                      provider_dataproduct)

            logging.info('Activated: {}'.format(event['id']))

    # aws resource specific code from here

    def _aws_deactivated_event(self,
        data_usage_agreement: DataUsageAgreement,
        consumer_dataproduct: DataProduct):

        data_usage_agreement_id = data_usage_agreement['info']['id']
        consumer_role_name = self._aws_consumer_role_name(consumer_dataproduct)
        self._aws_iam_manager.remove_access(data_usage_agreement_id, consumer_role_name)

        self._dmm_client.patch_data_usage_agreement(data_usage_agreement_id, {
            'tags': ['aws-integration', 'aws-integration-inactive']
        })

    def _aws_activated_event(self,
        data_usage_agreement: DataUsageAgreement,
        consumer_dataproduct: DataProduct,
        provider_dataproduct: DataProduct):

        data_usage_agreement_id = data_usage_agreement['info']['id']

        # grant access to aws_resource to consumer
        policy_name = self._aws_grant_access(data_usage_agreement,
                                             consumer_dataproduct,
                                             provider_dataproduct)

        self._dmm_client.patch_data_usage_agreement(data_usage_agreement_id, {
            'custom': {'aws-policy-name': policy_name},
            'tags': ['aws-integration', 'aws-integration-active']
        })

    def _aws_grant_access(self,
        data_usage_agreement: DataUsageAgreement,
        consumer_dataproduct: DataProduct,
        provider_dataproduct: DataProduct) -> str:

        # implementation for s3 bucket
        data_usage_agreement_id = data_usage_agreement['info']['id']
        consumer_role_name = self._aws_consumer_role_name(consumer_dataproduct)
        output_port = self._aws_s3_bucket_output_port(
            provider_dataproduct,
            data_usage_agreement['provider']['outputPortId'])

        return self._aws_iam_manager.grant_access(
            data_usage_agreement_id,
            consumer_role_name,
            self._output_port_type(output_port),
            self._output_port_arn(output_port))

    @staticmethod
    def _output_port_type(output_port: dict) -> str:
        try:
            return output_port['custom']['output-port-type']
        except KeyError as ke:
            raise RequiredCustomFieldNotSet(ke)

    @staticmethod
    def _output_port_arn(output_port) -> [str]:
        output_port_arn = list(
            output_port['custom'][field] for field in output_port['custom'] if
            field.startswith('aws') and field.endswith('arn'))
        return output_port_arn

    @staticmethod
    def _aws_consumer_role_name(consumer_dataproduct: DataProduct):
        try:
            consumer_role_name = consumer_dataproduct['custom']['aws-role-name']
        except KeyError as ke:
            raise RequiredCustomFieldNotSet(ke)

        return consumer_role_name

    @staticmethod
    def _aws_s3_bucket_output_port(
        provider_dataproduct: DataProduct,
        provider_output_port_id: str) -> dict:
        return next(op for op in provider_dataproduct['outputPorts']
                    if op['id'] == provider_output_port_id)


class RequiredCustomFieldNotSet(Exception):
    def __init__(self, field_name):
        super().__init__("Custom field must be set: {}".format(field_name))
