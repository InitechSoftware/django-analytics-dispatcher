from argparse import ArgumentParser

from django.core.management import BaseCommand

from analytics_dispatcher.event import process_event_queue


class Command(BaseCommand):
    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument('--clean', default=False, action='store_true')

    def handle(self, *args, **options):
        process_event_queue(clean=options['clean'])
        pass
