import datetime
import logging

from django.conf import settings
from django.utils import timezone
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

    def __request(self, event_data, *, user_properties, user_id, timestamp: datetime.datetime):
        if settings.GA4_API_SECRET is None:
            logger.warning('GA4 is not enabled (GA4_API_SECRET is None).')
            return None
        local_headers = {'Content-type': 'application/json'}

        auth_params = {
            'api_secret': self.API_SECRET,
            'measurement_id': self.MEASUREMENT_ID,
        }

        events_data2send = {
            'client_id': str(user_id),
            'non_personalized_ads': False,
            'user_id': str(user_id),
            'timestamp_micros': int(timestamp.timestamp() * 1000),
            'user_properties': user_properties,
            'events': [event_data],
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

        user_data = event.user_properties
        ga4_event = {'name': event.event_type, 'params': event.event_properties()}

        user_properties = {key[:24]: {"value": str(data)} for key, data in user_data.items()}

        self.__request(ga4_event, user_id=event.user.id, user_properties=user_properties, timestamp=event.timestamp)

        event.sent_ga4 = timezone.now()
        event.status_ga4 = 'ok'
        event.save(update_fields=('sent_ga4', 'status_ga4'))
        return 'next'


ga4_backend = Ga4Client()
