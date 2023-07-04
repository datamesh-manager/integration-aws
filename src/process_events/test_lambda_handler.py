import json
import logging
import unittest
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch, sentinel, Mock

import boto3
from botocore.stub import Stubber

from lambda_handler import Secrets, DMMClient, AccessManager, EventHandler, \
    UnsupportedServiceException, RequiredCustomFieldNotSet


class TestDMMClient(TestCase):
    _base_url = 'https://dmm-url.com'
    _api_key = 'supersecret'
    _datacontract_id = '123'
    _dataproduct_id = '987'

    def setUp(self) -> None:
        self._client = DMMClient(self._base_url, self._api_key)

    class MockResponse:
        def __init__(self, body, status):
            self._body = body
            self.status_code = status

        def json(self) -> str:
            return self._body

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise Exception()

    # commonly used

    @staticmethod
    def mock_get__api_key(**kwargs) -> MockResponse:
        if kwargs['headers']['x-api-key'] == TestDMMClient._api_key:
            return TestDMMClient.MockResponse(sentinel.expected, 200)
        else:
            return TestDMMClient.MockResponse(sentinel.something, 500)

    # get_datacontract

    @staticmethod
    def mock_get_datacontract(**kwargs) -> MockResponse:
        expected_url = '{base_url}/api/datacontracts/{id}'.format(
            base_url=TestDMMClient._base_url,
            id=TestDMMClient._datacontract_id)

        if kwargs['url'] == expected_url:
            return TestDMMClient.MockResponse(sentinel.expected, 200)
        else:
            return TestDMMClient.MockResponse(None, 200)

    @patch('requests.get', Mock(side_effect=mock_get_datacontract))
    def test_get_datacontract(self) -> None:
        self.assertEqual(sentinel.expected,
                         self._client.get_datacontract(self._datacontract_id))

    @staticmethod
    def mock_get_datacontract_not_found(**kwargs) -> MockResponse:
        return TestDMMClient.MockResponse(sentinel.something, 404)

    @patch('requests.get', Mock(side_effect=mock_get_datacontract_not_found))
    def test_get_datacontract_not_found(self) -> None:
        self.assertEqual(None,
                         self._client.get_datacontract(self._datacontract_id))

    @staticmethod
    def mock_get_datacontract_other_error() -> MockResponse:
        return TestDMMClient.MockResponse(sentinel.something, 500)

    @patch('requests.get', Mock(side_effect=mock_get_datacontract_other_error))
    def test_get_datacontract_other_error(self) -> None:
        with self.assertRaises(Exception):
            self._client.get_datacontract(self._datacontract_id)

    @patch('requests.get', Mock(side_effect=mock_get__api_key))
    def test_get_datacontract_api_key(self) -> None:
        self.assertEqual(sentinel.expected,
                         self._client.get_datacontract(self._datacontract_id))

    # get_dataproduct

    @staticmethod
    def mock_get_dataproduct(**kwargs) -> MockResponse:
        expected_url = '{base_url}/api/dataproducts/{id}'.format(
            base_url=TestDMMClient._base_url,
            id=TestDMMClient._dataproduct_id)

        if kwargs['url'] == expected_url:
            return TestDMMClient.MockResponse(sentinel.expected, 200)
        else:
            return TestDMMClient.MockResponse(None, 200)

    @patch('requests.get', Mock(side_effect=mock_get_dataproduct))
    def test_get_dataproduct(self) -> None:
        self.assertEqual(sentinel.expected,
                         self._client.get_dataproduct(self._dataproduct_id))

    @staticmethod
    def mock_get_dataproduct_not_found(**kwargs) -> MockResponse:
        return TestDMMClient.MockResponse(sentinel.something, 404)

    @patch('requests.get', Mock(side_effect=mock_get_dataproduct_not_found))
    def test_get_dataproduct_not_found(self) -> None:
        self.assertEqual(None,
                         self._client.get_dataproduct(self._dataproduct_id))

    @staticmethod
    def mock_get_dataproduct_other_error(**kwargs) -> MockResponse:
        return TestDMMClient.MockResponse(sentinel.something, 500)

    @patch('requests.get', Mock(side_effect=mock_get_dataproduct_other_error))
    def test_get_dataproduct_other_error(self) -> None:
        with self.assertRaises(Exception):
            self._client.get_dataproduct(self._dataproduct_id)

    @patch('requests.get', Mock(side_effect=mock_get__api_key))
    def test_get_dataproduct_api_key(self) -> None:
        self.assertEqual(sentinel.expected,
                         self._client.get_dataproduct(self._dataproduct_id))


