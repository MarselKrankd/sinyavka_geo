"""Auto-create a PlayerProfile for every new user and enrich from social account."""

from django.conf import settings
from django.db import IntegrityError
from django.db.models.signals import post_save
from django.dispatch import receiver

from allauth.socialaccount.signals import social_account_added, social_account_updated

from .models import PlayerProfile


def _unique_nickname(base: str) -> str:
    base = (base or 'player').strip().replace(' ', '_')[:40] or 'player'
    candidate = base
    suffix = 1
    while PlayerProfile.objects.filter(nickname=candidate).exists():
        suffix += 1
        candidate = f'{base}{suffix}'
    return candidate


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if not created:
        return
    base = instance.get_username() or instance.email.split('@')[0] if instance.email else 'player'
    try:
        PlayerProfile.objects.create(user=instance, nickname=_unique_nickname(base))
    except IntegrityError:
        pass


def _avatar_from_social(sociallogin) -> str:
    data = sociallogin.account.extra_data or {}
    provider = sociallogin.account.provider
    if provider == 'google':
        return data.get('picture', '') or ''
    if provider == 'yandex':
        avatar_id = data.get('default_avatar_id')
        if avatar_id:
            return f'https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200'
        return ''
    if provider == 'vk':
        return data.get('photo_200') or data.get('photo_100') or ''
    return ''


@receiver(social_account_added)
@receiver(social_account_updated)
def sync_social_profile(sender, request, sociallogin, **kwargs):
    user = sociallogin.user
    profile = getattr(user, 'profile', None)
    if profile is None:
        return
    avatar = _avatar_from_social(sociallogin)
    if avatar and avatar != profile.avatar_url:
        profile.avatar_url = avatar
        profile.save(update_fields=['avatar_url'])
