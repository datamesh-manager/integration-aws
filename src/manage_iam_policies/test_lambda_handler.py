import json
import unittest
from unittest import TestCase
from unittest.mock import patch, sentinel, Mock

import boto3
from botocore.stub import Stubber

from lambda_handler import Secrets, DMMClient, AWSIAMManager, EventHandler, \
    UnsupportedOutputPortException, RequiredCustomFieldNotSet


class TestDMMClient(TestCase):
    _base_url = 'https://dmm-url.com'
    _api_key = 'supersecret'
    _data_usage_agreement_id = '123'
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

    # get_data_usage_agreement

    @staticmethod
    def mock_get_data_usage_agreement(**kwargs) -> MockResponse:
        expected_url = '{base_url}/api/datausageagreements/{id}'.format(
            base_url=TestDMMClient._base_url,
            id=TestDMMClient._data_usage_agreement_id)

        if kwargs['url'] == expected_url:
            return TestDMMClient.MockResponse(sentinel.expected, 200)
        else:
            return TestDMMClient.MockResponse(None, 200)

    @patch('requests.get', Mock(side_effect=mock_get_data_usage_agreement))
    def test_get_data_usage_agreement(self) -> None:
        self.assertEqual(sentinel.expected,
                         self._client.get_data_usage_agreement(self._data_usage_agreement_id))

    @staticmethod
    def mock_get_data_usage_agreement_not_found(**kwargs) -> MockResponse:
        return TestDMMClient.MockResponse(sentinel.something, 404)

    @patch('requests.get', Mock(side_effect=mock_get_data_usage_agreement_not_found))
    def test_get_data_usage_agreement_not_found(self) -> None:
        self.assertEqual(None,
                         self._client.get_data_usage_agreement(self._data_usage_agreement_id))

    @staticmethod
    def mock_get_data_usage_agreement_other_error() -> MockResponse:
        return TestDMMClient.MockResponse(sentinel.something, 500)

    @patch('requests.get', Mock(side_effect=mock_get_data_usage_agreement_other_error))
    def test_get_data_usage_agreement_other_error(self) -> None:
        with self.assertRaises(Exception):
            self._client.get_data_usage_agreement(self._data_usage_agreement_id)

    @patch('requests.get', Mock(side_effect=mock_get__api_key))
    def test_get_data_usage_agreement_api_key(self) -> None:
        self.assertEqual(sentinel.expected,
                         self._client.get_data_usage_agreement(self._data_usage_agreement_id))

    # patch_data_usage_agreement

    @staticmethod
    def mock_get_data_usage_agreement__patch(**kwargs) -> MockResponse:
        return TestDMMClient.MockResponse({
            'key1': 'value1',
            'key2': 'value2'
        }, 200)

    @staticmethod
    def mock_put_data_usage_agreement__patch(**kwargs) -> MockResponse:
        expected_url = '{base_url}/api/datausageagreements/{id}'.format(
            base_url=TestDMMClient._base_url,
            id=TestDMMClient._data_usage_agreement_id)

        expected_body = {
            'key1': 'value1',
            'key2': 'value2_updated',
            'key3': 'value3'
        }

        assert kwargs['headers']['x-api-key'] == TestDMMClient._api_key
        assert kwargs['url'] == expected_url
        assert kwargs['json'] == expected_body

        return TestDMMClient.MockResponse(None, 200)

    @patch('requests.get', Mock(side_effect=mock_get_data_usage_agreement__patch))
    @patch('requests.put', Mock(side_effect=mock_put_data_usage_agreement__patch))
    def test_patch_data_usage_agreement(self) -> None:
        value = {'key2': 'value2_updated', 'key3': 'value3'}
        self._client.patch_data_usage_agreement(self._data_usage_agreement_id, value)

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


