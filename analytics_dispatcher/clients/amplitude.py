import logging
import pprint
import typing as t

import requests
from django.conf import settings
from django.db.transaction import atomic
from django.utils.timezone import now

from ..models import EventToDispatch

logger = logging.getLogger(__name__)


class AmplitudeError(Exception):
    pass


class AmplitudeQualifiedError(AmplitudeError):
    def __init__(self, request: dict, response: dict, status: int) -> None:
        self.request = request
        self.response = response
        self.status = status

    def __str__(self) -> str:
        return pprint.pformat(self.response, indent=4)


class Amplitude:
    API_URL = 'https://api.amplitude.com/2/httpapi'
    HEADERS = {
        'Content-Type': 'application/json',
        'Accept': '*/*'
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _request(self, **data) -> dict:
        data.update({
            'api_key': self.api_key,
        })
        r = requests.post(self.API_URL, headers=self.HEADERS, json=data)
        if 400 <= r.status_code < 500:
            if r.headers.get('Content-Type') == 'application/json':
                raise AmplitudeQualifiedError(data, r.json(), r.status_code)
            else:
                raise AmplitudeError(r.text)
        r.raise_for_status()
        return r.json()

    def events(self, events: t.List[dict]) -> dict:
        logger.info('Sending %d Amplitude events', len(events))
        return self._request(events=events)


def _filter_events(events, map_name, response) -> t.List:
    errors_map = response[map_name]
    to_drop = set()
    for k, v in errors_map.items():
        to_drop.update(v)
    resulting_events = []
    rejected_events = []
    for i in range(len(events)):
        if i in to_drop:
            logger.warning('amplitude rejected event "%s" with error %s', events[i], map_name)
            rejected_events.append(events[i])
        else:
            resulting_events.append(events[i])

    EventToDispatch.objects.filter(pk__in=[event.pk for event in rejected_events]).update(
        sent_amplitude=now(),
        status_amplitude=map_name + str(errors_map),
    )

    logger.warning('Filtered out %d events', len(events) - len(resulting_events))

    return resulting_events


@atomic
def process_batch(number: int = 100) -> int:
    client = Amplitude(api_key=settings.AMPLITUDE_API_KEY)

    events = list(EventToDispatch.objects
                  .select_for_update(skip_locked=True)
                  .filter(send_amplitude=True, sent_amplitude=None)
                  .order_by('timestamp')[:number]
                  )
    sent = False
    loop_count = 5
    events_count = 0
    users_cache = {}
    while not sent and loop_count > 0:
        loop_count -= 1
        events_count = len(events)
        if events_count == 0:
            return 0
        try:
            client.events([event.dict_for_amplutude(users_cache) for event in events])
            sent = True
        except AmplitudeQualifiedError as e:
            response = e.response
            code = response.get('code')
            if code == 429:
                logger.warning("Too many requests for a user / device. Stop submitting")
                return 0
            elif code == 400:
                logger.warning("Invalid upload request. '%s'. Response: %r", response.get('error'), response)
                if 'events_missing_required_fields' in response:
                    events = _filter_events(events, 'events_missing_required_fields', response)
                elif 'events_with_missing_fields' in response:
                    events = _filter_events(events, 'events_with_missing_fields', response)
                elif 'events_with_invalid_fields' in response:
                    events = _filter_events(events, 'events_with_invalid_fields', response)
                elif 'events_with_invalid_ids' in response:
                    events = _filter_events(events, 'events_with_invalid_ids', response)
                else:
                    logger.error("Invalid upload request. '%s'. Response: %r", response.get('error'), response)
                    return 0
            else:
                raise

    EventToDispatch.objects.filter(pk__in=[event.pk for event in events]).update(sent_amplitude=now(),
                                                                                 status_amplitude='ok')
    logger.info('sent %d events to amplitude', events_count)
    return events_count
