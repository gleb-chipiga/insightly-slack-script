#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from __future__ import print_function

import json
import logging
import logging.config
import os
import re
import shelve

from datetime import datetime
from collections import defaultdict
from copy import copy
from os.path import abspath, dirname, exists, join
from shutil import copyfile
from textwrap import dedent

import requests

if not exists('insightly_slack_notify_config.py'):
    print('*** Creating default config file insightly_slack_notify_config.py')
    copyfile('insightly_slack_notify_config.py.example',
             'insightly_slack_notify_config.py')

import insightly_slack_notify_config as config # noqa

INSIGHTLY_URL = 'https://api.insight.ly/v2.1'

NEW_MESSAGE = """\
New opportunity created: {OPPORTUNITY_NAME}
Value: {BID_AMOUNT} {BID_CURRENCY}
Category: {CATEGORY}
Responsible user: {RESPONSIBLE_USER}
Close date: {FORECAST_CLOSE_DATE}
Description: {OPPORTUNITY_DETAILS}
Url: https://googleapps.insight.ly/opportunities/details/{OPPORTUNITY_ID}"""

CHANGED_MESSAGE = """\
Opportunity {OPPORTUNITY_NAME} changed:\n{changes}\
Url: https://googleapps.insight.ly/opportunities/details/{OPPORTUNITY_ID}
Responsible user: {RESPONSIBLE_USER}"""

DELETED_MESSAGE = """\
Opportunity deleted: {OPPORTUNITY_NAME}
Description: {OPPORTUNITY_DETAILS}"""


def insightly_get(path, auth):
    """
    Send GET response. Raise exception if response status code is not 200.
    """
    response = requests.get(INSIGHTLY_URL + path, auth=auth)
    if response.status_code != 200:
        err = Exception('Insightly api GET error: Http status {}. Url:\n{}'
                        .format(response.status_code, INSIGHTLY_URL + path))
        logging.critical(err)
        raise err

    return json.loads(response.content)


def slack_post(url, *args, **kwargs):
    """
    Send POST response. Raise exception if response status code is not 200.
    """
    response = requests.post(url, *args, **kwargs)
    if response.status_code != 200:
        err = Exception('Slack api POST error: Http status {}. Url:\n{}'
                        .format(response.status_code, url))
        logging.critical(err)
        raise err
    return response


def configure():
    """
    Apply configuration from config.py
    """

    if hasattr(config, 'LOG_FILE'):
        LOG_FILE = abspath(config.LOG_FILE)
        print('Log messages will be sent to {}'.format(LOG_FILE))
    else:
        LOG_FILE = '/var/log/insightly_notify.log'
        print('Log messages will be sent to {}. You can change LOG_FILE in '
              'the config.'.format(LOG_FILE))

    # Test write permissions in the log file directory.
    permissons_test_path = join(dirname(LOG_FILE), 'insightly_test.log')
    try:
        with open(permissons_test_path, 'w+') as test_file:
            test_file.write('test')
        os.remove(permissons_test_path)
    except (OSError, IOError) as e:
        raise Exception(dedent('Write to the "{}/" directory failed. Please '
                               'check permissions or change LOG_FILE config. '
                               'Original error was: {}.'
                               .format(dirname(LOG_FILE), e)))

    LOG_LEVEL = getattr(config, 'LOG_LEVEL', 'INFO')

    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'verbose': {
                'format': '%(levelname)s %(asctime)s %(module)s.py: '
                          '%(message)s',
                'datefmt': '<%Y-%m-%d %H:%M:%S>'
            },
            'simple': {'format': '%(levelname)s %(module)s.py: %(message)s'},
        },
        'handlers': {
            'log_file': {
                'level': LOG_LEVEL,
                'class': 'logging.handlers.WatchedFileHandler',
                'filename': LOG_FILE,
                'formatter': 'verbose'
            },
            'console': {
                'level': LOG_LEVEL,
                'class': 'logging.StreamHandler',
                'formatter': 'simple'
            },
        },
        'loggers': {
            '': {'handlers': ['log_file', 'console'], 'level': LOG_LEVEL},
        }
    })

    try:
        from insightly_slack_notify_config import INSIGHTLY_API_KEY
        from insightly_slack_notify_config import SLACK_CHANNEL_URL
    except Exception as e:
        logging.critical('Please set required config varialble in '
                         'insightly_slack_notify_config.py:\n{}'.format(e))
        raise

    if not re.match(r'\w{8}-\w{4}-\w{4}-\w{4}-\w{12}', INSIGHTLY_API_KEY):
        err = Exception('INSIGHTLY_API_KEY has wrong format "{}", please set '
                        'the right value in insightly_slack_notify_config.py'
                        .format(INSIGHTLY_API_KEY))
        logging.critical(err)
        raise err

    if not re.match(r'https://hooks.slack.com/services/\w+/\w+/\w+',
                    SLACK_CHANNEL_URL):
        err = Exception('SLACK_CHANNEL_URL has wrong format "{}", please set '
                        'the right value in insightly_slack_notify_config.py'
                        .format(SLACK_CHANNEL_URL))
        logging.critical(err)
        raise err


