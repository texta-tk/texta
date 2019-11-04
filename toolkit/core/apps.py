from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'toolkit.core'

    def ready(self):
        '''When app is loaded, load signals'''
        import toolkit.core.user_profile.signals
