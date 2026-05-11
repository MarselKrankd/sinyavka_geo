from django.urls import path

from . import views

app_name = 'rooms'

urlpatterns = [
    path('', views.home, name='home'),
    path('create/', views.create_room, name='create_room'),
    path('solo/<slug:map_key>/', views.solo, name='solo'),
    path('profile/', views.profile, name='profile'),
    path('r/<str:code>/', views.room_detail, name='room_detail'),
    path('r/<str:code>/join/', views.join_room, name='join_room'),
    path('r/<str:code>/leave/', views.leave_room, name='leave_room'),
]
