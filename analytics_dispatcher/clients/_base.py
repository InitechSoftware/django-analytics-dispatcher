import logging

from django.conf import settings
from django.db import transaction
from django.utils.timezone import now

from analytics_dispatcher import models

logger = logging.getLogger(__name__)


class AnalyticsBackend:
    SERVICE_NAME = None
    SECRET_SETTINGS_NAME = None

    def is_enabled(self):
        return hasattr(settings, self.SECRET_SETTINGS_NAME)

    def push_event(self, event) -> str:
        raise NotImplemented

    def validate_event(self, event):
        from analytics_dispatcher.event import dispatcher

        if event.user_id is None:
            event_type = dispatcher.get_event_type(event.event_type)
            if event_type is not None and not event_type.dont_log_without_user:
                logger.warning('%s: attempt to emit event "%s" without user.', self.SERVICE_NAME, event.event_type)
            setattr(event, 'sent_'+self.SERVICE_NAME, now())
            event.status_user_dot_com = 'error: user missed'
            event.save(update_fields=('sent_'+self.SERVICE_NAME, 'status_'+self.SERVICE_NAME))
            return 'next'
        return None

    def process_batch(self, number: int = 500) -> int:
        events_count = 0
        filter_params = {
            'send_' + self.SERVICE_NAME: True,
            'sent_' + self.SERVICE_NAME: None,
        }
        while events_count < number:
            with transaction.atomic():
                event = (models.EventToDispatch.objects.select_for_update(skip_locked=True)
                         .filter(**filter_params).order_by('timestamp')).first()
                if event is None:
                    break
                status = self.push_event(event)
                if status == 'next':
                    continue
                elif status == 'pause':
                    break
                events_count += 1
        if events_count > 0:
            logger.info('sent %d events to %s', events_count, self.SERVICE_NAME)
        return events_count
