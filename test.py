# -*- coding: UTF-8 -*-
# You can run this test script with `python -m unittest test`

from textwrap import dedent
from unittest import TestCase

from mock import Mock, patch

import insightly_slack_notify
import insightly_slack_notify_config as config


class ChangedOpportunitiesTestCase(TestCase):

    def setUp(self):
        local_opportunity = {
            "OPPORTUNITY_ID": 111,
            "OPPORTUNITY_NAME": "op111",
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

        patch('insightly_slack_notify.slack_post', Mock()).start()
        patch('insightly_slack_notify.shelve.open', lambda x: self.local_db).start()

    def tearDown(self):
        patch.stopall()

    def test_changed_bid_amount(self):
        # WHEN BID_AMOUNT changed
        insightly_response_chain = [
            [dict(self.local_db['opportunity_111'], BID_AMOUNT=2)],
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_changed_opportunities() is called
        insightly_slack_notify.notify_changed_opportunities()

        # THEN one slack message should be sent
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL,
            json={'text': 'Opportunity op111 changed:\nBid amount changed to 2'})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['BID_AMOUNT'] == 2)

    def test_changed_pipeline(self):
        # WHEN PIPELINE_ID and STAGE_ID changed
        insightly_response_chain = [
            [dict(self.local_db['opportunity_111'], PIPELINE_ID=222, STAGE_ID=222)],
            {'PIPELINE_NAME': 'New pipe'},
            {'STAGE_NAME': 'New stage'}
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_changed_opportunities() is called
        insightly_slack_notify.notify_changed_opportunities()

        # THEN one slack message should be sent
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL,
            json={'text': 'Opportunity op111 changed:\nPipeline changed to New pipe (New stage)'})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['PIPELINE_ID'] == 222)
        assert(self.local_db['opportunity_111']['STAGE_ID'] == 222)

    def test_changed_category(self):
        # WHEN CATEGORY_ID changed
        insightly_response_chain = [
            [dict(self.local_db['opportunity_111'], CATEGORY_ID=222)],
            {'CATEGORY_NAME': 'New category'},
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_changed_opportunities() is called
        insightly_slack_notify.notify_changed_opportunities()

        # THEN one slack message should be sent
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL,
            json={'text': 'Opportunity op111 changed:\nCategory changed to New category'})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['CATEGORY_ID'] == 222)


class NewOpportunitiesTestCase(TestCase):
    def setUp(self):
        self.new_opportunity = {
            "OPPORTUNITY_ID": 111,
            "OPPORTUNITY_NAME": "op111",
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

        patch('insightly_slack_notify.slack_post', Mock()).start()
        patch('insightly_slack_notify.shelve.open', lambda x: self.local_db).start()

    def tearDown(self):
        patch.stopall()

    def test_new_opportunity(self):
        insightly_response_chain = [
            [self.new_opportunity],
            {'FIRST_NAME': 'First', 'LAST_NAME': 'Last', 'EMAIL_ADDRESS': 'email@test.com'},
            {'CATEGORY_NAME': 'New category'},
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_changed_opportunities() is called
        insightly_slack_notify.notify_new_opportunities()

        # THEN one slack message should be sent
        expected_message = '''\
            New opportunity created: op111
            Value: 1 USD
            Category: New category
            Responsible user: First Last email@test.com
            Close date: 2016-03-31 00:00:00
            Description: dddddd'''
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL, json={'text': dedent(expected_message)})


class DeletedOpportunitiesTestCase(TestCase):
    def setUp(self):
        self.known_opportunity = {
            "OPPORTUNITY_ID": 111,
            "OPPORTUNITY_NAME": "op111",
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
        self.local_db = {'opportunity_111': self.known_opportunity, 'opportunities_ids': {111}}

        patch('insightly_slack_notify.slack_post', Mock()).start()
        patch('insightly_slack_notify.shelve.open', lambda x: self.local_db).start()

    def tearDown(self):
        patch.stopall()

    def test_delete_known_opportunity(self):
        insightly_response_chain = [[], ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_deleted_opportunities() is called
        insightly_slack_notify.notify_deleted_opportunities()

        # THEN one slack message should be sent
        expected_message = '''\
            Opportunity deleted: op111
            Description: dddddd'''
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL, json={'text': dedent(expected_message)})

    def test_delete_unknown_opportunity(self):
        insightly_response_chain = [
            [
                {"OPPORTUNITY_ID": 111, "OPPORTUNITY_NAME": "op111", "OPPORTUNITY_DETAILS": "dddddd"},
                {"OPPORTUNITY_ID": 222, "OPPORTUNITY_NAME": "op222", "OPPORTUNITY_DETAILS": "2"},
            ],
            [
                {"OPPORTUNITY_ID": 111, "OPPORTUNITY_NAME": "op111", "OPPORTUNITY_DETAILS": "dddddd"},
                # 222 was deleted
            ]
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_deleted_opportunities() is called first time
        insightly_slack_notify.notify_deleted_opportunities()

        # THEN unknown opportunity should be added to local db
        self.assertTrue('opportunity_222' in self.local_db)

        # AND no slack message should be sent
        self.assertEqual(insightly_slack_notify.slack_post.call_count, 0)

        # WHEN notify_deleted_opportunities() is called second time
        insightly_slack_notify.notify_deleted_opportunities()

        # THEN one slack message should be sent
        expected_message = '''\
            Opportunity deleted: op222
            Description: 2'''
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL, json={'text': dedent(expected_message)})

        # AND deleted opportunity should be deleted drom local db
        self.assertFalse('opportunity_222' in self.local_db)
        self.assertFalse(222 in self.local_db['opportunities_ids'])
