import time
import uuid


class SessionIdMiddleware:
    session_cookie_name = 'session_id'
    session_timeout = 30 * 60  # 30 minutes
    device_cookie_name = 'device_id'
    device_timeout = 2 * 365 * 24 * 60 * 60  # 2 years

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.session_id = int(request.COOKIES.get(self.session_cookie_name, time.time()))
        request.device_id = request.COOKIES.get(self.device_cookie_name, str(uuid.uuid4()))
        response = self.get_response(request)
        response.set_cookie(self.session_cookie_name, request.session_id, max_age=self.session_timeout)
        response.set_cookie(self.device_cookie_name, request.device_id, max_age=self.device_timeout)
        return response
