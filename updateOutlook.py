# encoding: utf-8


from workflow import Workflow3, ICON_INFO
from settings import get_login, get_password, get_regex, get_server, get_value_from_settings_with_default_boolean
import sys, os
from workflow.background import run_in_background, is_running
from sets import Set
import subprocess

def asrun(ascript):
    "Run the given AppleScript and return the standard output and error."
    osa = subprocess.Popen(['osascript', '-'],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE)
    return osa.communicate(ascript)[0]

def asquote(astr):
    "Return the AppleScript equivalent of the given string."
    astr = astr.replace('"', '" & quote & "')
    return '"{}"'.format(astr)



def query_exchange_server(wf, start_search, end_search, date_offset):
    """Runs a query against an exchange server for either today or a date offset by `date_offset`"""
    from lib.pyexchange import Exchange2010Service, ExchangeBasicAuthConnection, ExchangeNTLMAuthConnection

    log = wf.logger

    log.info("BG: Refreshing Data Cache [Outlook]")
    log.info(wf.cachedir)

    # Get data from disk
    exchange_url, using_default_server = get_server(wf)
    exchange_username = get_login(wf, False)
    exchange_password = get_password(wf, False)
    using_ntlm = get_value_from_settings_with_default_boolean(wf, 'use_ntlm', False)

    if not using_ntlm:
        log.info("BG: Outlook connection - External Server - Basic Auth")
        # Set up the connection to Exchange
        connection = ExchangeBasicAuthConnection(url=exchange_url,
                                                 username=exchange_username,
                                                 password=exchange_password)
    else:
        connection = ExchangeNTLMAuthConnection(url=exchange_url,
                                                username=exchange_username,
                                                password=exchange_password)
        log.info("BG: Outlook connection - Internal NTML")

    service = Exchange2010Service(connection)

    try:
        # You can set event properties when you instantiate the event...
        event_list = service.calendar().list_events(start=start_search, end=end_search, details=True)

        log.info("BG: Event count: " + str(event_list.count))
        return event_list.events
    except:
        return None

EVENT_FIELD_NAMES = ['_id', 'end', 'start', 'html_body', 'subject']

def serialize_event(event):
    """ returns a string that serializes selected fields from an event"""
    return ''.join(['%s' % getattr(event, ff) for ff in EVENT_FIELD_NAMES])


def build_event_set(events):
    """returns a set"""
    # this bad boy uses set comprehensions (note the parens)
    return (serialize_event(evt) for evt in events)

def main(wf):
    import pytz
    from pytz import timezone
    from datetime import timedelta, datetime
    from settings import get_value_from_settings_with_default_boolean, get_value_from_settings_with_default_int
    import time

    # Get arguments to call
    args = wf.args
    wf.logger.debug(args)
    start_param = args[0]  # "2016-08-26-04:00:01"
    end_param = args[1]  # "2016-08-27-03:59:59"
    date_offset = args[2]

    format = "%Y-%m-%d-%H:%M:%S"
    start_outlook = datetime.strptime(start_param, format)#.astimezone(pytz.utc)
    end_outlook = datetime.strptime(end_param, format)#.astimezone(pytz.utc)


    def wrapper():
        return query_exchange_server(wf, start_outlook, end_outlook, date_offset)


    cache_key = "exchange.Today" if (date_offset == "1") else "exchange.Tomorrow"
    notify_key = cache_key.replace('exchange.','')

    # Compare Old events to New events to see if something changed
    old_events = wf.cached_data(cache_key)

    # Force rewrite the cache
    wf.cache_data(cache_key, query_exchange_server(wf, start_outlook, end_outlook, date_offset))

    # Compare the new "pulled" data against what was in the cache
    new_events = wf.cached_data(cache_key)

    if new_events is not None:
        new_set = build_event_set(new_events)
        old_set = build_event_set(old_events)

        cmd = 'tell application "Alfred 3" to run trigger "NotifyOfUpdate" in workflow "org.jeef.today" with argument "' + notify_key + '"'

        if len(new_set.symmetric_difference(old_set)) > 0:
            wf.logger.debug('Refreshing view')
            asrun(cmd)

        log.debug(cache_key)
        log.debug(date_offset)


if __name__ == '__main__':
    wf = Workflow3(libraries=['./lib'])
    log = wf.logger
    wf.run(main)
