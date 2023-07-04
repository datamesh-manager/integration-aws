import json
import logging
from datetime import datetime
from typing import TypeAlias

import requests

DataContract: TypeAlias = dict[str, dict[str, str]]
Port: TypeAlias = dict[str, dict[str, str]]
DataProduct: TypeAlias = dict[str, dict[str, str] | list[Port]]
DMMEvent: TypeAlias = dict[str, str | dict]


def lambda_handler(event, context):
    logging.getLogger().setLevel(logging.INFO)

    # resource_explorer = boto3.client('resource-explorer-2')
    # iam = boto3.client('iam')
    #
    # dmm_events = list(map(lambda e: json.loads(e['body']), event['Records']))
    #
    # secrets = Secrets(boto3.client('secretsmanager'))
    # api_key = secrets.get_secret('dmm_integration__api_key')
    #
    # for dmm_event in dmm_events:
    #     process_event(api_key, dmm_event)

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


class AccessManager:
    def __init__(self, iam, resource_explorer):
        self._iam = iam
        self._resource_explorer = resource_explorer

    def remove_access(self, datacontract_id: str):
        policy_arn = self._search_policy_for_contract(datacontract_id)
        if policy_arn is None:
            logging.warning('Policy for contract {} not found '
                            'while trying to remove access.'
                            .format(datacontract_id))
        else:
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

        # return existing policy arn if one exists for parameters
        existing_policy_arn = self._search_policy_for_contract(datacontract_id)
        if existing_policy_arn is not None:
            logging.info('Policy for datacontract {} exists already'
                         .format(datacontract_id))
            return existing_policy_arn

        # otherwise create policy and attach to role
        policy = {
            'Version': self._policy_version(),
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
            PolicyName='DMM Datacontract {}'.format(datacontract_id),
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

    def _search_policy_for_contract(self,
        datacontract_id) -> str | None:
        search_result = self._resource_explorer.search(
            QueryString='tag:managed-by=dmm-integration AND '
                        'tag:dmm-integration-contract=' + datacontract_id,
            MaxResults=1)
        assert search_result['Count']['TotalResources'] <= 1
        if search_result['Count']['TotalResources'] == 1:
            return search_result['Resources'][0]['Arn']
        else:
            return None

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
    def __init__(self, dmm_client: DMMClient, access_manager: AccessManager):
        self._dmm_client = dmm_client
        self._access_manager = access_manager

    def handle(self, event: DMMEvent) -> None:
        logging.info('Process event: {}'.format(event))
        match event['type']:
            case 'com.datamesh-manager.events.DataContractDeactivatedEvent':
                self._deactivated_event(event)
            case 'com.datamesh-manager.events.DataContractActivatedEvent':
                self._activated_event(event)

    def _deactivated_event(self, event: DMMEvent):
        self._access_manager.remove_access(event['data']['id'])

    def _activated_event(self, event: DMMEvent):
        datacontract_id = event['data']['id']

        datacontract = self._dmm_client.get_datacontract(datacontract_id)

        consumer_role_name = self._consumer_role_name(
            datacontract['consumer']['dataProductId'])

        output_port_arn = self._output_port_arn(
            datacontract['provider']['dataProductId'],
            datacontract['provider']['outputPortId'])

        self._access_manager.grant_access(datacontract_id,
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
