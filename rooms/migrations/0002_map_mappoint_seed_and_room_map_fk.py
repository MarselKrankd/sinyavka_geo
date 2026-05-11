import django.db.models.deletion
from django.db import migrations, models

ROSTOV = {
    'key':         ,
    'label':                 ,
    'center_lat': 47.2357, 'center_lng': 39.7180,
    'zoom': 11, 'max_zoom': 15,
    'south': 47.165, 'west': 39.595, 'north': 47.310, 'east': 39.840,
    'max_distance_m': 25000,
    'points': [
        (47.2222, 39.7178, 'Бол. Садовая / Будённовский'),
        (47.2256, 39.7383, 'Театральная пл.'),
        (47.2350, 39.7050, 'Пл. Свободы'),
        (47.2025, 39.7460, 'Левбердон'),
        (47.2540, 39.6680, 'ЗЖМ Стачки'),
        (47.2900, 39.7200, 'СЖМ Орбитальная'),
        (47.2300, 39.6500, 'Стачки запад'),
        (47.2380, 39.6720, 'Малиновского'),
        (47.2750, 39.7900, 'Сельмаш'),
        (47.2870, 39.7400, 'Военвед'),
        (47.2150, 39.7170, 'ЦГБ'),
        (47.2110, 39.7950, 'Чкаловский'),
        (47.2530, 39.7390, 'Каменка'),
        (47.2650, 39.7430, 'Северный'),
        (47.2270, 39.7240, 'Гражданская'),
        (47.2245, 39.7186, 'Пушкинская'),
        (47.2289, 39.7305, 'Соколова'),
        (47.2356, 39.7547, 'Шолохова'),
        (47.2412, 39.7818, 'Новый Колхозный'),
        (47.2200, 39.7330, 'Кировский'),
        (47.2410, 39.7050, 'Текучёва'),
        (47.2178, 39.7250, 'Энгельса'),
    ],
}

MOSCOW = {
    'key':         ,
    'label':         ,
    'center_lat': 55.7558, 'center_lng': 37.6173,
    'zoom': 9, 'max_zoom': 14,
    'south': 55.560, 'west': 37.380, 'north': 55.920, 'east': 37.870,
    'max_distance_m': 60000,
    'points': [
        (55.7572, 37.6155, 'Тверская / Манежная'),
        (55.7497, 37.5912, 'Арбат'),
        (55.7396, 37.5208, 'Кутузовский'),
        (55.7322, 37.5076, 'Поклонная гора'),
        (55.7113, 37.5440, 'Воробьёвы горы'),
        (55.7236, 37.5921, 'Ленинский 30'),
        (55.7625, 37.6440, 'Чистые пруды'),
        (55.7905, 37.6779, 'Сокольники'),
        (55.7589, 37.5747, 'Красная Пресня'),
        (55.7867, 37.5419, 'Ходынка'),
        (55.7305, 37.6033, 'Парк Горького'),
        (55.7164, 37.5523, 'Лужники'),
        (55.8294, 37.6313, 'ВДНХ'),
        (55.8214, 37.5677, 'Тимирязевская'),
        (55.8195, 37.4988, 'Войковская'),
        (55.6638, 37.4827, 'Юго-Западная'),
        (55.6502, 37.6019, 'Каховская'),
        (55.6532, 37.6483, 'Каширская'),
        (55.8508, 37.6489, 'Свиблово'),
        (55.6422, 37.5236, 'Беляево'),
        (55.6745, 37.5566, 'Профсоюзная'),
        (55.7702, 37.6781, 'Курская'),
        (55.7635, 37.6086, 'Театральная'),
        (55.7041, 37.7382, 'Кузьминки'),
        (55.8156, 37.7044, 'Бабушкинская'),
        (55.6692, 37.4795, 'Тёплый Стан'),
    ],
}

def seed_maps(apps, schema_editor):
    Map = apps.get_model('rooms', 'Map')
    MapPoint = apps.get_model('rooms', 'MapPoint')
    for data in (ROSTOV, MOSCOW):
        points = data['points']
        defaults = {k: v for k, v in data.items() if k != 'key' and k != 'points'}
        m, _ = Map.objects.update_or_create(key=data['key'], defaults=defaults)
        m.points_set.all().delete()
        MapPoint.objects.bulk_create([
            MapPoint(map=m, lat=lat, lng=lng, label=label) for lat, lng, label in points
        ])

def unseed_maps(apps, schema_editor):
    Map = apps.get_model('rooms', 'Map')
    Map.objects.filter(key__in=('rostov', 'moscow')).delete()

def backfill_room_map(apps, schema_editor):
    Map = apps.get_model('rooms', 'Map')
    Room = apps.get_model('rooms', 'Room')
    maps_by_key = {m.key: m for m in Map.objects.all()}
    fallback = maps_by_key.get('rostov') or next(iter(maps_by_key.values()), None)
    for room in Room.objects.all():
        m = maps_by_key.get(room.map_key) or fallback
        if m is None:
            continue
        room.map = m
        room.save(update_fields=['map'])

def restore_room_map_key(apps, schema_editor):
    Room = apps.get_model('rooms', 'Room')
    for room in Room.objects.all():
        room.map_key = room.map.key
        room.save(update_fields=['map_key'])

class Migration(migrations.Migration):

    dependencies = [
        ('rooms', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Map',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=32, unique=True)),
                ('label', models.CharField(max_length=80)),
                ('center_lat', models.FloatField()),
                ('center_lng', models.FloatField()),
                ('zoom', models.PositiveSmallIntegerField(default=11)),
                ('max_zoom', models.PositiveSmallIntegerField(default=15)),
                ('south', models.FloatField()),
                ('west', models.FloatField()),
                ('north', models.FloatField()),
                ('east', models.FloatField()),
                ('max_distance_m', models.FloatField()),
            ],
            options={'ordering': ['label']},
        ),
        migrations.CreateModel(
            name='MapPoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lat', models.FloatField()),
                ('lng', models.FloatField()),
                ('label', models.CharField(blank=True, default='', max_length=120)),
                ('map', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='points_set', to='rooms.map')),
            ],
            options={'ordering': ['id']},
        ),
        migrations.RunPython(seed_maps, unseed_maps),
        migrations.AddField(
            model_name='room',
            name='map',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rooms', to='rooms.map'),
        ),
        migrations.RunPython(backfill_room_map, restore_room_map_key),
        migrations.AlterField(
            model_name='room',
            name='map',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rooms', to='rooms.map'),
        ),
        migrations.RemoveField(
            model_name='room',
            name='map_key',
        ),
    ]
