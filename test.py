# -*- coding: UTF-8 -*-
# You can run this test script with `python -m unittest test`

from unittest import TestCase

from mock import Mock, patch

import insightly_notify
import config


class ChangedOpportunitiesTestCase(TestCase):

    def setUp(self):
        local_opportunity = {
            "OPPORTUNITY_ID": 111,
            "OPPORTUNITY_NAME": "op2",
            "OPPORTUNITY_DETAILS": "dddddd",
            "PROBABILITY": 1,
            "BID_CURRENCY": "USD",
            "BID_AMOUNT": 1,
            "BID_TYPE": "Fixed Bid",
            "BID_DURATION": None,
            "FORECAST_CLOSE_DATE": "2016-03-31 00:00:00",
            "ACTUAL_CLOSE_DATE": None,
            "CATEGORY_ID": None,
            "PIPELINE_ID": 111,
            "STAGE_ID": 111,
            "OPPORTUNITY_STATE": "OPEN",
            "IMAGE_URL": "http://s3.amazonaws.com/insightly.userfiles/643478/",
            "RESPONSIBLE_USER_ID": 111,
            "OWNER_USER_ID": 111,
            "DATE_CREATED_UTC": "2016-03-28 13:11:50",
            "DATE_UPDATED_UTC": "2016-03-29 12:03:56",
            "VISIBLE_TO": "EVERYONE",
            "VISIBLE_TEAM_ID": None,
            "VISIBLE_USER_IDS": None,
            "CUSTOMFIELDS": [],
            "TAGS": [],
            "LINKS": [],
            "EMAILLINKS": []}

        self.local_db = {'opportunity_111': local_opportunity}

        patch('insightly_notify.slack_post', Mock()).start()
        patch('insightly_notify.shelve.open', lambda x: self.local_db).start()

    def tearDown(self):
        patch.stopall()

    def test_changed_bid_amount(self):
        # WHEN BID_AMOUNT changed
        insightly_get_returns = [
            [dict(self.local_db['opportunity_111'], BID_AMOUNT=2)],
        ]
        patch('insightly_notify.insightly_get', Mock(side_effect=insightly_get_returns)).start()

        # AND notify_changed_opportunities() is called
        insightly_notify.notify_changed_opportunities()

        # THEN one slack message should be sent
        insightly_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL, json={'text': 'Bid amount changed to 2'})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['BID_AMOUNT'] == 2)

    def test_changed_pipeline(self):
        # WHEN PIPELINE_ID and STAGE_ID changed
        insightly_get_returns = [
            [dict(self.local_db['opportunity_111'], PIPELINE_ID=222, STAGE_ID=222)],
            {'PIPELINE_NAME': 'New pipe'},
            {'STAGE_NAME': 'New stage'}
        ]
        patch('insightly_notify.insightly_get', Mock(side_effect=insightly_get_returns)).start()

        # AND notify_changed_opportunities() is called
        insightly_notify.notify_changed_opportunities()

        # THEN one slack message should be sent
        insightly_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL, json={'text': 'Pipeline changed to New pipe (New stage)'})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['PIPELINE_ID'] == 222)
        assert(self.local_db['opportunity_111']['STAGE_ID'] == 222)
