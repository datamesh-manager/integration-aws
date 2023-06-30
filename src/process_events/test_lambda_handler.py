import unittest
from unittest import TestCase

import boto3
from botocore.stub import Stubber

from lambda_handler import Secrets


class TestSecrets(TestCase):
    _secret_name = 'a_name'
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


if __name__ == '__main__':
    unittest.main()
