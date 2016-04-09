# -*- coding: UTF-8 -*-
# You can run this test script with `python -m unittest test`

from textwrap import dedent
from unittest import TestCase

from mock import Mock, patch

import insightly_slack_notify
import insightly_slack_notify_config as config


OPPORTUNITY_TEMPLATE = {
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


class ChangedOpportunitiesTestCase(TestCase):

    def setUp(self):
        # GIVEN local database with one opportunity
        self.local_db = {'opportunity_111': OPPORTUNITY_TEMPLATE}
        patch('insightly_slack_notify.shelve.open', lambda x: self.local_db).start()

        patch('insightly_slack_notify.slack_post', Mock()).start()

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
            json={'text': dedent(
                'Opportunity op111 changed:\n'
                'Bid amount changed to 2\n'
                'Url: https://googleapps.insight.ly/opportunities/details/111')})

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
            json={'text': dedent(
                'Opportunity op111 changed:\n'
                'Pipeline changed to New pipe (New stage)\n'
                'Url: https://googleapps.insight.ly/opportunities/details/111')})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['PIPELINE_ID'] == 222)
        assert(self.local_db['opportunity_111']['STAGE_ID'] == 222)

    def test_changed_pipeline_to_none(self):
        # WHEN PIPELINE_ID changed to None
        insightly_response_chain = [
            [dict(self.local_db['opportunity_111'], PIPELINE_ID=None, STAGE_ID=None)],
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_changed_opportunities() is called
        insightly_slack_notify.notify_changed_opportunities()

        # THEN one slack message should be sent
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL,
            json={'text': dedent(
                'Opportunity op111 changed:\n'
                'Pipeline changed to None\n'
                'Url: https://googleapps.insight.ly/opportunities/details/111')})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['PIPELINE_ID'] is None)
        assert(self.local_db['opportunity_111']['STAGE_ID'] is None)

    def test_changed_pipeline_without_stage(self):
        # WHEN PIPELINE_ID changed and STAGE_ID changed to None
        insightly_response_chain = [
            [dict(self.local_db['opportunity_111'], PIPELINE_ID=222, STAGE_ID=None)],
            {'PIPELINE_NAME': 'New pipe'},
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_changed_opportunities() is called
        insightly_slack_notify.notify_changed_opportunities()

        # THEN one slack message should be sent
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL,
            json={'text': dedent(
                'Opportunity op111 changed:\n'
                'Pipeline changed to New pipe (No stage)\n'
                'Url: https://googleapps.insight.ly/opportunities/details/111')})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['PIPELINE_ID'] == 222)
        assert(self.local_db['opportunity_111']['STAGE_ID'] is None)

    def test_changed_stage_to_none(self):
        # WHEN STAGE_ID changed to None
        insightly_response_chain = [
            [dict(self.local_db['opportunity_111'], STAGE_ID=None)],
            {'PIPELINE_NAME': 'New pipe'},
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_changed_opportunities() is called
        insightly_slack_notify.notify_changed_opportunities()

        # THEN one slack message should be sent
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL,
            json={'text': dedent(
                'Opportunity op111 changed:\n'
                'Stage changed to None\n'
                'Url: https://googleapps.insight.ly/opportunities/details/111')})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['PIPELINE_ID'] == 111)
        assert(self.local_db['opportunity_111']['STAGE_ID'] is None)

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
            json={'text': dedent(
                'Opportunity op111 changed:\n'
                'Category changed to New category\n'
                'Url: https://googleapps.insight.ly/opportunities/details/111')})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['CATEGORY_ID'] == 222)

    def test_changed_category_to_none(self):
        # WHEN CATEGORY_ID changed to None
        insightly_response_chain = [
            [dict(self.local_db['opportunity_111'], CATEGORY_ID=None)],
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_changed_opportunities() is called
        insightly_slack_notify.notify_changed_opportunities()

        # THEN one slack message should be sent
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL,
            json={'text': dedent(
                'Opportunity op111 changed:\n'
                'Category changed to None\n'
                'Url: https://googleapps.insight.ly/opportunities/details/111')})

        # AND local db opportunity should get updated
        assert(self.local_db['opportunity_111']['CATEGORY_ID'] is None)


