"""Configure Site + SocialApps from environment variables.

Run after every settings change:
    python manage.py setup_site

It points django.contrib.sites at the configured host and ensures one
SocialApp row per provider when client_id is present, so allauth picks them
up from the DB.
"""

from __future__ import annotations

import os
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Sync Site + SocialApps from .env'

    def handle(self, *args, **options):
        from allauth.socialaccount.models import SocialApp

        host = os.getenv('SITE_DOMAIN', 'localhost:8000')
        site, _ = Site.objects.update_or_create(
            id=settings.SITE_ID,
            defaults={'domain': host, 'name': 'sinyavka_geo'},
        )
        self.stdout.write(self.style.SUCCESS(f'Site -> {site.domain}'))

        providers = {
            'yandex': (os.getenv('YANDEX_CLIENT_ID', ''), os.getenv('YANDEX_CLIENT_SECRET', '')),
            'vk': (os.getenv('VK_CLIENT_ID', ''), os.getenv('VK_CLIENT_SECRET', '')),
        }
        for provider, (client_id, secret) in providers.items():
            if not client_id:
                self.stdout.write(self.style.WARNING(f'{provider}: client_id empty — skipped'))
                continue
            app, _ = SocialApp.objects.update_or_create(
                provider=provider,
                defaults={'name': provider.capitalize(), 'client_id': client_id, 'secret': secret, 'key': ''},
            )
            app.sites.add(site)
            self.stdout.write(self.style.SUCCESS(f'{provider}: ok ({client_id[:8]}...)'))
