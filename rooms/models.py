from __future__ import annotations

import random
import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse

class Map(models.Model):
    key = models.CharField(max_length=32, unique=True)
    label = models.CharField(max_length=80)
    center_lat = models.FloatField()
    center_lng = models.FloatField()
    zoom = models.PositiveSmallIntegerField(default=11)
    max_zoom = models.PositiveSmallIntegerField(default=15)
    south = models.FloatField()
    west = models.FloatField()
    north = models.FloatField()
    east = models.FloatField()
    max_distance_m = models.FloatField()

    class Meta:
        ordering = ['label']

    def __str__(self):
        return self.label

    @property
    def center(self):
        return (self.center_lat, self.center_lng)

    @property
    def bounds(self):
        return (self.south, self.west, self.north, self.east)

    @property
    def points(self):
        return [(p.lat, p.lng) for p in self.points_set.all()]

    def random_point_excluding(self, used=None):
        used_keys = {(round(u[0], 4), round(u[1], 4)) for u in (used or [])}
        pool = [p for p in self.points if (round(p[0], 4), round(p[1], 4)) not in used_keys]
        if pool:
            return random.choice(pool)
        lat = self.south + random.random() * (self.north - self.south)
        lng = self.west + random.random() * (self.east - self.west)
        return (lat, lng)

class MapPoint(models.Model):
    map = models.ForeignKey(Map, on_delete=models.CASCADE, related_name='points_set')
    lat = models.FloatField()
    lng = models.FloatField()
    label = models.CharField(max_length=120, blank=True, default='')

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.map.key}: {self.lat:.4f}, {self.lng:.4f}'

class Room(models.Model):
    class Status(models.TextChoices):
        LOBBY = 'lobby', 'Лобби'
        IN_GAME = 'in_game', 'Игра идёт'
        FINISHED = 'finished', 'Завершена'

    name = models.CharField(max_length=80)
    code = models.CharField(max_length=12, unique=True, db_index=True)
    map = models.ForeignKey(Map, on_delete=models.PROTECT, related_name='rooms')
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
    def map_key(self):
        return self.map.key

    @property
    def map_def(self):
        return self.map

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