class TestSecrets(TestCase):
    _secret_name = 'configured_name'
    _secret_value = 'hi!_i_am_secret'

    def setUp(self) -> None:
        secretsmanager = boto3.client('secretsmanager')

        self._secretsmanager_stubber = Stubber(secretsmanager)
        self._secrets = Secrets(secretsmanager)

    def tearDown(self) -> None:
        self._secretsmanager_stubber.deactivate()

    def test_get_secret(self) -> None:
        expected_params = {
            'SecretId': self._secret_name
        }
        response = {
            'SecretString': self._secret_value
        }
        self._secretsmanager_stubber.add_response(
            'get_secret_value', response, expected_params)
        self._secretsmanager_stubber.activate()

        self.assertEqual(self._secret_value,
                         self._secrets.get_secret(self._secret_name))


class TestAccessManager(TestCase):
    _datacontract_id = '123-123-321'
    _consumer_role_name = 'hi_iam_a_consumer_role'
    _s3_output_port_arn = 'arn:aws:s3:one:two:three'
    _policy_arn = 'arn:aws:policy:one:two:three'

    def setUp(self) -> None:
        iam = boto3.client('iam')
        resource_explorer = boto3.client('resource-explorer-2')

        self._iam_stubber = Stubber(iam)
        self._resource_explorer_stubber = Stubber(resource_explorer)
        self._access_manager = AccessManager(iam, resource_explorer)

    def tearDown(self) -> None:
        self._iam_stubber.deactivate()
        self._resource_explorer_stubber.deactivate()

    def test_remove_access(self) -> None:
        self._stub_resource_search_with_single_result()

        self._iam_stubber.add_response(
            'list_entities_for_policy',
            {
                'PolicyGroups': [],
                'PolicyUsers': [],
                'PolicyRoles': [
                    {
                        'RoleName': self._consumer_role_name,
                    },
                ]
            },
            {
                'MaxItems': 1,
                'PolicyArn': self._policy_arn
            }
        )

        self._iam_stubber.add_response(
            'detach_role_policy',
            {},
            {
                'RoleName': self._consumer_role_name,
                'PolicyArn': self._policy_arn
            }
        )

        self._iam_stubber.add_response(
            'delete_policy',
            {},
            {'PolicyArn': self._policy_arn}
        )

        self._resource_explorer_stubber.activate()
        self._iam_stubber.activate()

        self._access_manager.remove_access(self._datacontract_id)

        self._iam_stubber.assert_no_pending_responses()

    def test_remove_access_policy_not_found(self) -> None:
        self._stub_resource_search_with_empty_result()
        self._resource_explorer_stubber.activate()

        with self.assertLogs(logger=None, level=logging.WARNING) as cm:
            self._access_manager.remove_access(self._datacontract_id)
            self.assertEqual(['WARNING:root:Policy for contract {} not found '
                              'while trying to remove access.'
                             .format(self._datacontract_id)],
                             cm.output)

    def test_grant_access_unsupported(self) -> None:
        self._stub_resource_search_with_empty_result()
        self._resource_explorer_stubber.activate()
        with self.assertRaises(UnsupportedServiceException):
            self._access_manager.grant_access(self._datacontract_id,
                                              self._consumer_role_name,
                                              "aws:arn:iam:one:two:three")

    def test_grant_access_too_many_results(self) -> None:
        self._resource_explorer_stubber.add_response(
            'search',
            {
                'Count': {
                    'TotalResources': 2
                },
                'Resources': [
                    {'Arn': self._policy_arn}
                ]
            },
            {
                'MaxResults': 1,
                'QueryString': 'tag:managed-by=dmm-integration AND '
                               'tag:dmm-integration-contract=' +
                               self._datacontract_id
            }
        )
        self._resource_explorer_stubber.activate()

        with self.assertRaises(AssertionError):
            self._access_manager.grant_access(self._datacontract_id,
                                              self._consumer_role_name,
                                              self._s3_output_port_arn)

    def test_grant_access_policy_exists_already(self) -> None:
        self._stub_resource_search_with_single_result()
        self._resource_explorer_stubber.activate()

        result = self._access_manager.grant_access(self._datacontract_id,
                                                   self._consumer_role_name,
                                                   self._s3_output_port_arn)

        self.assertEqual(self._policy_arn, result)

    def test_grant_access_s3(self) -> None:
        expected_document = {
            'Version': datetime.today().strftime('%Y-%m-%d'),
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Action': [
                        's3:GetBucketLocation',
                        's3:GetObject',
                        's3:ListBucket'
                    ],
                    'Resource': [
                        self._s3_output_port_arn,
                        '{}/*'.format(self._s3_output_port_arn)
                    ]
                }
            ]
        }

        self._stub_create_policy(expected_document)
        self._stub_attach_role_policy()

        self._stub_resource_search_with_empty_result()

        self._iam_stubber.activate()
        self._resource_explorer_stubber.activate()

        result = self._access_manager.grant_access(self._datacontract_id,
                                                   self._consumer_role_name,
                                                   self._s3_output_port_arn)

        self.assertEqual(self._policy_arn, result)

        self._iam_stubber.assert_no_pending_responses()
        self._resource_explorer_stubber.assert_no_pending_responses()

    def _stub_resource_search_with_single_result(self):
        self._resource_explorer_stubber.add_response(
            'search',
            {
                'Count': {
                    'TotalResources': 1
                },
                'Resources': [
                    {
                        'Arn': self._policy_arn
                    }
                ]
            },
            {
                'MaxResults': 1,
                'QueryString': 'tag:managed-by=dmm-integration AND '
                               'tag:dmm-integration-contract=' +
                               self._datacontract_id
            }
        )

    def _stub_resource_search_with_empty_result(self):
        self._resource_explorer_stubber.add_response(
            'search',
            {
                'Count': {
                    'TotalResources': 0
                },
                'Resources': []
            },
            {
                'MaxResults': 1,
                'QueryString': 'tag:managed-by=dmm-integration AND '
                               'tag:dmm-integration-contract=' +
                               self._datacontract_id
            }
        )

    def _stub_create_policy(self, expected_document):
        self._iam_stubber.add_response(
            'create_policy',
            {
                'Policy': {
                    'Arn': self._policy_arn
                }
            },
            {
                'PolicyName': 'DMM Datacontract {}'.format(
                    self._datacontract_id),
                'PolicyDocument': json.dumps(expected_document),
                'Tags': [
                    {
                        'Key': 'managed-by',
                        'Value': 'dmm-integration'
                    },
                    {
                        'Key': 'dmm-integration-contract',
                        'Value': self._datacontract_id
                    }
                ]
            }
        )

    def _stub_attach_role_policy(self):
        expected_params = {
            'RoleName': self._consumer_role_name,
            'PolicyArn': self._policy_arn
        }
        self._iam_stubber.add_response(
            'attach_role_policy',
            {},
            expected_params
        )


