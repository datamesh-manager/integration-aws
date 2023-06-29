import json
import unittest
from io import BytesIO

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber

from lambda_handler import TargetQueueClient, LastProcessedEventIdRepo


class TestTargetQueueClient(unittest.TestCase):

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


class TestLastProcessedEventIdRepo(unittest.TestCase):

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


if __name__ == '__main__':
    unittest.main()
