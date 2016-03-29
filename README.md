# insightly-slack-script
Script, launched periodically, will fetch new and changed opportunities from insightly and send message to slack

## Quickstart
1. Launch the script first time, it will copy `config.py.example` to `config.py`:

        > ./insightly_notify.py
    
2. Edit `config.py`.
    
    Set *INSIGHTLY_API_KEY*, which can be seen on your insightly user page. 

    Go to the https://my.slack.com/services/new/incoming-webhook/ to configure incoming webhooks. Select a channel or user you want to post messages to. Copy resulting webhook url to *SLACK_CHANNEL_URL* in `config.py`
    
3. Launch the script second time. It will store current time in local file and fetch new opportunities from insightly, which was created after current time. The list will be empty, so nothing will happen.

4. Create new opportunity in insightly.

5. Launch the script third time, it will get the last launch time from local file, and fetch new opportunities from insightly, which was created after that time. It should send slack message about the opportunity you have created on step 4.

6. You can put the script to crontab to be launched periodically. But beware of daily api calls limit, so don't schedule it too often.

## Configuration
All config variables should be put in the `config.py` file. That file will be created automatically after the first launch.

*INSIGHTLY_API_KEY* - string, required. The api key can be obtained on your insightly user page. 

*SLACK_CHANNEL_URL* - string, required. The url can be obtained at slack incoming webhooks configuration page: https://my.slack.com/services/new/incoming-webhook/

*SYSLOG_ADDRESS* - string or tuple, optional. This setting will be used to send log messages to syslog daemon. Depending on the local syslog daemon configuration, it should be set to the address it is listening to. It can be string, representing local unix-socket file path, or tuple (hostname, port)
