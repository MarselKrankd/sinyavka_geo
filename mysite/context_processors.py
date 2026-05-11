from django.conf import settings

def maps_settings(request):
    return {'YANDEX_MAPS_API_KEY': settings.YANDEX_MAPS_API_KEY}
