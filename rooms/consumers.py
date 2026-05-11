"""WebSocket consumer that drives realtime room state.

Protocol (server -> client `type`):
  - state: full snapshot of the room (players, round, status)
  - chat:  chat message
  - guess_locked: a player has committed a guess (without coordinates)
  - round_result: round ended, includes everyone's guesses + actual location
  - game_over: full leaderboard + xp gained

Client -> server `action`:
  - start: host starts the game
  - guess: {lat, lng} commit a guess for the current round
  - chat:  {text}
"""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from .models import Guess, Membership, Room, Round
from .scoring import haversine_m, points_from_distance

ROUND_REVEAL_SEC = 6
MAX_PANO_RETRIES = 20

_PANO_RETRIES: dict[int, int] = {}

class RoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return
        self.code = self.scope['url_route']['kwargs']['code']
        self.group_name = f'room.{self.code}'
        self.room = await self._get_room()
        if not self.room:
            await self.close(code=4404)
            return
        await self._ensure_membership()
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._broadcast_state()
        await self._broadcast({'type': 'system', 'text': f'{self.user.username} зашёл в комнату.'})

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        if hasattr(self, 'code') and hasattr(self, 'user') and getattr(self.user, 'is_authenticated', False):
            try:
                await self._auto_miss_on_disconnect()
            except Exception:
                pass

            try:
                await database_sync_to_async(self._drop_membership_sync)()
            except Exception:
                pass

    def _drop_membership_sync(self):
        try:
            room = Room.objects.get(code=self.code)
        except Room.DoesNotExist:
            return
        Membership.objects.filter(room=room, user=self.user).delete()
        if not Membership.objects.filter(room=room).exists():
            room.delete()

    async def _auto_miss_on_disconnect(self):
        result = await database_sync_to_async(self._auto_miss_sync)()
        if not result:
            return
        await self._broadcast({
            'type': 'guess_locked',
            'user': self.user.username,
        })
        if result[0] == 'end_round':
            room = await self._reload_room()
            rnd_obj = await database_sync_to_async(
                lambda pk: Round.objects.select_related('room', 'room__map').get(pk=pk)
            )(result[1])
            await self._end_round(room, rnd_obj)

    def _auto_miss_sync(self):
        try:
            room = Room.objects.get(code=self.code)
        except Room.DoesNotExist:
            return None
        if room.status != Room.Status.IN_GAME:
            return None
        rnd = room.rounds.order_by('-number').first()
        if not rnd or rnd.ended_at is not None:
            return None
        if not Membership.objects.filter(room=room, user=self.user).exists():
            return None
        if Guess.objects.filter(round=rnd, user=self.user).exists():
            return None
        Guess.objects.create(
            round=rnd, user=self.user, lat=0, lng=0,
            distance_m=room.map_def.max_distance_m, points=0,
        )
        members = Membership.objects.filter(room=room).count()
        guesses = Guess.objects.filter(round=rnd).count()
        if guesses >= members:
            return ('end_round', rnd.pk)
        return ('locked', None)

    async def receive_json(self, content, **kwargs):
        action = content.get('action')
        if action == 'start':
            await self._handle_start()
        elif action == 'guess':
            await self._handle_guess(content)
        elif action == 'pano_missing':
            await self._handle_pano_missing()
        elif action == 'chat':
            text = (content.get('text') or '').strip()[:200]
            if text:
                await self._broadcast({
                    'type': 'chat',
                    'user': self.user.username,
                    'text': text,
                })

    async def _handle_start(self):
        room = await self._reload_room()
        if room.host_id != self.user.id:
            await self.send_json({'type': 'error', 'text': 'Только хост может начать игру.'})
            return
        if room.status != Room.Status.LOBBY:
            return
        await self._start_round(1)

    async def _handle_pano_missing(self):
        room = await self._reload_room()
        if room.status != Room.Status.IN_GAME:
            return
        rnd = await self._current_round(room)
        if rnd is None or rnd.ended_at is not None:
            return

        count = _PANO_RETRIES.get(rnd.pk, 0)
        if count >= MAX_PANO_RETRIES:
            return
        _PANO_RETRIES[rnd.pk] = count + 1
        used = await database_sync_to_async(self._collect_used_coords_sync)(room.pk)
        lat, lng = await database_sync_to_async(room.map_def.random_point_excluding)(used)
        await database_sync_to_async(self._update_round_coords_sync)(rnd.pk, lat, lng)

        await self._broadcast({
            'type': 'round_started',
            'number': rnd.number,
            'total': room.rounds_total,
            'lat': lat,
            'lng': lng,
            'map_key': room.map_key,
            'duration': room.round_duration_sec,
        })

    async def _handle_guess(self, content):
        try:
            lat = float(content['lat'])
            lng = float(content['lng'])
        except (KeyError, TypeError, ValueError):
            return
        room = await self._reload_room()
        if room.status != Room.Status.IN_GAME:
            return
        rnd = await self._current_round(room)
        if rnd is None or rnd.ended_at is not None:
            return
        created = await self._create_guess(rnd, lat, lng, room.map_def.max_distance_m)
        if not created:
            return
        await self._broadcast({
            'type': 'guess_locked',
            'user': self.user.username,
        })
        if await self._everyone_guessed(rnd):
            await self._end_round(room, rnd)

    async def _start_round(self, number: int):
        room = await self._reload_room()
        used = await database_sync_to_async(self._collect_used_coords_sync)(room.pk)
        lat, lng = await database_sync_to_async(room.map_def.random_point_excluding)(used)
        rnd = await database_sync_to_async(Round.objects.create)(
            room=room, number=number, lat=lat, lng=lng,
        )
        await database_sync_to_async(
            Room.objects.filter(pk=room.pk).update
        )(status=Room.Status.IN_GAME, current_round=number)
        await self._broadcast({
            'type': 'round_started',
            'number': number,
            'total': room.rounds_total,
            'lat': lat,
            'lng': lng,
            'map_key': room.map_key,
            'duration': room.round_duration_sec,
        })
        await self._broadcast_state()
        asyncio.create_task(self._round_timer(rnd.pk, room.round_duration_sec))

    async def _round_timer(self, round_id: int, seconds: int):
        await asyncio.sleep(seconds)
        rnd = await database_sync_to_async(
            lambda: Round.objects.filter(pk=round_id).select_related('room', 'room__map').first()
        )()
        if not rnd or rnd.ended_at is not None:
            return
        room = rnd.room
        await self._end_round(room, rnd)

    async def _end_round(self, room: Room, rnd: Round):
        ended = await database_sync_to_async(self._finalize_round_sync)(rnd.pk)
        if not ended:
            return
        results, totals = await database_sync_to_async(self._round_results_sync)(rnd.pk)
        await self._broadcast({
            'type': 'round_result',
            'number': rnd.number,
            'actual': {'lat': rnd.lat, 'lng': rnd.lng},
            'guesses': results,
            'totals': totals,
        })

        await self._broadcast_state()

        asyncio.create_task(self._proceed_after_reveal(rnd.number, rnd.pk))

    async def _proceed_after_reveal(self, round_number: int, round_pk: int):
        await asyncio.sleep(ROUND_REVEAL_SEC)
        room = await self._reload_room()
        if round_number >= room.rounds_total:
            await self._end_game(room)
        else:
            await self._start_round(round_number + 1)

    async def _end_game(self, room: Room):
        leaderboard, xp_gains = await database_sync_to_async(self._end_game_sync)(room.pk)
        await self._broadcast({
            'type': 'game_over',
            'leaderboard': leaderboard,
            'xp_gains': xp_gains,
        })
        await self._broadcast_state()

    @database_sync_to_async
    def _get_room(self):
        return Room.objects.filter(code=self.code).select_related('host', 'map').first()

    @database_sync_to_async
    def _reload_room(self):
        return Room.objects.select_related('host', 'map').get(code=self.code)

    @database_sync_to_async
    def _ensure_membership(self):
        if self.room.status == Room.Status.LOBBY:
            Membership.objects.get_or_create(room=self.room, user=self.user)

    @database_sync_to_async
    def _current_round(self, room):
        return room.rounds.order_by('-number').first()

    def _update_round_coords_sync(self, round_id, lat, lng):
        Round.objects.filter(pk=round_id).update(lat=lat, lng=lng)

    def _collect_used_coords_sync(self, room_pk):
        return list(Round.objects.filter(room_id=room_pk).values_list('lat', 'lng'))

    @database_sync_to_async
    def _create_guess(self, rnd, lat, lng, max_distance_m):

        rnd.refresh_from_db(fields=['lat', 'lng'])
        if Guess.objects.filter(round=rnd, user=self.user).exists():
            return False
        dist = haversine_m(rnd.lat, rnd.lng, lat, lng)
        pts = points_from_distance(dist, max_distance_m)
        Guess.objects.create(
            round=rnd, user=self.user, lat=lat, lng=lng,
            distance_m=dist, points=pts,
        )
        Membership.objects.filter(room=rnd.room, user=self.user).update(
            score=models_F_add('score', pts),
        )
        return True

    @database_sync_to_async
    def _everyone_guessed(self, rnd):
        members = Membership.objects.filter(room=rnd.room).count()
        guesses = Guess.objects.filter(round=rnd).count()
        return guesses >= members

    def _finalize_round_sync(self, round_id):
        from django.db import transaction
        with transaction.atomic():
            rnd = Round.objects.select_for_update().get(pk=round_id)
            if rnd.ended_at is not None:
                return False
            rnd.ended_at = timezone.now()
            rnd.save(update_fields=['ended_at'])

            members = Membership.objects.filter(room=rnd.room).values_list('user_id', flat=True)
            guessed = set(Guess.objects.filter(round=rnd).values_list('user_id', flat=True))
            for uid in members:
                if uid not in guessed:
                    Guess.objects.create(
                        round=rnd, user_id=uid, lat=0, lng=0,
                        distance_m=rnd.room.map_def.max_distance_m, points=0,
                    )
        return True

    def _round_results_sync(self, round_id):
        rnd = Round.objects.select_related('room').get(pk=round_id)
        guesses = (
            Guess.objects.filter(round=rnd)
            .select_related('user__profile')
            .order_by('-points')
        )
        results = [
            {
                'user': g.user.username,
                'lat': g.lat,
                'lng': g.lng,
                'distance_m': round(g.distance_m, 1),
                'points': g.points,
            }
            for g in guesses
        ]
        totals = list(
            Membership.objects.filter(room=rnd.room)
            .select_related('user__profile')
            .order_by('-score')
            .values('user__username', 'score')
        )
        totals = [{'user': t['user__username'], 'score': t['score']} for t in totals]
        return results, totals

    def _end_game_sync(self, room_id):
        from django.db import transaction
        with transaction.atomic():
            room = Room.objects.select_for_update().get(pk=room_id)
            room.status = Room.Status.FINISHED
            room.finished_at = timezone.now()
            room.save(update_fields=['status', 'finished_at'])
            memberships = list(
                Membership.objects.filter(room=room)
                .select_related('user__profile')
                .order_by('-score')
            )
            leaderboard = [
                {'user': m.user.username, 'score': m.score}
                for m in memberships
            ]
            xp_gains = {}
            for idx, m in enumerate(memberships):
                gain = max(m.score // 10, 10)
                if idx == 0 and len(memberships) > 1:
                    gain += 250
                profile = getattr(m.user, 'profile', None)
                if profile is None:
                    continue
                profile.games_played += 1
                if idx == 0 and len(memberships) > 1:
                    profile.wins += 1
                profile.add_xp(gain)
                profile.save(update_fields=['games_played', 'wins', 'xp', 'level'])
                xp_gains[m.user.username] = gain
        return leaderboard, xp_gains

    async def _broadcast_state(self):
        snapshot = await database_sync_to_async(self._snapshot_sync)()
        await self._broadcast({'type': 'state', **snapshot})

    def _snapshot_sync(self):
        room = Room.objects.select_related('host', 'map').prefetch_related(
            'memberships__user__profile'
        ).get(code=self.code)
        players = []
        for m in room.memberships.all():

            profile = getattr(m.user, 'profile', None)
            players.append({
                'username': m.user.username,
                'nickname': getattr(profile, 'nickname', None) or m.user.username,
                'level': getattr(profile, 'level', 1),
                'avatar': getattr(profile, 'avatar_url', '') or '',
                'score': m.score,
                'is_host': m.user_id == room.host_id,
            })
        return {
            'room': {
                'code': room.code,
                'name': room.name,
                'status': room.status,
                'current_round': room.current_round,
                'rounds_total': room.rounds_total,
                'map_key': room.map_key,
                'host': room.host.username,
                'round_duration': room.round_duration_sec,
            },
            'players': players,
        }

    async def _broadcast(self, payload):
        await self.channel_layer.group_send(self.group_name, {'type': 'room.event', 'payload': payload})

    async def room_event(self, event):
        await self.send_json(event['payload'])

def models_F_add(field, value):
    """Tiny helper so the F() expression is testable."""
    from django.db.models import F
    return F(field) + value
