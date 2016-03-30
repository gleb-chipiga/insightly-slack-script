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
from copy import copy
from os.path import abspath, dirname, exists, join
from shutil import copyfile
from textwrap import dedent

import requests

if not exists('config.py'):
    print(u'*** Creating default config file config.py')
    copyfile('config.py.example', 'config.py')

import config


def insightly_get(url, auth):
    """ Send GET response. Raise exception if response status code is not 200. """
    response = requests.get('https://api.insight.ly/v2.1' + url, auth=auth)
    if response.status_code != 200:
        err = Exception('Insightly api GET error: Http status %s. Url:\n%s' % (response.status_code, url))
        logging.critical(err)
        raise err
    return json.loads(response.content)


def slack_post(url, *args, **kwargs):
    """ Send POST response. Raise exception if response status code is not 200. """
    response = requests.post(url, *args, **kwargs)
    if response.status_code != 200:
        err = Exception('Slack api POST error: Http status %s. Url:\n%s' % (response.status_code, url))
        logging.critical(err)
        raise err
    return response


def configure():
    """
    Apply configuration from config.py
    """

    if hasattr(config, 'LOG_FILE'):
        LOG_FILE = abspath(config.LOG_FILE)
        print('Log messages will be sent to %s' % LOG_FILE)
    else:
        LOG_FILE = '/var/log/insightly_notify.log'
        print('Log messages will be sent to %s. You can change LOG_FILE in the config.' % LOG_FILE)

    # Test write permissions in the log file directory.
    permissons_test_path = join(dirname(LOG_FILE), 'insightly_test.log')
    try:
        with open(permissons_test_path, 'w+') as test_file:
            test_file.write('test')
        os.remove(permissons_test_path)
    except (OSError, IOError) as e:
        msg = '''\
            Write to the "%s/" directory failed. Please check permissions or change LOG_FILE config.
            Original error was: %s.''' % (dirname(LOG_FILE), e)
        raise Exception(dedent(msg))

    LOG_LEVEL = getattr(config, 'LOG_LEVEL', 'INFO')

    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'verbose': {
                'format': '%(levelname)s %(asctime)s %(module)s.py: %(message)s',
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
        from config import INSIGHTLY_API_KEY
        from config import SLACK_CHANNEL_URL
    except Exception as e:
        logging.critical('Please set required config varialble in config.py:\n%s', str(e))
        raise

    if not re.match(r'\w{8}-\w{4}-\w{4}-\w{4}-\w{12}', INSIGHTLY_API_KEY):
        err = Exception('INSIGHTLY_API_KEY has wrong format "%s", please set the right value in config.py' % INSIGHTLY_API_KEY)
        logging.critical(err)
        raise err

    if not re.match(r'https://hooks.slack.com/services/\w+/\w+/\w+', SLACK_CHANNEL_URL):
        err = Exception('SLACK_CHANNEL_URL has wrong format "%s", please set the right value in config.py' % SLACK_CHANNEL_URL)
        logging.critical(err)
        raise err


def notify_new_opportunities():
    """
    Fetch new opportunities using insightly api. Send slack message on each new opportunity.
    """
    # Persistent file storage will keep track of last poll time.
    db = shelve.open('db.shelve')

    # Tuple (user, password) for request authentication. User should be the api key, password is empty.
    insightly_auth = (config.INSIGHTLY_API_KEY, '')

    now = datetime.utcnow()

    if 'last_poll' not in db:
        db['last_poll'] = now
        logging.info('*** insightly_notify is launched first time, previously created opportunities are ignored.')

    last_poll = db['last_poll'].strftime('%Y-%m-%dT%H:%M:%S')

    url = "/opportunities?$filter=DATE_CREATED_UTC%20gt%20DateTime'{from_date}'".format(from_date=last_poll)
    new_opportunities = insightly_get(url, insightly_auth)

    db['last_poll'] = now

    logging.info('%d new opportunities found.' % len(new_opportunities))

    for opp in new_opportunities:

        # Fetch responsible user info.
        uid = opp['RESPONSIBLE_USER_ID']
        userdata = insightly_get("/users/%s" % uid, insightly_auth)

        opp['RESPONSIBLE_USER'] = "{FIRST_NAME} {LAST_NAME} {EMAIL_ADDRESS}".format(**userdata)

        # The message template to send to slack.
        message = '''\
            New opportunity created: {OPPORTUNITY_NAME}
            Value: {BID_AMOUNT} {BID_CURRENCY}
            Responsible user: {RESPONSIBLE_USER}
            Close date: {FORECAST_CLOSE_DATE}
            Description: {OPPORTUNITY_DETAILS}'''\
            .format(**opp)

        # Send message to slack.
        slack_post(config.SLACK_CHANNEL_URL, json={'text': dedent(message)})


def notify_changed_opportunities():
    """
    Fetch changed opportunities using insightly api. Send slack message on each changed opportunity.
    """
    db = shelve.open('db.shelve')

    insightly_auth = (config.INSIGHTLY_API_KEY, '')

    now = datetime.utcnow()

    if 'changed_opportunities_last_poll_time' not in db:
        db['changed_opportunities_last_poll_time'] = now
        logging.info('*** insightly_notify is launched first time, previously changed opportunities are ignored.')

    last_poll = db['changed_opportunities_last_poll_time'].strftime('%Y-%m-%dT%H:%M:%S')

    url = "/opportunities?$filter=DATE_UPDATED_UTC%20gt%20DateTime'{from_date}'".format(from_date=last_poll)
    changed_opportunities = insightly_get(url, insightly_auth)

    db['changed_opportunities_last_poll_time'] = now

    # Clear list from new opportunities, we only handle changed ones here.
    for opp in copy(changed_opportunities):
        # Assign LOCAL_ID to opportunity.
        opp['LOCAL_ID'] = 'opportunity_%s' % opp['OPPORTUNITY_ID']

        if opp['LOCAL_ID'] not in db:
            # This is new opportunitiy, add to the local database and remove from changed list.
            db[opp['LOCAL_ID']] = opp
            changed_opportunities.remove(opp)

    logging.info('%d changed opportunities found.' % len(changed_opportunities))

    for opp in changed_opportunities:
        local_opp = db[opp['LOCAL_ID']]

        # Make list of changed fields.
        changed_fields = [x for x in opp if opp.get(x) != local_opp.get(x)]

        message = ''
        if 'PROBABILITY' in changed_fields:
            message += 'Probability changed to %s\n' % opp['PROBABILITY']
        if 'BID_AMOUNT' in changed_fields:
            message += 'Bid amount changed to %s\n' % opp['BID_AMOUNT']
        if 'BID_CURRENCY' in changed_fields:
            message += 'Bid currency changed to %s\n' % opp['BID_CURRENCY']
        if 'OPPORTUNITY_STATE' in changed_fields:
            message += 'State changed to %s\n' % opp['OPPORTUNITY_STATE']
        if 'PIPELINE_ID' in changed_fields:
            pipeline = insightly_get("/Pipelines/%s" % opp['PIPELINE_ID'], insightly_auth)
            stage = insightly_get("/PipelineStages/%s" % opp['STAGE_ID'], insightly_auth)
            message += 'Pipeline changed to %s (%s)\n' % (pipeline['PIPELINE_NAME'], stage['STAGE_NAME'])
        elif 'STAGE_ID' in changed_fields:
            stage = insightly_get("/PipelineStages/%s" % opp['STAGE_ID'], insightly_auth)
            message += 'Stage changed to %s\n' % stage['STAGE_NAME']

        # Send message to slack.
        if message:
            slack_post(config.SLACK_CHANNEL_URL, json={'text': message.strip()})

        # Update local opportunity.
        db[opp['LOCAL_ID']] = opp


def main():
    configure()
    notify_new_opportunities()
    notify_changed_opportunities()


if __name__ == '__main__':
    main()
