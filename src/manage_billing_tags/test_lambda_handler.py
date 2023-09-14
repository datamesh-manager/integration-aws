import datetime
from unittest import TestCase

import boto3
from botocore.stub import Stubber

from lambda_handler import CostExplorerTagging


class TestAWSCostExplorerTagging(TestCase):
    def setUp(self) -> None:
        cost_explorer = boto3.client('ce')

        self._cost_explorer_stubber = Stubber(cost_explorer)
        self._cost_explorer_tagging = CostExplorerTagging(cost_explorer)

    def test_list_values_for_tag_key(self):
        tag_key = 'a-key'
        tag_value = 'a-value'

        self._cost_explorer_stubber.add_response(
            'get_tags',
            {
                'Tags': [tag_value],
                'ReturnSize': 1,
                'TotalSize': 1
            },
            {
                'TimePeriod': {
                    'Start': f'{datetime.date.today().replace(day=1)}',
                    'End': f'{datetime.date.today()}'
                },
                'TagKey': tag_key
            }
        )

        self._cost_explorer_stubber.activate()

        result = self._cost_explorer_tagging.list_values_for_tag_key(tag_key)

        self.assertIs(1, len(result))
        self.assertIn(tag_value, result)

    # todo: test pagination
