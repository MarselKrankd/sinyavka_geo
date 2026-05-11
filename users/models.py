from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    pass

class PlayerProfile(models.Model):
    XP_PER_LEVEL = 1000

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile',
    )
    nickname = models.CharField(max_length=50, unique=True)
    avatar_url = models.URLField(blank=True, default='')
    wins = models.PositiveIntegerField(default=0)
    games_played = models.PositiveIntegerField(default=0)
    xp = models.PositiveIntegerField(default=0)
    level = models.PositiveIntegerField(default=1)

    def add_xp(self, amount: int) -> int:
        if amount <= 0:
            return 0
        self.xp += amount
        levels_gained = 0
        while self.xp >= self.XP_PER_LEVEL:
            self.xp -= self.XP_PER_LEVEL
            self.level += 1
            levels_gained += 1
        return levels_gained

    def __str__(self):
        return self.nickname or self.user.get_username()
