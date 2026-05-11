"""Drop rooms that no one can ever finish.

Two passes:
 1. Rooms with zero memberships that are at least `--empty-grace-minutes`
    old. The grace window stops us racing freshly-created rooms whose
    host hasn't loaded the page yet.
 2. Non-finished rooms older than `--stale-cutoff-hours`, regardless of
    membership count — long-running tabs that someone forgot about.

Usage:
    python manage.py cleanup_stale_rooms
    python manage.py cleanup_stale_rooms --empty-grace-minutes 0
    python manage.py cleanup_stale_rooms --dry-run
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from rooms.models import Room

class Command(BaseCommand):
    help = 'Delete empty / stale lobby and in-game rooms'

    def add_arguments(self, parser):
        parser.add_argument('--empty-grace-minutes', type=int, default=2)
        parser.add_argument('--stale-cutoff-hours', type=int, default=2)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        now = timezone.now()
        empty_cutoff = now - timedelta(minutes=options['empty_grace_minutes'])
        stale_cutoff = now - timedelta(hours=options['stale_cutoff_hours'])
        dry = options['dry_run']

        empty_qs = (
            Room.objects
            .exclude(status=Room.Status.FINISHED)
            .annotate(member_count=Count('memberships'))
            .filter(member_count=0, created_at__lt=empty_cutoff)
        )
        empty_list = list(empty_qs.values_list('code', 'name', 'status'))

        stale_qs = (
            Room.objects
            .exclude(status=Room.Status.FINISHED)
            .filter(created_at__lt=stale_cutoff)
        )
        stale_list = list(stale_qs.values_list('code', 'name', 'status'))

        self.stdout.write(self.style.WARNING(
            f'empty rooms (<{options["empty_grace_minutes"]}m grace): {len(empty_list)}'
        ))
        for code, name, status in empty_list:
            self.stdout.write(f'  {code} "{name}" [{status}]')
        self.stdout.write(self.style.WARNING(
            f'stale rooms (>{options["stale_cutoff_hours"]}h old, not finished): {len(stale_list)}'
        ))
        for code, name, status in stale_list:
            self.stdout.write(f'  {code} "{name}" [{status}]')

        if dry:
            self.stdout.write(self.style.NOTICE('--dry-run: nothing deleted'))
            return

        total = empty_qs.count() + stale_qs.count()
        empty_qs.delete()
        stale_qs.delete()
        self.stdout.write(self.style.SUCCESS(f'deleted {total} room(s)'))