def notify_new_opportunities():
    """
    Fetch new opportunities using insightly api. Send slack message on each
    new opportunity.
    """
    # Persistent file storage will keep track of last poll time.
    db = shelve.open('db.shelve')

    # Tuple (user, password) for request authentication.
    # User should be the api key, password is empty.
    auth = (config.INSIGHTLY_API_KEY, '')

    now = datetime.utcnow()

    if 'last_poll' not in db:
        db['last_poll'] = now
        logging.info('*** insightly_notify is launched first time, previously '
                     'created opportunities are ignored.')

    last_poll = db['last_poll'].strftime('%Y-%m-%dT%H:%M:%S')

    new_opportunities = insightly_get(
        '/opportunities?$filter=DATE_CREATED_UTC%20gt%20DateTime\'{}\''
        .format(last_poll),
        auth
    )

    db['last_poll'] = now

    logging.info('%d new opportunities found.' % len(new_opportunities))

    for opp in new_opportunities:

        # Fetch responsible user info.
        if opp['RESPONSIBLE_USER_ID']:
            userdata = insightly_get(
                '/users/{}'.format(opp['RESPONSIBLE_USER_ID']), auth)
            opp['RESPONSIBLE_USER'] = ('{FIRST_NAME} {LAST_NAME} '
                                       '{EMAIL_ADDRESS}'.format(**userdata))
        else:
            opp['RESPONSIBLE_USER'] = None

        # Fetch category info.
        if opp['CATEGORY_ID']:
            category = insightly_get(
                '/OpportunityCategories/{}'.format(opp['CATEGORY_ID']),
                auth)
            opp['CATEGORY'] = category['CATEGORY_NAME']
        else:
            opp['CATEGORY'] = None

        # The message template to send to slack.
        message = NEW_MESSAGE.format(**opp)

        # Send message to slack.
        slack_post(config.SLACK_CHANNEL_URL, json={'text': dedent(message)})


