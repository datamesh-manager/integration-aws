import json
import unittest
from io import BytesIO
from unittest import TestCase
from unittest.mock import sentinel, patch, call, Mock

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber

from lambda_handler import TargetQueueClient, LastProcessedEventIdRepo, \
    DMMEventsClient, Secrets, FeedProcessor, DMMEvent


class TestTargetQueueClient(TestCase):

    def setUp(self) -> None:
        self._queue_url = 'a_queue_url'

        sqs = boto3.client('sqs')

        self._sqs_stubber = Stubber(sqs)
        self._queue_client = TargetQueueClient(sqs, self._queue_url)

    def tearDown(self) -> None:
        self._sqs_stubber.deactivate()

    def test_send_message(self) -> None:
        message_id = '123'
        message = {'hello': 'world'}

        expected_params = {
            'QueueUrl': self._queue_url,
            'MessageBody': json.dumps(message),
            'MessageDeduplicationId': message_id,
            'MessageGroupId': '1'
        }
        self._sqs_stubber.add_response(
            'send_message',
            {},
            expected_params
        )
        self._sqs_stubber.activate()

        self._queue_client.send_message(message, message_id)


class TestLastProcessedEventIdRepo(TestCase):

    def setUp(self) -> None:
        s3 = boto3.client('s3')
        self._s3_stubber = Stubber(s3)
        self._bucket = 'a_bucket'
        self._key = 'a_key'
        self._repo = LastProcessedEventIdRepo(s3, self._bucket, self._key)

    def tearDown(self) -> None:
        self._s3_stubber.deactivate()

    def test_get_last_event_id(self) -> None:
        an_id = 'an_id'
        an_id_encoded = an_id.encode('utf-8')

        self._s3_stubber.add_response(
            'get_object',
            {'Body': StreamingBody(BytesIO(an_id_encoded), len(an_id_encoded))},
            {'Bucket': self._bucket, 'Key': self._key}
        )
        self._s3_stubber.activate()

        self.assertEqual(an_id, self._repo.get_last_event_id())

    def test_get_last_event_id_not_found(self) -> None:
        self._s3_stubber.add_client_error(
            'get_object',
            'NoSuchKey',
            expected_params={'Bucket': self._bucket, 'Key': self._key}
        )
        self._s3_stubber.activate()

        self.assertIsNone(self._repo.get_last_event_id())

    def test_put_last_event_id(self) -> None:
        the_id = 'the_new_id'

        expected_params = {
            'Body': the_id,
            'Bucket': self._bucket,
            'Key': self._key
        }
        self._s3_stubber.add_response(
            'put_object',
            {},
            expected_params
        )
        self._s3_stubber.activate()

        self._repo.put_last_event_id(the_id)


class TestDMMEventsClient(TestCase):
    _base_url = 'https://dmm-url.com'
    _last_event_id = '123'
    _api_key = 'supersecret'

    def setUp(self) -> None:
        self._client = DMMEventsClient(self._base_url, self._api_key)

    class MockResponse:
        def __init__(self, body, status):
            self._body = body
            self._status = status

        def json(self) -> str:
            return self._body

        def raise_for_status(self) -> None:
            if self._status >= 400:
                raise Exception()

    @staticmethod
    def mock_get_events_without_last_event_id(**kwargs) -> MockResponse:
        expected_url = '{}/api/events'.format(TestDMMEventsClient._base_url)

        if kwargs['url'] == expected_url:
            return TestDMMEventsClient.MockResponse(sentinel.expected, 200)
        else:
            return TestDMMEventsClient.MockResponse(None, 200)

    @patch('requests.get',
           Mock(side_effect=mock_get_events_without_last_event_id))
    def test_get_events_without_last_event_id(self) -> None:
        self.assertEqual(sentinel.expected, self._client.get_events(None))

    @staticmethod
    def mock_get_events_with_last_event_id(**kwargs) -> MockResponse:
        expected_url = \
            '{base_url}/api/events?lastEventId={last_event_id}'.format(
                base_url=TestDMMEventsClient._base_url,
                last_event_id=TestDMMEventsClient._last_event_id
            )

        if kwargs['url'] == expected_url:
            return TestDMMEventsClient.MockResponse(sentinel.expected, 200)
        else:
            return TestDMMEventsClient.MockResponse(None, 200)

    @patch('requests.get', Mock(side_effect=mock_get_events_with_last_event_id))
    def test_get_events_with_last_event_id(self) -> None:
        self.assertEqual(sentinel.expected,
                         self._client.get_events(self._last_event_id))

    @staticmethod
    def mock_get_events_api_key(**kwargs) -> MockResponse:
        if kwargs['headers']['x-api-key'] != TestDMMEventsClient._api_key:
            return TestDMMEventsClient.MockResponse(None, 403)
        else:
            return TestDMMEventsClient.MockResponse(None, 200)

    @patch('requests.get', Mock(side_effect=mock_get_events_api_key))
    def test_get_events_api_key(self) -> None:
        client = DMMEventsClient(self._base_url, 'wrong api key')
        with self.assertRaises(Exception):
            client.get_events(None)

    @staticmethod
    def mock_get_events_accept_header(**kwargs) -> MockResponse:
        if kwargs['headers']['accept'] != 'application/cloudevents-batch+json':
            return TestDMMEventsClient.MockResponse(None, 400)
        else:
            return TestDMMEventsClient.MockResponse(sentinel.expected, 200)

    @patch('requests.get', Mock(side_effect=mock_get_events_accept_header))
    def test_get_events_accept_header(self) -> None:
        self.assertEqual(sentinel.expected, self._client.get_events(None))


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