class NewOpportunitiesTestCase(TestCase):
    def setUp(self):
        # GIVEN empty local db
        self.local_db = {}
        patch('insightly_slack_notify.shelve.open', lambda x: self.local_db).start()

        patch('insightly_slack_notify.slack_post', Mock()).start()

    def tearDown(self):
        patch.stopall()

    def test_new_opportunity_with_category_and_user(self):
        # GIVEN remote new opportunity with category and responsible user
        new_opportunity = dict(OPPORTUNITY_TEMPLATE, CATEGORY_ID=111, RESPONSIBLE_USER_ID=111)

        insightly_response_chain = [
            [new_opportunity],
            {'FIRST_NAME': 'First', 'LAST_NAME': 'Last', 'EMAIL_ADDRESS': 'email@test.com'},
            {'CATEGORY_NAME': 'New category'},
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # WHEN notify_changed_opportunities() is called
        insightly_slack_notify.notify_new_opportunities()

        # THEN one slack message should be sent
        expected_message = '''\
            New opportunity created: op111
            Value: 1 USD
            Category: New category
            Responsible user: First Last email@test.com
            Close date: 2016-03-31 00:00:00
            Description: dddddd
            Url: https://googleapps.insight.ly/opportunities/details/111'''
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL, json={'text': dedent(expected_message)})

    def test_new_opportunity_without_category(self):
        # GIVEN remote new opportunity without category
        new_opportunity_without_category = dict(OPPORTUNITY_TEMPLATE, CATEGORY_ID=None)

        insightly_response_chain = [
            [new_opportunity_without_category],
            {'FIRST_NAME': 'First', 'LAST_NAME': 'Last', 'EMAIL_ADDRESS': 'email@test.com'},
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # WHEN notify_changed_opportunities() is called
        insightly_slack_notify.notify_new_opportunities()

        # THEN one slack message should be sent
        expected_message = '''\
            New opportunity created: op111
            Value: 1 USD
            Category: None
            Responsible user: First Last email@test.com
            Close date: 2016-03-31 00:00:00
            Description: dddddd
            Url: https://googleapps.insight.ly/opportunities/details/111'''
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL, json={'text': dedent(expected_message)})

    def test_new_opportunity_without_user(self):
        # GIVEN remote new opportunity without responsible user
        new_opportunity_without_user = dict(OPPORTUNITY_TEMPLATE, RESPONSIBLE_USER_ID=None)

        insightly_response_chain = [
            [new_opportunity_without_user],
            {'CATEGORY_NAME': 'New category'},
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # WHEN notify_changed_opportunities() is called
        insightly_slack_notify.notify_new_opportunities()

        # THEN one slack message should be sent
        expected_message = '''\
            New opportunity created: op111
            Value: 1 USD
            Category: New category
            Responsible user: None
            Close date: 2016-03-31 00:00:00
            Description: dddddd
            Url: https://googleapps.insight.ly/opportunities/details/111'''
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL, json={'text': dedent(expected_message)})


class DeletedOpportunitiesTestCase(TestCase):
    def setUp(self):
        # GIVEN local db with one known opportunity
        self.local_db = {'opportunity_111': OPPORTUNITY_TEMPLATE, 'opportunities_ids': {111}}
        patch('insightly_slack_notify.shelve.open', lambda x: self.local_db).start()

        patch('insightly_slack_notify.slack_post', Mock()).start()

    def tearDown(self):
        patch.stopall()

    def test_delete_known_opportunity(self):
        # GIVEN remote end deleted all opportunities
        insightly_response_chain = [[], ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # WHEN notify_deleted_opportunities() is called
        insightly_slack_notify.notify_deleted_opportunities()

        # THEN one slack message should be sent
        expected_message = '''\
            Opportunity deleted: op111
            Description: dddddd'''
        insightly_slack_notify.slack_post.assert_called_once_with(
            config.SLACK_CHANNEL_URL, json={'text': dedent(expected_message)})

    def test_delete_unknown_opportunity(self):
        # GIVEN remote end with one new opportunity op222
        insightly_response_chain = [
            [
                {"OPPORTUNITY_ID": 111, "OPPORTUNITY_NAME": "op111", "OPPORTUNITY_DETAILS": "dddddd"},
                {"OPPORTUNITY_ID": 222, "OPPORTUNITY_NAME": "op222", "OPPORTUNITY_DETAILS": "2"},
            ]
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # WHEN notify_deleted_opportunities() is called first time
        insightly_slack_notify.notify_deleted_opportunities()

        # THEN unknown opportunity should be added to local db
        self.assertTrue('opportunity_222' in self.local_db)

        # AND no slack message should be sent
        self.assertEqual(insightly_slack_notify.slack_post.call_count, 0)

        # WHEN remote end deleted opportunity op222
        insightly_response_chain = [
            [
                {"OPPORTUNITY_ID": 111, "OPPORTUNITY_NAME": "op111", "OPPORTUNITY_DETAILS": "dddddd"},
                # op222 was deleted
            ]
        ]
        patch('insightly_slack_notify.insightly_get', Mock(side_effect=insightly_response_chain)).start()

        # AND notify_deleted_opportunities() is called second time
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