def notify_changed_opportunities():
    """
    Fetch changed opportunities using insightly api.
    Send slack message on each changed opportunity.
    """
    db = shelve.open('db.shelve')

    auth = (config.INSIGHTLY_API_KEY, '')

    now = datetime.utcnow()

    if 'changed_opportunities_last_poll_time' not in db:
        db['changed_opportunities_last_poll_time'] = now
        logging.info('*** insightly_notify is launched first time, previously '
                     'changed opportunities are ignored.')

    last_poll = (db['changed_opportunities_last_poll_time']
                 .strftime('%Y-%m-%dT%H:%M:%S'))

    changed_opportunities = insightly_get(
        '/opportunities?$filter=DATE_UPDATED_UTC%20gt%20DateTime\'{}\''
        .format(last_poll),
        auth
    )

    new_notes = insightly_get(
        '/notes?$filter=DATE_CREATED_UTC%20gt%20DateTime\'{}\''
        .format(last_poll),
        auth
    )
    opportunities_with_new_notes = defaultdict(list)

    for note in new_notes:
        for link in note['NOTELINKS']:
            if link.get('OPPORTUNITY_ID'):
                opp_id = link.get('OPPORTUNITY_ID')
                opportunities_with_new_notes[opp_id].append(note)

    db['changed_opportunities_last_poll_time'] = now

    for opp in copy(changed_opportunities):
        # Assign LOCAL_ID to opportunity.
        opp['LOCAL_ID'] = 'opportunity_%s' % opp['OPPORTUNITY_ID']

        # Clear list from new opportunities, we only handle changed ones here.
        if opp['LOCAL_ID'] not in db:
            # This is new opportunitiy, add to the local database and
            # remove from changed list.
            db[opp['LOCAL_ID']] = opp
            changed_opportunities.remove(opp)
        else:
            local_opp = db[opp['LOCAL_ID']]

            # Make list of changed fields.
            changed_fields = [x for x in opp if opp.get(x) != local_opp.get(x)]

            nnotes = opp['OPPORTUNITY_ID'] not in opportunities_with_new_notes
            if not changed_fields and nnotes:
                # This opportunity is not really changed.
                # Insightly seems to cache the response list and we can get
                # false positives. Remove this opportunity from changed list.
                changed_opportunities.remove(opp)

    logging.info('{} changed opportunities found.'
                 .format(len(changed_opportunities)))

    for opp in changed_opportunities:
        local_opp = db[opp['LOCAL_ID']]

        # Fetch responsible user info.
        if opp['RESPONSIBLE_USER_ID']:
            userdata = insightly_get(
                '/users/{}'.format(opp['RESPONSIBLE_USER_ID']), auth)
            opp['RESPONSIBLE_USER'] = ('{FIRST_NAME} {LAST_NAME} '
                                       '{EMAIL_ADDRESS}'.format(**userdata))
        else:
            opp['RESPONSIBLE_USER'] = None

        # Make list of changed fields.
        changed_fields = [x for x in opp if opp.get(x) != local_opp.get(x)]

        changes = []
        if 'PROBABILITY' in changed_fields:
            changes.append(
                'Probability changed from {} to {}\n'
                .format(local_opp['PROBABILITY'], opp['PROBABILITY']))
        if 'BID_AMOUNT' in changed_fields:
            changes.append('Bid amount changed from {} to {}\n'
                           .format(local_opp['BID_AMOUNT'], opp['BID_AMOUNT']))
        if 'BID_CURRENCY' in changed_fields:
            changes.append(
                'Bid currency changed from {} to {}\n'
                .format(local_opp['BID_CURRENCY'], opp['BID_CURRENCY']))
        if 'OPPORTUNITY_STATE' in changed_fields:
            changes.append('State changed from {} to {}\n'
                           .fromat(local_opp['OPPORTUNITY_STATE'],
                                   opp['OPPORTUNITY_STATE']))
        if 'PIPELINE_ID' in changed_fields:
            if local_opp['PIPELINE_ID']:
                old_pipeline = insightly_get(
                    '/Pipelines/{}'.format(local_opp['PIPELINE_ID']), auth)
            else:
                old_pipeline = {'PIPELINE_NAME': 'No pipeline'}
            if local_opp['STAGE_ID']:
                old_stage = insightly_get(
                    '/PipelineStages/{}'.format(local_opp['STAGE_ID']), auth)
            else:
                old_stage = {'STAGE_NAME': 'No stage'}
            if opp['PIPELINE_ID']:
                pipeline = insightly_get(
                    '/Pipelines/{}'.format(opp['PIPELINE_ID']), auth)
                if opp['STAGE_ID']:
                    stage = insightly_get(
                        '/PipelineStages/{}'.format(opp['STAGE_ID']), auth)
                else:
                    stage = {'STAGE_NAME': 'No stage'}
                changes.append(
                    'Pipeline changed from {} ({}) to {} ({})\n'
                    .format(old_pipeline['PIPELINE_NAME'],
                            old_stage['STAGE_NAME'], pipeline['PIPELINE_NAME'],
                            stage['STAGE_NAME']))
            else:
                changes.append('Pipeline changed from {} ({}) to None\n'
                               .format(old_pipeline['PIPELINE_NAME'],
                                       old_stage['STAGE_NAME']))
        elif 'STAGE_ID' in changed_fields:
            if local_opp['STAGE_ID']:
                old_stage = insightly_get(
                    '/PipelineStages/{}'.format(local_opp['STAGE_ID']), auth)
            else:
                old_stage = {'STAGE_NAME': 'No stage'}
            if opp['STAGE_ID']:
                stage = insightly_get('/PipelineStages/' + opp['STAGE_ID'],
                                      auth)
                changes.append('Stage changed from {} to {}\n'
                               .format(old_stage['STAGE_NAME'],
                                       stage['STAGE_NAME']))
            else:
                changes.append('Stage changed from {} to None\n'
                               .format(old_stage['STAGE_NAME']))
        elif 'CATEGORY_ID' in changed_fields:
            if local_opp['CATEGORY_ID']:
                old_category = insightly_get(
                    '/PipelineStages/{}'.format(local_opp['CATEGORY_ID']),
                    auth)
            else:
                old_category = {'STAGE_NAME': 'No stage'}
            if opp['CATEGORY_ID']:
                category = insightly_get(
                    '/OpportunityCategories/{}'.format(opp['CATEGORY_ID']),
                    auth)
                changes.append('Category changed from {} to {}\n'
                               .format(old_category['CATEGORY_NAME'],
                                       category['CATEGORY_NAME']))
            else:
                changes.append('Category changed from {} to None\n'
                               .format(old_category['CATEGORY_NAME']))
        elif 'RESPONSIBLE_USER_ID' in changed_fields:
            changes.append('Responsible user changed\n')

        notes = opportunities_with_new_notes.get(opp['OPPORTUNITY_ID'])
        if notes is not None:
            for note in notes:
                body = re.sub('<.*?>', '', note['BODY']).strip()
                changes.append('New note added: {}\nText: {}\n'
                               .format(note['TITLE'], body))

        # Send message to slack.
        if changes:
            message = CHANGED_MESSAGE.format(changes='\n'.join(changes), **opp)
            slack_post(config.SLACK_CHANNEL_URL,
                       json={'text': dedent(message).strip()})

        # Update local opportunity.
        db[opp['LOCAL_ID']] = opp


