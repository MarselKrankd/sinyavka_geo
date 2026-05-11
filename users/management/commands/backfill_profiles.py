"""Create a PlayerProfile for every User that's missing one.

Re-runnable. Use after setting up the project on an environment that has
legacy User rows pre-dating the post_save profile signal.

    python manage.py backfill_profiles
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from users.models import PlayerProfile
from users.signals import _unique_nickname


class Command(BaseCommand):
    help = 'Create PlayerProfile for every User missing one'

    def handle(self, *args, **options):
        User = get_user_model()
        missing = User.objects.filter(profile__isnull=True)
        count = 0
        for u in missing:
            base = u.get_username() or (u.email.split('@')[0] if u.email else 'player')
            nickname = _unique_nickname(base)
            PlayerProfile.objects.create(user=u, nickname=nickname)
            self.stdout.write(self.style.SUCCESS(f'created profile for {u.username} -> {nickname}'))
            count += 1
        if count == 0:
            self.stdout.write(self.style.SUCCESS('all users already have a profile'))
        else:
            self.stdout.write(self.style.SUCCESS(f'done — {count} profile(s) created'))
