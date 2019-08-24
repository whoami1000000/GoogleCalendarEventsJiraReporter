from __future__ import print_function

import datetime
import json
import os.path
import pickle

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from jira import JIRA

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


def get_dt_jira_format(dt: datetime.datetime):
    dt_str = dt.isoformat(timespec='milliseconds')
    components = dt_str.split('+')
    dt_str = components[0] + '+0000'
    return dt_str


def get_calendar_credentials(config: dict):
    credentials = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            credentials = pickle.load(token)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(config, SCOPES)
            credentials = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(credentials, token)
    return credentials


def get_calendar_events(credentials, count_days: int, ignored_events: list) -> list:
    service = build('calendar', 'v3', credentials=credentials)

    dt = datetime.datetime.utcnow() - datetime.timedelta(days=count_days)
    scan_from = datetime.datetime(dt.year, dt.month, dt.day, tzinfo=dt.tzinfo)

    scan_to = datetime.datetime.utcnow()

    events_result = service.events().list(calendarId='primary',
                                          timeMin=scan_from.isoformat() + 'Z',
                                          timeMax=scan_to.isoformat() + 'Z',
                                          maxResults=10000,
                                          singleEvents=True,
                                          orderBy='startTime').execute()

    def event_filter_func(event: dict) -> bool:
        if event.get('status', '') != 'confirmed':
            return False

        if event.get('summary') in ignored_events:
            return False

        def attendee_filter_func(attendee: dict) -> bool:
            return attendee.get('self', False) and attendee.get('responseStatus', '') == 'accepted'

        return next(filter(attendee_filter_func, event.get('attendees', [])), None) is not None

    events = list(filter(event_filter_func, events_result.get('items', [])))

    print('{} events extracted from google calendar'.format(len(events)))

    return events


def get_jira_object(url: str, username: str, password: str) -> JIRA:
    jira = JIRA(server=url, basic_auth=(username, password))
    return jira


def get_config(filename: str) -> dict:
    with open(filename) as json_file:
        return json.load(json_file)


def log_work(jira: JIRA, events: list, task_id: str) -> None:
    dt_format = '%Y-%m-%dT%H:%M:%S%z'

    event_count = 0
    total_count = len(events)

    work_logs = jira.worklogs(task_id)

    for event in events:
        try:
            original_start_dt_str = event['originalStartTime']['dateTime'] if 'originalStartTime' in event \
                else event['start']['dateTime']
            original_start_dt = datetime.datetime.strptime(original_start_dt_str, dt_format)

            start_dt = datetime.datetime.strptime(event['start']['dateTime'], dt_format)
            end_dt = datetime.datetime.strptime(event['end']['dateTime'], dt_format)

            started = get_dt_jira_format(original_start_dt)
            comment = event['summary']
            duration = end_dt - start_dt

            for work_log in work_logs:
                if work_log.started == started and work_log.comment == comment \
                        and work_log.timeSpentSeconds == duration.total_seconds():
                    print(f'Event {comment} which started {started} will skip because item already exists')
                    break
            else:
                jira.add_worklog(issue=task_id,
                                 timeSpentSeconds=duration.total_seconds(),
                                 started=original_start_dt,
                                 comment=comment)
                print(f'Event {comment} which started {started} was sent successfully')
                event_count = event_count + 1
        except Exception as ex:
            print(f'Can not process event : {event}. Error = {ex}')

    print(f'{event_count} events from {total_count} were sent to jira')


def main():
    config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.json')
    print(f'Config path = {config_path}')

    config = get_config(config_path)

    credentials = get_calendar_credentials(config['calendar'])

    jira_config = config['jira']
    jira = get_jira_object(jira_config['url'], jira_config['username'], jira_config['password'])

    count_days = config['scan_last_days']

    ignored_events = config['ignored_events']

    events = get_calendar_events(credentials, count_days, ignored_events)

    if events:
        print('Available events:')
        for event in events:
            print({'summary': event['summary'], 'start': event['start']})
        print('\n')

        print('logging has started...')
        log_work(jira, events, jira_config['task'])
        print('logging has finished')
    else:
        print('No available events')


if __name__ == '__main__':
    main()