class TestFeedProcessor(TestCase):
    _id_1 = '123'
    _event_1 = {'id': _id_1}

    _id_2 = '321'
    _event_2 = {'id': _id_2}

    @patch('lambda_handler.TargetQueueClient')
    @patch('lambda_handler.DMMEventsClient')
    @patch('lambda_handler.LastProcessedEventIdRepo')
    def setUp(self,
        last_processed_event_id_repo_mock,
        dmm_events_client_mock,
        target_queue_client_mock) -> None:

        self._last_processed_event_id_repo_mock = \
            last_processed_event_id_repo_mock
        self._dmm_events_client_mock = dmm_events_client_mock
        self._target_queue_client_mock = target_queue_client_mock

        # basic mocks
        self._last_processed_event_id_repo_mock.get_last_event_id = lambda: None
        self._dmm_events_client_mock.get_events = \
            self._process_new_events__get_events_mock

        self._feed_processor = FeedProcessor(
            self._last_processed_event_id_repo_mock,
            self._dmm_events_client_mock,
            self._target_queue_client_mock)

    def tearDown(self) -> None:
        self._last_processed_event_id_repo_mock.reset_mock()
        self._dmm_events_client_mock.reset_mock()
        self._target_queue_client_mock.reset_mock()

    @staticmethod
    def _process_new_events__get_events_mock(
        last_event_id: str | None) -> list[DMMEvent]:

        if last_event_id is None:
            return [TestFeedProcessor._event_1, TestFeedProcessor._event_2]
        else:
            return []

    def test_process_new_events__sends_message(self) -> None:
        self._feed_processor.process_new_events()

        self._target_queue_client_mock.send_message \
            .assert_has_calls([call(self._event_1, self._id_1),
                               call(self._event_2, self._id_2)])

    def test_process_new_events__put_last_event_id(self) -> None:
        self._feed_processor.process_new_events()

        self._last_processed_event_id_repo_mock.put_last_event_id \
            .assert_has_calls([call(self._id_1), call(self._id_2)])

    def test_process_new_events__order_of_calls(self) -> None:
        expected = ['send_message {}'.format(self._id_1),
                    'event_id {}'.format(self._id_1),
                    'send_message {}'.format(self._id_2),
                    'event_id {}'.format(self._id_2)]
        result = []

        self._target_queue_client_mock \
            .send_message.side_effect = lambda m, i: \
            result.append('send_message {}'.format(i))

        self._last_processed_event_id_repo_mock \
            .put_last_event_id.side_effect = lambda i: \
            result.append('event_id {}'.format(i))

        self._feed_processor.process_new_events()

        self.assertEqual(expected, result)



    def test_process_new_events__existing_event_id(self) -> None:
        # override get_last_event_id mock
        self._last_processed_event_id_repo_mock.get_last_event_id = \
            lambda: self._id_2

        self._feed_processor.process_new_events()

        self._last_processed_event_id_repo_mock.put_last_event_id \
            .assert_not_called()


if __name__ == '__main__':
    unittest.main()
