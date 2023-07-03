import json
import unittest
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch, sentinel, Mock

import boto3
from botocore.stub import Stubber

from lambda_handler import Secrets, DMMClient, AccessManager, \
    UnsupportedServiceException


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
    _output_port_arn = 'arn:aws:s3:one:two:three'
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
                        self._output_port_arn,
                        '{}/*'.format(self._output_port_arn)
                    ]
                }
            ]
        }

        self._stub_create_policy(expected_document)
        self._stub_attach_role_policy()

        self._iam_stubber.activate()

        self._access_manager.grant_access(self._datacontract_id,
                                          self._consumer_role_name,
                                          self._output_port_arn)

        self._iam_stubber.assert_no_pending_responses()

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

    def test_grant_access_unsupported(self) -> None:
        with self.assertRaises(UnsupportedServiceException):
            self._access_manager.grant_access(self._datacontract_id,
                                              self._consumer_role_name,
                                              "aws:arn:iam:one:two:three")

    def test_remove_access(self) -> None:
        pass

    def test_remove_access_policy_not_found(self) -> None:
        pass


if __name__ == '__main__':
    unittest.main()
