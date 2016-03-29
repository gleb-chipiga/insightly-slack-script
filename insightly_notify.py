#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from __future__ import print_function

import json
import logging
import logging.config
import re
import shelve

from datetime import datetime
from os.path import exists
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

    if hasattr(config, 'SYSLOG_ADDRESS'):
        SYSLOG_ADDRESS = config.SYSLOG_ADDRESS
        print('Syslog is configured to use %s' % SYSLOG_ADDRESS)
    else:
        SYSLOG_ADDRESS = '/run/systemd/journal/syslog'
        print('Syslog is configured to use %s by default. You can change SYSLOG_ADDRESS in the config.' % SYSLOG_ADDRESS)

    logging.config.dictConfig({
        'version': 1,
        'handlers': {
            'syslog': {
                'level': 'INFO',
                'class': 'logging.handlers.SysLogHandler',
                'address': SYSLOG_ADDRESS
            },
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
            },
        },
        'loggers': {
            '': {'handlers': ['syslog', 'console'], 'level': 'INFO'},
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

    # Auth user should be the api key, password is empty.
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
