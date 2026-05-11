from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse

from .locations import MAP_CHOICES, MAPS


class Room(models.Model):
    class Status(models.TextChoices):
        LOBBY = 'lobby', 'Лобби'
        IN_GAME = 'in_game', 'Игра идёт'
        FINISHED = 'finished', 'Завершена'

    name = models.CharField(max_length=80)
    code = models.CharField(max_length=12, unique=True, db_index=True)
    map_key = models.CharField(max_length=32, choices=MAP_CHOICES)
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hosted_rooms',
    )
    is_private = models.BooleanField(default=False)
    max_players = models.PositiveSmallIntegerField(default=6)
    rounds_total = models.PositiveSmallIntegerField(default=5)
    round_duration_sec = models.PositiveSmallIntegerField(default=90)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.LOBBY)
    current_round = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.code})'

    @staticmethod
    def generate_code() -> str:
        return secrets.token_urlsafe(6).replace('_', 'a').replace('-', 'b')[:8].upper()

    @property
    def map_def(self):
        return MAPS[self.map_key]

    @property
    def is_full(self) -> bool:
        return self.memberships.count() >= self.max_players

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.LOBBY and not self.is_full

    def get_absolute_url(self):
        return reverse('rooms:room_detail', args=[self.code])


class Membership(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memberships',
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    score = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('room', 'user')
        ordering = ['joined_at']

    def __str__(self):
        return f'{self.user} in {self.room.code}'


class Round(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='rounds')
    number = models.PositiveSmallIntegerField()
    lat = models.FloatField()
    lng = models.FloatField()
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('room', 'number')
        ordering = ['number']

    def __str__(self):
        return f'{self.room.code} R{self.number}'


class Guess(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='guesses')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lat = models.FloatField()
    lng = models.FloatField()
    distance_m = models.FloatField(default=0)
    points = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('round', 'user')
        ordering = ['submitted_at']

    def __str__(self):
        return f'{self.user} -> R{self.round.number}: {self.points}'
