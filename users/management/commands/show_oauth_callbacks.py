"""Print the exact Callback URLs that need to be registered on
https://oauth.yandex.ru for the configured client to accept logins.

Run after every settings change and on a fresh checkout:

    python manage.py show_oauth_callbacks
"""

from __future__ import annotations

import os

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Print the redirect_uri values to register on oauth.yandex.ru'

    def handle(self, *args, **options):
        client_id = os.getenv('YANDEX_CLIENT_ID', '')
        host = os.getenv('SITE_DOMAIN', 'localhost:8000')

        host = host.replace('http://', '').replace('https://', '').rstrip('/')
        path = '/accounts/yandex/login/callback/'

        self.stdout.write(self.style.NOTICE('Yandex OAuth: redirect_uri mismatch fix'))
        self.stdout.write('')
        self.stdout.write(f'  Yandex client_id: {client_id or "<not set in .env>"}')
        self.stdout.write(f'  SITE_DOMAIN env:  {os.getenv("SITE_DOMAIN") or "<not set; using default localhost:8000>"}')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            'Go to https://oauth.yandex.ru/client/{}/edit'.format(client_id or '<your-client-id>')
        ))
        self.stdout.write('and register BOTH of these as Callback URLs (Redirect URI):')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'  http://localhost:8000{path}'))
        self.stdout.write(self.style.SUCCESS(f'  http://127.0.0.1:8000{path}'))
        self.stdout.write('')
        self.stdout.write('You need BOTH because Django builds redirect_uri from')
        self.stdout.write('whichever host you typed in the browser bar — opening')
        self.stdout.write('the app at localhost sends one, at 127.0.0.1 sends the')
        self.stdout.write('other, and Yandex rejects anything not in its list.')
        self.stdout.write('')
        self.stdout.write('If you deploy under a different domain, add that too')
        self.stdout.write('(with https://) and set SITE_DOMAIN in .env accordingly.')
