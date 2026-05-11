
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Room',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80)),
                ('code', models.CharField(db_index=True, max_length=12, unique=True)),
                ('map_key', models.CharField(choices=[('sinyavskoe', 'с. Синявское'), ('rostov', 'Ростов-на-Дону'), ('moscow', 'Москва')], max_length=32)),
                ('is_private', models.BooleanField(default=False)),
                ('max_players', models.PositiveSmallIntegerField(default=6)),
                ('rounds_total', models.PositiveSmallIntegerField(default=5)),
                ('round_duration_sec', models.PositiveSmallIntegerField(default=90)),
                ('status', models.CharField(choices=[('lobby', 'Лобби'), ('in_game', 'Игра идёт'), ('finished', 'Завершена')], default='lobby', max_length=16)),
                ('current_round', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('host', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hosted_rooms', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Round',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveSmallIntegerField()),
                ('lat', models.FloatField()),
                ('lng', models.FloatField()),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rounds', to='rooms.room')),
            ],
            options={
                'ordering': ['number'],
                'unique_together': {('room', 'number')},
            },
        ),
        migrations.CreateModel(
            name='Membership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('score', models.PositiveIntegerField(default=0)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to=settings.AUTH_USER_MODEL)),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='rooms.room')),
            ],
            options={
                'ordering': ['joined_at'],
                'unique_together': {('room', 'user')},
            },
        ),
        migrations.CreateModel(
            name='Guess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lat', models.FloatField()),
                ('lng', models.FloatField()),
                ('distance_m', models.FloatField(default=0)),
                ('points', models.PositiveIntegerField(default=0)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('round', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guesses', to='rooms.round')),
            ],
            options={
                'ordering': ['submitted_at'],
                'unique_together': {('round', 'user')},
            },
        ),
    ]
