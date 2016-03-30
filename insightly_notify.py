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
from os.path import abspath, dirname, exists, join
from shutil import copyfile
from textwrap import dedent

import requests

if not exists('config.py'):
    print(u'*** Creating default config file config.py')
    copyfile('config.py.example', 'config.py')

import config


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


def main():
    """
    Fetch new opportunities using insightly api. Send slack message on each new opportunity.
    """
    configure()

    # Persistent file storage will keep track of last poll time.
    db = shelve.open('db.shelve')

    # Tuple (user, password) for request authentication. User should be the api key, password is empty.
    insightly_auth = (config.INSIGHTLY_API_KEY, '')

    now = datetime.utcnow()

    if 'last_poll' not in db:
        db['last_poll'] = now
        logging.info('*** insightly_notify is launched first time, previous events are ignored.')

    last_poll = db['last_poll'].strftime('%Y-%m-%dT%H:%M:%S')

    url = "https://api.insight.ly/v2.1/opportunities?$filter=DATE_CREATED_UTC%20gt%20DateTime'{from_date}'"
    opp_response = requests.get(url.format(from_date=last_poll), auth=insightly_auth)

    if opp_response.status_code != 200:
        err = Exception('Insightly api GET error: Http status %s. Url:\n%s' % (opp_response.status_code, opp_response.url))
        logging.critical(err)
        raise err

    db['last_poll'] = now

    new_opportunities = json.loads(opp_response.content)

    logging.info('%d new opportunities found.' % len(new_opportunities))

    for opp in new_opportunities:

        # Fetch responsible user info.
        uid = opp['RESPONSIBLE_USER_ID']
        u_response = requests.get("https://api.insight.ly/v2.1/users/%s" % uid, auth=insightly_auth)
        if u_response.status_code != 200:
            err = Exception('Insightly api GET error: Http status %s. Url:\n%s' % (u_response.status_code, u_response.url))
            logging.critical(err)
            raise err

        userdata = json.loads(u_response.content)
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
        slack_response = requests.post(config.SLACK_CHANNEL_URL, json={'text': dedent(message)})
        if slack_response.status_code != 200:
            err = Exception('Slack api POST error: Http status %s. Url:\n%s' % (slack_response.status_code, slack_response.url))
            logging.critical(err)
            raise err


if __name__ == '__main__':
    main()
