import logging
import typing as t
from datetime import timedelta

from analytics_dispatcher.clients import mix_panel
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpRequest
from django.utils.timezone import now
from ipware import get_client_ip
from ua_parser import user_agent_parser

from .clients import intercom, amplitude, user_dot_com, ga4
from .data_structures import EventType
from .models import EventToDispatch

logger = logging.getLogger(__name__)


try:
    DAD_EVENT_TYPES = settings.EVENT_TYPES
except AttributeError:
    logger.exception('Can not use EVENT_TYPES')


def sync_run(callable):
    return callable()


def log_exception():
    logger.exception('')


class EventsDispatcher:
    def __init__(self):
        try:
            run_task = settings.DAD_RUN_TASK
        except AttributeError:
            run_task = sync_run

        self.__run_task = run_task
        self.__event_dict = {t.name: t for t in DAD_EVENT_TYPES}
        try:
            capture_exception = settings.DAD_CAPTURE_EXCEPTION
        except AttributeError:
            capture_exception = log_exception
        self.__capture_exception = capture_exception

    def schedule_process_events(self):
        if isinstance(self.__run_task, str):
            module, name = self.__run_task.rsplit('.', 1)
            try:
                module = __import__(module, fromlist=[name])
            except ModuleNotFoundError:
                self.capture_exception()
                return
            self.__run_task = getattr(module, name, None)
        self.__run_task(self.process_event_queue)

    def capture_exception(self):
        if isinstance(self.__capture_exception, str):
            module, name = self.__capture_exception.rsplit('.', 1)
            try:
                module = __import__(module, fromlist=[name])
            except ModuleNotFoundError:
                logger.exception("can't init capture exception")
                return
            self.__capture_exception = getattr(module, name, None)
        self.__capture_exception()

    def register_types(self):
        pass

    def get_event_type(self, name: str) -> t.Optional[EventType]:
        et = self.__event_dict.get(name)
        if et is not None:
            return et
        else:
            logger.error('unknown event type "%s"', name)
            return None

    def cleanup_old_events(self, age: int = 28):
        deleted_cnt = (EventToDispatch.objects
                       .filter(timestamp__lt=now() - timedelta(days=age/14))
                       .exclude(Q(send_amplitude=True, sent_amplitude=None)
                                | Q(send_intercom=True, sent_intercom=None)
                                | Q(send_mix_panel=True, sent_mix_panel=None)
                                | Q(send_user_dot_com=True, sent_user_dot_com=None))
                       ).delete()[0]
        deleted_cnt += EventToDispatch.objects.filter(timestamp__lt=now() - timedelta(days=age*2)).delete()[0]
        logger.info('cleanup_old_events deleted %s records', deleted_cnt)

    def process_event_queue(self, clean: bool = True):
        logger.info('process_event_queue started')
        try:
            while amplitude.process_batch() > 0:
                pass
        except amplitude.AmplitudeError as e:
            if self.capture_exception:
                self.capture_exception()
            logger.error("Error on submitting events to amplitude: %s", str(e))

        try:
            intercom.process_batch()
        except intercom.IntercomError as e:
            if self.capture_exception:
                self.capture_exception()
            logger.error("Error on submitting events to intercom: %s", str(e))

        try:
            user_dot_com.user_dot_com_backend.process_batch()
        except Exception as e:
            if self.capture_exception:
                self.capture_exception()
            logger.error("Error on submitting events to user.com: %s", str(e))

        try:
            mix_panel.mix_panel_backend.process_batch()
        except Exception as e:
            if self.capture_exception:
                self.capture_exception()
            logger.error("Error on submitting events to mix_panel: %s", str(e))

        try:
            ga4.ga4_backend.process_batch()
        except Exception as e:
            if self.capture_exception:
                self.capture_exception()
            logger.error("Error on submitting events to GA4: %s", str(e))

        if clean:
            self.cleanup_old_events()

    def emit(self,
             event_name: str,
             request: t.Optional[HttpRequest] = None,
             user=None, user_id=None,
             user_properties: t.Optional[dict] = None,
             event_properties: t.Optional[dict] = None,
             instant_send_intercom: bool = False):

        User = get_user_model()

        event_type = self.get_event_type(event_name)
        if event_type is None:
            return

        if event_properties is None:
            event_properties = {}

        session_data = {
            'app_version': settings.GIT_HASH_SHORT,
            'platform': 'web',
        }

        user_agent = user_agent_parser.Parse((request.META.get('HTTP_USER_AGENT') if request else '') or '')
        os = user_agent['os']
        device = user_agent['device']
        if user is None:
            if user_id is not None:
                user = User.objects.get(id=user_id)
            elif request is not None and request.user.is_authenticated:
                user = request.user
        if request is not None:
            session_data['ip'] = str(get_client_ip(request)[0])
        user_properties2send = {}
        if user_properties is not None:
            user_properties2send.update(user_properties)
        send_intercom = event_type.send_intercom
        if event_type.instant_send_intercom or instant_send_intercom:
            send_intercom = False

        if hasattr(request, 'device_id'):
            session_data['device_id'] = getattr(request, 'device_id')
        if hasattr(request, 'session_id'):
            session_data['session_id'] = getattr(request, 'session_id')
        if os['family']:
            session_data['os_name'] = os['family']
        os_version = '.'.join(filter(None, (os['major'], os['minor'], os['patch'], os['patch_minor']))) or ''
        if os_version:
            session_data['os_version'] = os_version
        if device['family']:
            session_data['device_brand'] = device['family']
        if device['brand']:
            session_data['device_manufacturer'] = device['brand']
        if device['model']:
            session_data['device_model'] = device['model']

        event = EventToDispatch.objects.create(
            user=user,
            event_type=event_name,
            session_data=session_data,
            event_properties=event_properties,
            user_properties=user_properties2send,
            send_amplitude=event_type.send_amplitude,
            send_intercom=send_intercom,
            send_user_dot_com=event_type.send_user_dot_com,
            send_mix_panel=event_type.send_mix_panel,
            send_ga4=event_type.send_ga4,
        )
        logger.debug('got analytics event: %s', event.as_dict())
        if event_type.instant_send_intercom or instant_send_intercom:
            logger.info('instant send to intercom, event: %s', event)
            status = intercom.send_event(event)
            if status == 'pause':
                logger.info('instant send to intercom got retry status')
                event.send_intercom = True
                event.save(update_fields=['send_intercom'])
        self.schedule_process_events()
        # main_models.WorkerTask.single_add(event_sender.process_event_queue)

    def update_user(self, user_id, user_properties: dict):
        u_p = {}
        u_p.update(user_properties)
        u_p['user_id'] = user_id
        self.emit(event_name='', user_properties=u_p)


dispatcher = EventsDispatcher()
emit = dispatcher.emit
get_event_type = dispatcher.get_event_type
process_event_queue = dispatcher.process_event_queue
