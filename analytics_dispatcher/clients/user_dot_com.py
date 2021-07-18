import logging

import requests
from django.conf import settings
from django.utils.timezone import now

from ._base import AnalyticsBackend

logger = logging.getLogger(__name__)


class UserDotComBackend(AnalyticsBackend):
    SERVICE_NAME = 'user_dot_com'
    SECRET_SETTINGS_NAME = 'USER_DOT_COM_API_KEY'

    def __init__(self):
        super().__init__()
        self.session = requests.session()

    def __request(self, method, path, data, headers=None):
        if settings.USER_DOT_COM_API_KEY is None:
            logger.warning('user.com is not enabled (USER_DOT_COM_API_KEY is None).')
            return None
        local_headers = {}
        if headers is not None:
            local_headers.update(headers)
        local_headers.update({
            'Authorization': 'Token ' + settings.USER_DOT_COM_API_KEY,
            'Content-type': 'application/json'
        })
        url = f'https://{settings.USER_DOT_COM_APP}.user.com/api/public' + path
        if method == 'get':
            response = self.session.request(method, url, headers=local_headers)
        else:
            response = self.session.request(method, url, headers=local_headers, json=data)
        if response.status_code >= 300:
            logger.warning('user.com request "%s %s %s" bad response with status: %s, body: %s',
                           method, path, data,
                           response.status_code, response.text)
        else:
            logger.info('user.com request "%s %s %s" response with status: %s, body: %s',
                           method, path, data,
                           response.status_code, response.text)
        return response

    def create_user(self, user):
        user_data = {
            'user_id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }
        return self.__request('post', '/users/', user_data)

    def set_user_custom_attributes(self, user_id, custom_attributes):
        # To set custom attributes for certain user, the attribute need to exist before proceeding.
        # https://user.com/en/api/users/set-multiple-attributes-by-id/
        if len(custom_attributes) > 0:
            return self.__request('post', f'/users-by-id/{user_id}/set_multiple_attributes/', custom_attributes)
        else:
            return None

    def send_event(self, name, user, timestamp, event_data, user_data):
        request_data = {
            'name': name,
            'timestamp': timestamp,
            'data': event_data,
        }
        request_url = f'/users-by-id/{user.id}/events/'
        event_response = self.__request('post', request_url, request_data)
        if event_response is None:
            return None
        if event_response.status_code == 404:
            self.create_user(user)
            event_response = self.__request('post', request_url, request_data)
        self.set_user_custom_attributes(user.id, user_data)
        return event_response

    def push_event(self, event) -> str:
        validate_res = self.validate_event(event)
        if validate_res is not None:
            return validate_res

        self.send_event(event.event_type, event.user, event.timestamp.timestamp(),
                       event.event_properties, user_data=event.user_properties)
        event.sent_user_dot_com = now()
        event.status_user_dot_com = 'ok'
        event.save(update_fields=('sent_user_dot_com', 'status_user_dot_com'))
        return 'next'


user_dot_com_backend = UserDotComBackend()
