from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import RoomCreateForm
from .locations import MAPS
from .models import Membership, Room
from django.http import Http404


@login_required
def home(request):
    rooms = (
        Room.objects.filter(is_private=False)
        .exclude(status=Room.Status.FINISHED)
        .annotate(player_count=Count('memberships'))
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
    if room.host_id == request.user.id and not room.memberships.exists():
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
