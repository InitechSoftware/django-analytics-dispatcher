
import hashlib
import logging

from django.conf import settings
from django.db import models

AMPLITUDE_SESSION_VALUES = ('device_id', 'session_id', 'ip',
                            'app_version', 'platform',
                            'os_name', 'os_version',
                            'device_brand', 'device_manufacturer', 'device_model',
                            )

logger = logging.getLogger(__name__)


class EventToDispatch(models.Model):
    event_type = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    session_data = models.JSONField(default=dict)
    user_properties = models.JSONField(default=dict)
    event_properties = models.JSONField(default=dict)

    send_amplitude = models.BooleanField()
    sent_amplitude = models.DateTimeField(default=None, blank=True, null=True, db_index=True)
    status_amplitude = models.CharField(max_length=256, null=True)

    send_intercom = models.BooleanField()
    sent_intercom = models.DateTimeField(default=None, blank=True, null=True, db_index=True)
    status_intercom = models.CharField(max_length=256, null=True)

    send_user_dot_com = models.BooleanField()
    sent_user_dot_com = models.DateTimeField(default=None, blank=True, null=True, db_index=True)
    status_user_dot_com = models.CharField(max_length=256, null=True)

    send_mix_panel = models.BooleanField()
    sent_mix_panel = models.DateTimeField(default=None, blank=True, null=True, db_index=True)
    status_mix_panel = models.CharField(max_length=256, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.event_type} @ {self.timestamp} by {self.user} id:{self.pk}'

    @property
    def insert_id(self):
        """
        "A unique identifier for the event. We will deduplicate subsequent events sent with an insert_id we have already
        seen before within the past 7 days. We recommend generation a UUID or using some combination of device_id,
        user_id, event_type, event_id, and time."
        """
        return hashlib.sha224('{}.{}.{}'.format(
            self.id, self.event_type, self.session_data.get('device_id')).encode()).hexdigest()

    def dict_for_amplutude(self, users_cache):
        """
        https://developers.amplitude.com/#schemaevent
        """

        event_properties = {}
        user_properties = {}

        user_email = None

        if self.user_id is not None:
            if self.user_id not in users_cache:
                users_cache[self.user_id] = {
                    'user_id': self.user.id,
                    'email': self.user.email,
                    'first_name': self.user.first_name,
                    'last_name': self.user.last_name
                }
            user_properties = users_cache[self.user_id]
            user_email = user_properties['email']
            event_properties['user_id'] = user_properties['user_id']

        user_properties.update(self.user_properties)
        event_properties.update(self.event_properties)

        event_data = {
            # 'user_id': getattr(self.user, 'email', None),
            'user_id': user_email,
            'event_id': self.id,
            'event_type': self.event_type,
            'insert_id': self.insert_id,
            'time': int(self.timestamp.timestamp()),
            'event_properties': event_properties,
            'user_properties': user_properties,
        }

        for value_name in AMPLITUDE_SESSION_VALUES:
            if value_name in self.session_data:
                event_data[value_name] = self.session_data[value_name]

        return event_data

    def dict_for_intercom_event(self):
        return self.event_properties

    def dict_for_intercom_user(self):
        res = {}
        for k, v in self.user_properties.items():
            if type(v) == list:
                res[k] = ', '.join(v)
            else:
                res[k] = v
        return res

    def as_dict(self):
        """
        https://developers.amplitude.com/#schemaevent
        """

        event_data = {
            'user_id': getattr(self.user, 'email', None),
            'event_id': self.id,
            'event_type': self.event_type,
            'insert_id': self.insert_id,
            'time': int(self.timestamp.timestamp()),
            'event_properties': self.event_properties,
            'user_properties': self.user_properties,
            'session_data': self.session_data,
        }
        return event_data
