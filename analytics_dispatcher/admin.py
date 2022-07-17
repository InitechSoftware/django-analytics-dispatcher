from django.contrib import admin
from django_admin_listfilter_dropdown.filters import DropdownFilter

from .models import EventToDispatch


@admin.register(EventToDispatch)
class EventAdmin(admin.ModelAdmin):
    list_display = ('f_timestamp', 'user', 'event_type',
                    'event_properties', 'user_properties',
                    'fsent_amplitude', 'fsent_intercom', 'fsent_user_dot_com', 'fsent_ga4', 'has_errors')
    list_filter = (
        ('event_type', DropdownFilter),
    )
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'event_type']
    list_select_related = ['user']
    readonly_fields = ['user', 'timestamp', 'event_type']
    fieldsets = (
        (None, {
            'fields': ('user', 'event_type', 'timestamp', 'send_amplitude', 'send_intercom', 'send_ga4')
        }),
        ('Event info', {
            'fields': ('session_data', 'user_properties', 'event_properties')
        }),
        ('Emit info', {
            'fields': ('sent_amplitude', 'status_amplitude',
                       'sent_intercom', 'status_intercom',
                       'sent_user_dot_com', 'status_user_dot_com',
                       'sent_ga4', 'status_ga4',
                       )
        }),
    )

    def has_errors(self, obj):
        status_intercom = obj.status_intercom
        status_amplitude = obj.status_amplitude
        if ((status_intercom is not None and status_intercom != 'ok')
                or (status_amplitude is not None and status_amplitude != 'ok')):
            return 'has errors'
        return '-'

    has_errors.short_description = 'Has errors'

    def f_timestamp(self, obj):
        return obj.timestamp.strftime('%Y-%m-%d %H:%M')

    f_timestamp.short_description = 'Timestamp'

    def fsent_amplitude(self, obj):
        if obj.sent_amplitude is not None:
            return obj.sent_amplitude.strftime('%Y-%m-%d %H:%M')
        return ''

    fsent_amplitude.short_description = 'Sent amplitude'

    def fsent_intercom(self, obj):
        if obj.sent_intercom is not None:
            return obj.sent_intercom.strftime('%Y-%m-%d %H:%M')
        return ''

    fsent_intercom.short_description = 'Sent intercom'

    def fsent_user_dot_com(self, obj):
        if obj.sent_user_dot_com is not None:
            return obj.sent_user_dot_com.strftime('%Y-%m-%d %H:%M')
        return ''

    fsent_user_dot_com.short_description = 'Sent user.com'

    def fsent_ga4(self, obj):
        if obj.sent_ga4 is not None:
            return obj.sent_ga4.strftime('%Y-%m-%d %H:%M')
        return ''

    fsent_ga4.short_description = 'Sent Google Analytics 4'