class TestEventHandler(TestCase):
    _event_id = '123-123-123-123'
    _data_contract_id = '999-888-777'
    _consumer_role_name = 'consumer_role_123'
    _consumer_dataproduct_id = 'asdf-123-asdf'
    _output_port_id = '456-6454-545'
    _output_port_arn = 'arn:aws:service:output:port'
    _provider_dataproduct_id = 'qwer-321-qwer'

    _activated_event = {
        'id': _event_id,
        'type': 'com.datamesh-manager.events.DataContractActivatedEvent',
        'data': {'id': _data_contract_id}
    }

    @patch('lambda_handler.AccessManager')
    @patch('lambda_handler.DMMClient')
    def setUp(self, dmm_client, access_manager) -> None:
        self._dmm_client = dmm_client
        self._access_manager = access_manager
        self._event_handler = EventHandler(dmm_client, access_manager)

    def tearDown(self) -> None:
        self._dmm_client.reset_mock()
        self._access_manager.reset_mock()

    def test_handle__ignore_others(self) -> None:
        event = {
            'id': self._event_id,
            'type': 'com.datamesh-manager.events.OtherEvent'
        }
        self._event_handler.handle(event)
        self._access_manager.grant_access.assert_not_called()
        self._access_manager.remove_access.assert_not_called()

    def test_handle__deactivated(self) -> None:
        event = {
            'id': self._event_id,
            'type': 'com.datamesh-manager.events.DataContractDeactivatedEvent',
            'data': {'id': self._data_contract_id}
        }

        self._event_handler.handle(event)

        self._access_manager.remove_access.assert_called_with(
            self._data_contract_id)

    def test_handle__activated(self) -> None:
        self._dmm_client.get_datacontract = self._mock_get_data_contract
        self._dmm_client.get_dataproduct = self._mock_get_dataproduct

        self._event_handler.handle(self._activated_event)

        self._access_manager.grant_access.assert_called_with(
            self._data_contract_id,
            self._consumer_role_name,
            self._output_port_arn)

    def test_handle__activated__consumer_role_not_set(self) -> None:
        self._dmm_client.get_datacontract = self._mock_get_data_contract
        self._dmm_client.get_dataproduct = self._mock_get_dataproduct_no_role

        with self.assertRaises(RequiredCustomFieldNotSet):
            self._event_handler.handle(self._activated_event)

    def test_handle__activated__provider_arn_not_set(self) -> None:
        self._dmm_client.get_datacontract = self._mock_get_data_contract
        self._dmm_client.get_dataproduct = self._mock_get_dataproduct_no_arn

        with self.assertRaises(RequiredCustomFieldNotSet):
            self._event_handler.handle(self._activated_event)

    def _mock_get_data_contract(self, datacontract_id: str):
        if datacontract_id == self._data_contract_id:
            return {
                'consumer': {
                    'dataProductId': self._consumer_dataproduct_id
                },
                'provider': {
                    'dataProductId': self._provider_dataproduct_id,
                    'outputPortId': self._output_port_id
                }
            }
        else:
            return None

    def _mock_get_dataproduct(self, dataproduct_id: str):
        if dataproduct_id == self._consumer_dataproduct_id:
            return {
                'custom': {
                    'aws-role-name': self._consumer_role_name
                }
            }
        elif dataproduct_id == self._provider_dataproduct_id:
            return {
                'outputPorts': [
                    {
                        'id': self._output_port_id,
                        'custom': {
                            'aws-arn': self._output_port_arn
                        }
                    }
                ]
            }
        else:
            return None

    def _mock_get_dataproduct_no_role(self, dataproduct_id: str):
        if dataproduct_id == self._consumer_dataproduct_id:
            return {
                'custom': {}
            }
        elif dataproduct_id == self._provider_dataproduct_id:
            return {
                'outputPorts': [
                    {
                        'id': self._output_port_id,
                        'custom': {
                            'aws-arn': self._output_port_arn
                        }
                    }
                ]
            }
        else:
            return None

    def _mock_get_dataproduct_no_arn(self, dataproduct_id: str):
        if dataproduct_id == self._consumer_dataproduct_id:
            return {
                'custom': {
                    'aws-role-name': self._consumer_role_name
                }
            }
        elif dataproduct_id == self._provider_dataproduct_id:
            return {
                'outputPorts': [
                    {
                        'id': self._output_port_id,
                        'custom': {}
                    }
                ]
            }
        else:
            return None


if __name__ == '__main__':
    unittest.main()
