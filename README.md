# django-analytics-dispatcher

## Installation:
Install app with:
```
$ pip install -e git+ssh://git@github.com/InitechSoftware/django-analytics-dispatcher.git#egg=django-analytics-dispatcher
```
Add to setting.py into INSTALLED_APPS:

```
'analytics_dispatcher',
```

Run migrate command:
```
$ python manage.py migrate
```

Add credentials for used platforms: 

```
# Intercom
INTERCOM_ACCESS_TOKEN = env('INTERCOM_ACCESS_TOKEN', default=None, cast=str)
# user.com
USER_DOT_COM_API_KEY = env('USER_DOT_COM_API_KEY', default=None, cast=str)
USER_DOT_COM_APIJS_KEY = env('USER_DOT_COM_APIJS_KEY', default=None, cast=str)
USER_DOT_COM_APP = env('USER_DOT_COM_APP', default=None, cast=str)
# Amplitude
AMPLITUDE_API_KEY = env('AMPLITUDE_API_KEY', default='', cast=str)
```

Add Event types to settings

```
from analytics_dispatcher.data_structures import EventType

EVENT_TYPES = [
    # comment
    EventType(name='APP_LOADED'),
...
]
```

Add async (if needed) runner into settings.py. 
If runner setting is missed events are sent in realtime. 

```
DAD_RUN_TASK = 'project.main.analytics_helper.run_task'
```

Sample of runner:
```
def run_task(task):
    logger.info('run_task %r', task)
    main_models.WorkerTask.single_add(task)
```

Add API entry point into urls file:
```
from django.views.decorators.csrf import csrf_exempt
from analytics_dispatcher import views as analytics_views

urlpatterns = [
...
    path('analytics/track', csrf_exempt(analytics_views.track)),
...
]
```