class TestAWSIAMManager(TestCase):
    _data_usage_agreement_id = '123-123-321'
    _consumer_role_name = 'hi_iam_a_consumer_role'
    _policy_name = 'DMM_DataUsageAgreement_{}'.format(_data_usage_agreement_id)

    _s3_output_port_bucket_arn = 'arn:aws:s3:one:two:three'
    _s3_output_port_folder_arn = 'arn:aws:s3:one:two:three/folder'

    _glue_output_port_catalog_arn = 'arn:aws:glue:catalog'
    _glue_output_port_database_arn = 'arn:aws:glue:database/name'
    _glue_output_port_table_arn = 'arn:aws:glue:table/name/name'

    _athena_output_port_workgroup_arn = 'arn:aws:athena:workgroup/primary'

    def setUp(self) -> None:
        iam = boto3.client('iam')

        self._iam_stubber = Stubber(iam)
        self._iam_manager = AWSIAMManager(iam)

    def tearDown(self) -> None:
        self._iam_stubber.deactivate()

    def test_remove_access(self) -> None:
        self._iam_stubber.add_response(
            'delete_role_policy',
            {},
            {
                'RoleName': self._consumer_role_name,
                'PolicyName': self._policy_name
            }
        )
        self._iam_stubber.activate()

        self._iam_manager.remove_access(self._data_usage_agreement_id,
                                        self._consumer_role_name)

        self._iam_stubber.assert_no_pending_responses()

    def test_remove_access_not_found(self) -> None:
        self._iam_stubber.add_client_error(
            'delete_role_policy',
            service_error_code='NoSuchEntity',
            expected_params={
                'RoleName': self._consumer_role_name,
                'PolicyName': self._policy_name
            }
        )
        self._iam_stubber.activate()

        self._iam_manager.remove_access(self._data_usage_agreement_id,
                                        self._consumer_role_name)

    def test_grant_access_unsupported(self) -> None:
        with self.assertRaises(UnsupportedOutputPortException):
            self._iam_manager.grant_access(self._data_usage_agreement_id,
                                           self._consumer_role_name,
                                           'iam',
                                           ['aws:arn:iam:one:two:three'])

    def test_grant_access_s3_bucket(self) -> None:
        self._iam_stubber.add_response(
            'put_role_policy',
            {},
            {
                'RoleName': self._consumer_role_name,
                'PolicyName': 'DMM_DataUsageAgreement_{}'.format(
                    self._data_usage_agreement_id),
                'PolicyDocument': json.dumps({
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Allow',
                            'Action': [
                                's3:GetBucketLocation',
                                's3:GetObject',
                                's3:ListBucket'
                            ],
                            'Resource': [
                                self._s3_output_port_bucket_arn,
                                '{}/*'.format(self._s3_output_port_bucket_arn)
                            ]
                        }
                    ]
                })
            }
        )

        self._iam_stubber.activate()

        result = self._iam_manager.grant_access(self._data_usage_agreement_id,
                                                self._consumer_role_name,
                                                's3_bucket',
                                                [self._s3_output_port_bucket_arn])

        expected = 'DMM_DataUsageAgreement_{}'.format(self._data_usage_agreement_id)
        self.assertEqual(expected, result)

        self._iam_stubber.assert_no_pending_responses()

    def test_grant_access_glue_table(self) -> None:
        self._iam_stubber.add_response(
            'put_role_policy',
            {},
            {
                'RoleName': self._consumer_role_name,
                'PolicyName': 'DMM_DataUsageAgreement_{}'.format(
                    self._data_usage_agreement_id),
                'PolicyDocument': json.dumps({
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Allow',
                            'Action': [
                                's3:ListBucket'
                            ],
                            'Resource': [
                                self._s3_output_port_bucket_arn
                            ]
                        },
                        {
                            'Effect': 'Allow',
                            'Action': [
                                's3:GetObject'
                            ],
                            'Resource': [
                                '{}/*'.format(self._s3_output_port_folder_arn)
                            ]
                        },
                        {
                            'Effect': 'Allow',
                            'Action': [
                                'glue:GetTable'
                            ],
                            'Resource': [
                                self._glue_output_port_catalog_arn,
                                self._glue_output_port_database_arn,
                                self._glue_output_port_table_arn
                            ]
                        },
                        {
                            'Effect': 'Allow',
                            'Action': [
                                'athena:StartQueryExecution'
                            ],
                            'Resource': [
                                self._athena_output_port_workgroup_arn
                            ]
                        }
                    ]
                })
            }
        )

        self._iam_stubber.activate()

        result = self._iam_manager.grant_access(
            self._data_usage_agreement_id,
            self._consumer_role_name,
            'glue_table',
            [self._s3_output_port_folder_arn,
             self._glue_output_port_catalog_arn,
             self._glue_output_port_database_arn,
             self._glue_output_port_table_arn,
             self._athena_output_port_workgroup_arn])

        expected = 'DMM_DataUsageAgreement_{}'.format(self._data_usage_agreement_id)
        self.assertEqual(expected, result)

        self._iam_stubber.assert_no_pending_responses()


