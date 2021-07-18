import json
import logging

from django import http

from . import event

logger = logging.getLogger(__name__)


def track(request: http.HttpRequest) -> http.HttpResponse:
    if request.method != 'POST':
        return http.HttpResponseNotAllowed(['POST'])
    try:
        data = json.loads(request.body.decode())
    except json.JSONDecodeError:
        return http.HttpResponseBadRequest('Bad data', content_type='text/plain')
    try:
        event_type = data['event_type']
    except KeyError:
        return http.HttpResponseBadRequest('No event_type', content_type='text/plain')
    logger.info('got analytics event from client-side, data: %r', data)

    properties = data.get('event_properties')

    event.emit(event_type, request,
               event_properties=properties or {},
               user_properties=data.get('user_properties') or {}
               )
    return http.HttpResponse('OK', content_type='text/plain')


