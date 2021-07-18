import collections

EventType = collections.namedtuple('EventType',
                                   ['name',
                                    'send_intercom','send_user_dot_com','send_amplitude','send_mix_panel',
                                   'instant_send_intercom','dont_log_without_user'],
                                   defaults=(None, False, False, False, False, False, False)
                                   )