class TestEventHandler(TestCase):
    _event_id = '123-123-123-123'
    _data_usage_agreement_id = '999-888-777'
    _consumer_role_name = 'consumer_role_123'
    _consumer_dataproduct_id = 'asdf-123-asdf'
    _output_port_id = '456-6454-545'
    _output_port_arn = 'arn:aws:service:output:port'
    _output_port_type = 'output_type'
    _provider_dataproduct_id = 'qwer-321-qwer'
    _policy_name = 'DMM_DataUsageAgreement_asdf-123-asdf'

    _activated_event = {
        'id': _event_id,
        'type': 'com.datamesh-manager.events.DataUsageAgreementActivatedEvent',
        'data': {'id': _data_usage_agreement_id}
    }

    @patch('lambda_handler.AWSIAMManager')
    @patch('lambda_handler.DMMClient')
    def setUp(self, dmm_client, iam_manager) -> None:
        self._dmm_client = dmm_client
        self._iam_manager = iam_manager
        self._event_handler = EventHandler(dmm_client, iam_manager)

    def tearDown(self) -> None:
        self._dmm_client.reset_mock()
        self._iam_manager.reset_mock()

    def test_handle__ignore_others(self) -> None:
        event = {
            'id': self._event_id,
            'type': 'com.datamesh-manager.events.OtherEvent'
        }
        self._event_handler.handle(event)
        self._iam_manager.grant_access.assert_not_called()
        self._iam_manager.remove_access.assert_not_called()

    def test_handle__deactivated(self) -> None:
        self._dmm_client.get_data_usage_agreement = \
            self._mock_get_data_usage_agreement
        self._dmm_client.get_dataproduct = \
            self._mock_get_dataproduct

        event = {
            'id': self._event_id,
            'type': 'com.datamesh-manager.events.DataUsageAgreementDeactivatedEvent',
            'data': {'id': self._data_usage_agreement_id}
        }
        self._event_handler.handle(event)

        self._iam_manager.remove_access.assert_called_with(
            self._data_usage_agreement_id,
            self._consumer_role_name)

        self._dmm_client.patch_data_usage_agreement.assert_called_with(
            self._data_usage_agreement_id,
            {
                'tags': ['aws-integration', 'aws-integration-inactive']
            }
        )

    def test_handle__deactivated__contract_not_found(self) -> None:
        self._dmm_client.get_data_usage_agreement = \
            self._mock_get_data_usage_agreement

        event = {
            'id': self._event_id,
            'type': 'com.datamesh-manager.events.DataUsageAgreementDeactivatedEvent',
            'data': {'id': 'something_else'}
        }
        self._event_handler.handle(event)

        self._iam_manager.remove_access.assert_not_called()

    def test_handle__activated(self) -> None:
        self._dmm_client.get_data_usage_agreement = self._mock_get_data_usage_agreement
        self._dmm_client.get_dataproduct = self._mock_get_dataproduct
        self._iam_manager.grant_access.return_value = self._policy_name

        self._event_handler.handle(self._activated_event)

        self._iam_manager.grant_access.assert_called_with(
            self._data_usage_agreement_id,
            self._consumer_role_name,
            self._output_port_type,
            [self._output_port_arn])
        self._dmm_client.patch_data_usage_agreement.assert_called_with(
            self._data_usage_agreement_id,
            {
                'custom': {'aws-policy-name': self._policy_name},
                'tags': ['aws-integration', 'aws-integration-active']
            }
        )

    def test_handle__activated__consumer_role_not_set(self) -> None:
        self._dmm_client.get_data_usage_agreement = self._mock_get_data_usage_agreement
        self._dmm_client.get_dataproduct = self._mock_get_dataproduct_no_role

        with self.assertRaises(RequiredCustomFieldNotSet):
            self._event_handler.handle(self._activated_event)

    def test_handle__activated__provider_arn_not_set(self) -> None:
        self._dmm_client.get_data_usage_agreement = self._mock_get_data_usage_agreement
        self._dmm_client.get_dataproduct = self._mock_get_dataproduct_no_arn

        with self.assertRaises(RequiredCustomFieldNotSet):
            self._event_handler.handle(self._activated_event)

    def test_handle__activated__contract_not_found(self) -> None:
        self._dmm_client.get_data_usage_agreement.return_value = None

        self._event_handler.handle(self._activated_event)

        self._iam_manager.grant_access.assert_not_called()
        self._dmm_client.patch_data_usage_agreement.assert_not_called()

    def _mock_get_data_usage_agreement(self, data_usage_agreement_id: str):
        if data_usage_agreement_id == self._data_usage_agreement_id:
            return {
                'info': {
                    'id': self._data_usage_agreement_id
                },
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
                            'output-port-type': self._output_port_type,
                            'aws-s3-bucket-arn': self._output_port_arn
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
                            'aws-s3-bucket-arn': self._output_port_arn
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
