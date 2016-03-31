# -*- coding: UTF-8 -*-
# You can run this test script with `python -m unittest test`

from textwrap import dedent
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
            "CATEGORY_ID": 111,
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
        insightly_response_chain = [
            [dict(self.local_db['opportunity_111'], BID_AMOUNT=2)],
        ]
        patch('insightly_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_changed_opportunities() is called
        insightly_notify.notify_changed_opportunities()

        # THEN one slack message should be sent
        insightly_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL, json={'text': 'Opportunity op2 changed:\nBid amount changed to 2'})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['BID_AMOUNT'] == 2)

    def test_changed_pipeline(self):
        # WHEN PIPELINE_ID and STAGE_ID changed
        insightly_response_chain = [
            [dict(self.local_db['opportunity_111'], PIPELINE_ID=222, STAGE_ID=222)],
            {'PIPELINE_NAME': 'New pipe'},
            {'STAGE_NAME': 'New stage'}
        ]
        patch('insightly_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_changed_opportunities() is called
        insightly_notify.notify_changed_opportunities()

        # THEN one slack message should be sent
        insightly_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL, json={'text': 'Opportunity op2 changed:\nPipeline changed to New pipe (New stage)'})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['PIPELINE_ID'] == 222)
        assert(self.local_db['opportunity_111']['STAGE_ID'] == 222)

    def test_changed_category(self):
        # WHEN CATEGORY_ID changed
        insightly_response_chain = [
            [dict(self.local_db['opportunity_111'], CATEGORY_ID=222)],
            {'CATEGORY_NAME': 'New category'},
        ]
        patch('insightly_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_changed_opportunities() is called
        insightly_notify.notify_changed_opportunities()

        # THEN one slack message should be sent
        insightly_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL, json={'text': 'Opportunity op2 changed:\nCategory changed to New category'})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['CATEGORY_ID'] == 222)


class NewOpportunitiesTestCase(TestCase):
    def setUp(self):
        self.new_opportunity = {
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
            "CATEGORY_ID": 111,
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
        self.local_db = {}

        patch('insightly_notify.slack_post', Mock()).start()
        patch('insightly_notify.shelve.open', lambda x: self.local_db).start()

    def tearDown(self):
        patch.stopall()

    def test_new_opportunity(self):
        insightly_response_chain = [
            [self.new_opportunity],
            {'FIRST_NAME': 'First', 'LAST_NAME': 'Last', 'EMAIL_ADDRESS': 'email@test.com'},
            {'CATEGORY_NAME': 'New category'},
        ]
        patch('insightly_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_changed_opportunities() is called
        insightly_notify.notify_new_opportunities()

        # THEN one slack message should be sent
        expected_message = '''\
            New opportunity created: op2
            Value: 1 USD
            Category: New category
            Responsible user: First Last email@test.com
            Close date: 2016-03-31 00:00:00
            Description: dddddd'''
        insightly_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL, json={'text': dedent(expected_message)})