def notify_deleted_opportunities():
    """
    Fetch all opportunities using insightly api. Compare with local copy.
    Send slack message on each deleted opportunity.

    NOTE: Details of the deleted opportunity can only be known from local db.
    These details should be periodically updated
    using notify_changed_opportunities() function. So periodically running
    script should always run both functions, as done in the main().
    """
    db = shelve.open('db.shelve')

    auth = (config.INSIGHTLY_API_KEY, '')

    if 'opportunities_ids' not in db:
        db['opportunities_ids'] = set()

    server_opportunities = insightly_get('/opportunities', auth)

    # Store locally opportunity details which was not known previously.
    for opp in server_opportunities:
        opp['LOCAL_ID'] = 'opportunity_%s' % opp['OPPORTUNITY_ID']

        if opp['LOCAL_ID'] not in db:
            db[opp['LOCAL_ID']] = opp

    # Determine deleted ids.
    server_opportunities_ids = set(x['OPPORTUNITY_ID'] for x in
                                   server_opportunities)
    deleted_opportunities_ids = (db['opportunities_ids']
                                 .difference(server_opportunities_ids))

    logging.info('%d deleted opportunities found.'
                 % len(deleted_opportunities_ids))

    for opp_id in deleted_opportunities_ids:
        local_id = 'opportunity_%s' % opp_id

        message = DELETED_MESSAGE.format(**db[local_id])

        # Send message to slack.
        slack_post(config.SLACK_CHANNEL_URL, json={'text': dedent(message)})

    # Update local list of existing opportunities ids.
    db['opportunities_ids'] = server_opportunities_ids

    # Delete not needed details of deleted opportunities.
    for opp_id in deleted_opportunities_ids:
        local_id = 'opportunity_%s' % opp_id
        del db[local_id]


def main():
    configure()
    notify_new_opportunities()
    notify_changed_opportunities()
    notify_deleted_opportunities()


if __name__ == '__main__':
    main()
