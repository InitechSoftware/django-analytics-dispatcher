import logging
import pprint
import time
import typing as t

import requests
from django.conf import settings
from django.db import transaction
from django.utils.timezone import now
from requests import Response

from ..utils import capture_exception
from .. import models

logger = logging.getLogger(__name__)


class IntercomError(Exception):
    def __init__(self, response: str, status: int) -> None:
        self.response = response
        self.status = status

    def __str__(self) -> str:
        return f'Intercom error "{self.response}" with status "{self.status}"'


class IntercomQualifiedError(IntercomError):
    def __init__(self, response: dict, status: int) -> None:
        self.response = response
        self.status = status

    def __str__(self) -> str:
        return pprint.pformat(self.response, indent=4)


USER_ATTRIBUTES = {'user_id', 'email', 'phone', 'pseudonym', 'name',
                   'referrer', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'}


class IntercomClient:
    BASE_URL = 'https://api.intercom.io/'
    ACCESS_TOKEN = settings.INTERCOM_ACCESS_TOKEN

    def __init__(self):
        self.session = requests.Session()

    def _request(self, method: str, path: str, json_data: dict) -> t.Optional[Response]:
        url = self.BASE_URL + path
        logger.info("intercom request %s %s %r", method, url, json_data)

        headers = {
            'Authorization': 'Bearer ' + (self.ACCESS_TOKEN or '<no token defined>'),
            'Accept': 'application/json',
        }

        if self.ACCESS_TOKEN is not None:
            resp = self.session.request(method, url, headers=headers, json=json_data)
            if (400 <= resp.status_code < 500 or resp.status_code == 503) and resp.status_code != 404:
                if resp.headers.get('Content-Type') == 'application/json':
                    raise IntercomQualifiedError(resp.json(), resp.status_code)
                else:
                    raise IntercomError(resp.text, resp.status_code)
            elif resp.status_code != 404:
                resp.raise_for_status()
            logger.info("intercom API response %s %s %s %s", method, url, resp.status_code, resp.content)
            return resp
        else:
            logger.info('intercom API call %s, %s, %r', method, url, json_data)

    def create_or_update_user(self, user, user_properties):
        user_data = {
            'user_id': user.id,
            'email': user.email,
            'signed_up_at': user.timestamp_joined,
            'name': user.username,
        }
        if user_properties:
            custom_attributes = {}
            for arg_name in user_properties.keys():
                if arg_name in USER_ATTRIBUTES:
                    user_data[arg_name] = user_properties[arg_name]
                else:
                    custom_attributes[arg_name] = user_properties[arg_name]
            if len(custom_attributes) > 0:
                user_data['custom_attributes'] = custom_attributes
        if self.ACCESS_TOKEN is not None:
            resp = self._request('post', 'users', json_data=user_data)
            if resp is None or resp.status_code != 200:
                logger.error('error on create or update user')
            return resp
        else:
            self._request('post', 'users', json_data=user_data)

    def event(self, name, user, event_properties, user_properties):
        logger.info('intercom event %s for user[%s] event_properties: %r, user_properties: %r',
                    name, str(user), event_properties, user_properties)
        data = {
            'event_name': name,
            'created_at': int(time.time()),
            'user_id': user.id,
        }
        if event_properties:
            data.update({
                'metadata': event_properties,
            })

        if settings.DEBUG:
            return

        if self.ACCESS_TOKEN is not None:
            if len(user_properties) > 0:
                self.create_or_update_user(user, user_properties)

            resp = self._request('post', 'events', json_data=data)
            if resp is not None and resp.status_code == 404:
                resp_data = resp.json()
                if resp_data.get('type') == 'error.list':
                    resp_data_errors = resp_data.get('errors', [])
                    if len(resp_data_errors) > 0 and resp_data_errors[0].get('message') == 'User Not Found':
                        self.create_or_update_user(user, {})
                        resp = self._request('post', 'events', json_data=data)
                        if resp is None or resp.status_code != 202:
                            logger.error('double error in sending event')
                    else:
                        logger.error('error sending event, wrong response structure, %r', resp.text)
                else:
                    logger.error('error sending event, wrong response structure')
            elif resp is None or resp.status_code != 202:
                logger.error('error sending event')
        else:
            self._request('post', 'events', json_data=data)


api = IntercomClient()


def send_event(event: models.EventToDispatch, client: IntercomClient = None):
    from analytics_dispatcher.event import dispatcher

    if client is None:
        client = IntercomClient()

    if event.user_id is None:
        event_type = dispatcher.get_event_type(event.event_type)
        if event_type is not None and not event_type.dont_log_without_user:
            logger.warning('intercom: attempt to emit event "%s" without user.', event.event_type)
        event.sent_intercom = now()
        event.status_intercom = 'error: user missed'
        event.save(update_fields=('sent_intercom', 'status_intercom'))
        return 'next'

    event_properties = event.dict_for_intercom_event()
    user_properties = event.dict_for_intercom_user()

    try:
        client.event(event.event_type, event.user, event_properties, user_properties)
    except IntercomQualifiedError as e:
        response = e.response
        if response.get('type') == 'error.list':
            error0 = response.get('errors', [{}])[0]
            if error0.get('code') == 'service unavailable':
                logger.warning('Service unavailable, interrupt emitting process. Message from server: %r',
                               error0.get('message'))
                return 'pause'
        event.sent_intercom = now()
        event.status_intercom = f'Error during emitting event. Code: {e.status}, response: {response}'
        event.save(update_fields=('sent_intercom', 'status_intercom'))
        capture_exception()
        return 'next'
    except IntercomError as e:
        if e.status in (429, 503):
            logger.warning("Too many requests for a user / device, status: %s. Stop submitting", e.status)
            return 'pause'
        event.sent_intercom = now()
        event.status_intercom = f'Error during emitting event. Exception: {e}'
        event.save(update_fields=('sent_intercom', 'status_intercom'))
        capture_exception()
        return 'next'
    event.sent_intercom = now()
    event.status_intercom = 'ok'
    event.save(update_fields=('sent_intercom', 'status_intercom'))
    return 'next'


def process_batch(number: int = 500) -> int:
    client = IntercomClient()

    events_count = 0
    while events_count < number:
        with transaction.atomic():
            event = (models.EventToDispatch.objects.select_for_update(skip_locked=True)
                     .filter(send_intercom=True, sent_intercom=None).order_by('timestamp')).first()
            if event is None:
                break
            status = send_event(event, client=client)
            if status == 'next':
                continue
            elif status == 'pause':
                break
            events_count += 1
    if events_count > 0:
        logger.info('sent %d events to intercom', events_count)
    return events_count
