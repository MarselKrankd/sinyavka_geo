from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import RoomCreateForm
from .locations import MAPS
from .models import Membership, Room
from django.http import Http404


# Rooms older than this with no memberships, or rooms in any non-finished
# state that haven't seen activity for a long time, get cleaned up on the
# next home page load. Avoids the home view drifting into a graveyard of
# half-dead test rooms.
EMPTY_ROOM_GRACE = timedelta(minutes=2)
STALE_ROOM_CUTOFF = timedelta(hours=2)


def _cleanup_stale_rooms():
    """Drop rooms nobody can finish: empty rooms (no memberships) past the
    short grace window, and any non-finished room older than the long
    cutoff. Cheap enough to run on every home view hit."""
    now = timezone.now()
    empty_cutoff = now - EMPTY_ROOM_GRACE
    stale_cutoff = now - STALE_ROOM_CUTOFF

    empty_ids = list(
        Room.objects
        .exclude(status=Room.Status.FINISHED)
        .annotate(member_count=Count('memberships'))
        .filter(member_count=0, created_at__lt=empty_cutoff)
        .values_list('pk', flat=True)
    )
    if empty_ids:
        Room.objects.filter(pk__in=empty_ids).delete()

    stale_ids = list(
        Room.objects
        .exclude(status=Room.Status.FINISHED)
        .filter(created_at__lt=stale_cutoff)
        .values_list('pk', flat=True)
    )
    if stale_ids:
        Room.objects.filter(pk__in=stale_ids).delete()


@login_required
def home(request):
    _cleanup_stale_rooms()
    rooms = (
        Room.objects.filter(is_private=False)
        .exclude(status=Room.Status.FINISHED)
        .annotate(player_count=Count('memberships'))
        # Hide rooms with no real members — a final safety net in case
        # cleanup didn't run yet (e.g., room just emptied this second).
        .filter(player_count__gt=0)
        .select_related('host')
    )
    return render(request, 'rooms/home.html', {
        'rooms': rooms,
        'maps': MAPS,
    })


@login_required
def create_room(request):
    if request.method == 'POST':
        form = RoomCreateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                room = form.save(commit=False)
                room.host = request.user
                for _ in range(8):
                    code = Room.generate_code()
                    if not Room.objects.filter(code=code).exists():
                        room.code = code
                        break
                room.save()
                Membership.objects.create(room=room, user=request.user)
            messages.success(request, 'Комната создана.')
            return redirect(room)
    else:
        form = RoomCreateForm()
    return render(request, 'rooms/create_room.html', {'form': form})


@login_required
def room_detail(request, code):
    room = get_object_or_404(
        Room.objects.select_related('host').prefetch_related('memberships__user__profile'),
        code=code,
    )
    membership = Membership.objects.filter(room=room, user=request.user).first()
    if not membership and room.status != Room.Status.LOBBY:
        messages.error(request, 'Игра уже идёт, к ней нельзя присоединиться.')
        return redirect('rooms:home')

    return render(request, 'rooms/room.html', {
        'room': room,
        'membership': membership,
        'map_def': room.map_def,
    })


@login_required
@require_POST
def join_room(request, code):
    room = get_object_or_404(Room, code=code)
    if room.status != Room.Status.LOBBY:
        messages.error(request, 'В эту комнату уже нельзя зайти.')
        return redirect('rooms:home')
    if room.is_full and not Membership.objects.filter(room=room, user=request.user).exists():
        messages.error(request, 'Комната заполнена.')
        return redirect('rooms:home')
    Membership.objects.get_or_create(room=room, user=request.user)
    return redirect(room)


@login_required
@require_POST
def leave_room(request, code):
    room = get_object_or_404(Room, code=code)
    Membership.objects.filter(room=room, user=request.user).delete()
    # Delete the room when no one's left, regardless of who's leaving — the
    # previous version only deleted on host exit, so a non-host being the
    # last to leave would orphan the room.
    if not room.memberships.exists():
        room.delete()
    return redirect('rooms:home')


@login_required
def solo(request, map_key):
    map_def = MAPS.get(map_key)
    if not map_def:
        raise Http404('Карта не найдена')
    payload = {
        'key': map_def.key,
        'label': map_def.label,
        'center': list(map_def.center),
        'zoom': map_def.zoom,
        'max_zoom': map_def.max_zoom,
        'bounds': list(map_def.bounds),
        'points': [list(p) for p in map_def.points],
        'max_distance_m': map_def.max_distance_m,
    }
    return render(request, 'rooms/solo.html', {
        'map_def': map_def,
        'map_payload': payload,
    })


@login_required
def profile(request):
    user = request.user
    profile_obj = getattr(user, 'profile', None)
    rooms_played = user.memberships.count() if hasattr(user, 'memberships') else 0
    return render(request, 'rooms/profile.html', {
        'profile': profile_obj,
        'rooms_played': rooms_played,
    })
