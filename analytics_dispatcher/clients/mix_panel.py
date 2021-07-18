import logging

from django.conf import settings
from django.utils.timezone import now
try:
    from mixpanel import Mixpanel
    mixpanel_installed = True
except:
    mixpanel_installed = False

from analytics_dispatcher import models
from analytics_dispatcher.clients._base import AnalyticsBackend


logger = logging.getLogger(__name__)


class MixPanelBackend(AnalyticsBackend):
    SERVICE_NAME = 'mix_panel'
    SECRET_SETTINGS_NAME = 'MIXPANEL_TOKEN'

    def __init__(self):
        self.mp = None
        if not hasattr(settings, 'MIXPANEL_TOKEN') or not settings.MIXPANEL_TOKEN:
            return
        self.mp = Mixpanel(settings.MIXPANEL_TOKEN)

    def _ll_send_event(self, user_id, event, data):
        logger.info('Mixpanel track event for user %s, event %s, data: %r', user_id, event, data)
        if self.mp is not None:
            self.mp.track(user_id, event, data)
        else:
            logger.info('Mixpanel not configured, skip tracking of event')

    def _ll_save_user(self, user_id, data):
        logger.info('Mixpanel add user %s, data: %r', user_id, data)
        if not settings.MIXPANEL_TOKEN:
            return
        properties = {
            '$first_name': data.get('first_name'),
            '$last_name': data.get('last_name'),
            '$email': data.get('email'),
            '$phone': data.get('phone')
        }
        self.mp.people_set(
            user_id,
            properties,
            meta={
                '$ignore_time': 'true',
                'ip': data.get('ip')
            }
        )

    def push_event(self, event: models.EventToDispatch):
        user_properties = event.user_properties
        user_id = user_properties.pop('user_id', None)
        if event.event_type == '':
            if user_id is not None:
                self._ll_save_user(user_id, user_properties)
        else:
            if event.user_id is not None:
                user_id = event.user_id
        self._ll_send_event(user_id, event.event_type, event.event_properties)

        event.sent_mix_panel = now()
        event.status_mix_panel = 'ok'
        event.save(update_fields=('sent_mix_panel', 'status_mix_panel'))


mix_panel_backend = MixPanelBackend()
