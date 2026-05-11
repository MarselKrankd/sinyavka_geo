from django.contrib import admin

from .models import Guess, Membership, Room, Round


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    readonly_fields = ('joined_at',)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'map_key', 'host', 'status', 'current_round', 'rounds_total', 'created_at')
    list_filter = ('status', 'map_key', 'is_private')
    search_fields = ('name', 'code', 'host__username')
    inlines = [MembershipInline]


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ('room', 'number', 'lat', 'lng', 'started_at', 'ended_at')
    list_filter = ('room__map_key',)


@admin.register(Guess)
class GuessAdmin(admin.ModelAdmin):
    list_display = ('round', 'user', 'distance_m', 'points', 'submitted_at')
    list_filter = ('round__room__map_key',)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('room', 'user', 'score', 'joined_at')
