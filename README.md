# GoogleCalendarEventsJiraReporter
This script can log some events from google calendar to a dedicated JIRA task

1. Visit page https://developers.google.com/calendar/quickstart/python 
and push button 'ENABLE THE GOOGLE CALENDAR API'.
After that popup with button 'DOWNLOAD GOOGLE CONFIGURATION' will be showed.
Just download it and put value which stored by key 'installed' into 'config.file'.

2. You should create new virtual enviroment (optional)

3. pip install -r requirements.txt

4. Put some details into config.json (jira details, scan_last_days etc)

5. python main.py
