import datetime
import logging

from django.conf import settings
from django.utils import timezone
from ga4mp import Ga4mp
import requests

from ._base import AnalyticsBackend
from .. import models

logger = logging.getLogger(__name__)


class Ga4Client(AnalyticsBackend):
    SERVICE_NAME = 'ga4'
    SECRET_SETTINGS_NAME = 'GA4_API_SECRET'

    BASE_URL = 'https://www.google-analytics.com/mp/collect'
    API_SECRET = settings.GA4_API_SECRET
    # FIREBASE_APP_ID = settings.GA4_FIREBASE_APP_ID
    MEASUREMENT_ID = settings.GA4_MEASUREMENT_ID
    CLIENT_ID = settings.GA4_CLIENT_ID

    def __init__(self):
        super().__init__()
        self.session = requests.session()

    def __request(self, events_data, *, timestamp: datetime.datetime, headers=None):
        if settings.GA4_API_SECRET is None:
            logger.warning('GA4 is not enabled (GA4_API_SECRET is None).')
            return None
        local_headers = {}
        if headers is not None:
            local_headers.update(headers)
        local_headers.update({'Content-type': 'application/json'})

        auth_params = {
            'api_secret': self.API_SECRET,
            'measurement_id': self.MEASUREMENT_ID,
        }

        events_data2send = {
            'client_id': self.CLIENT_ID,
            # 'user_id': '',  # todo !
            'timestamp_micros': int(timestamp.timestamp() * 1000),
            'events': events_data,
        }

        response = self.session.post(self.BASE_URL, params=auth_params, headers=local_headers, json=events_data2send)
        if response.status_code >= 300:
            logger.warning('GA4 request "%s" bad response with status: %s, body: "%s"',
                           events_data2send, response.status_code, response.text)
        else:
            logger.info('GA4 request "%s" response with status: %s, body: "%s"',
                        events_data2send, response.status_code, response.text)
        return response

    def push_event(self, event: models.EventToDispatch) -> str:
        validate_res = self.validate_event(event)
        if validate_res is not None:
            return validate_res

        # ga = Ga4mp(measurement_id=self.MEASUREMENT_ID, api_secret=self.API_SECRET, client_id=self.CLIENT_ID)

        if event.event_type == 'login':
            events = [
                # {'name': event.event_type, 'params': event.event_properties}
                {'name': event.event_type, 'params': {'method': ''}}
            ]
        else:
            events = [
                # {'name': event.event_type, 'params': event.event_properties}
                {'name': event.event_type, 'params': {}}
            ]
        # ga.set_user_property('user_id', event.user_id)
        # for user_prop_key, user_prop_value in event.user_properties.items():
        #     ga.set_user_property(user_prop_key, user_prop_value)

        # ga.send(events)
        self.__request(events, timestamp=event.timestamp)

        event.sent_ga4 = timezone.now()
        event.status_ga4 = 'ok'
        event.save(update_fields=('sent_ga4', 'status_ga4'))
        return 'next'

    # def push_event(self, event) -> str:
    #
    #     self.send_event(event.event_type, event.user, event.timestamp.timestamp(),
    #                    event.event_properties, user_data=event.user_properties)


ga4_backend = Ga4Client()
