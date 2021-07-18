import logging

from django.conf import settings

logger = logging.getLogger(__name__)

try:
    capture_exception = settings.SENTRY_CAPTURE_EXCEPTION
    if isinstance(capture_exception, str):
        module, name = capture_exception.rsplit('.', 1)
        try:
            module = __import__(module, fromlist=[name])
        except ModuleNotFoundError:
            logger.error('Can not find %s', capture_exception)

        capture_exception = getattr(module, name, None)
except AttributeError:
    def capture_exception():
        logger.error('Dummy exception capture')
