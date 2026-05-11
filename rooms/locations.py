"""Coordinate pools for each playable map.

Hand-picked points at locations that Yandex covers heavily with panoramas:
big avenues, well-known squares, central districts. Bounds describe the
playable rectangle (used to clamp the guess map and draw the boundary
overlay so players see where they can guess).
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class MapDef:
    key: str
    label: str
    center: tuple[float, float]
    zoom: int
    bounds: tuple[float, float, float, float]  # south, west, north, east
    points: tuple[tuple[float, float], ...]
    max_distance_m: float
    max_zoom: int = 15

    def random_point(self) -> tuple[float, float]:
        return random.choice(self.points)

    def random_point_excluding(
        self, used: list[tuple[float, float]] | set[tuple[float, float]] | None = None
    ) -> tuple[float, float]:
        """Pick a fresh point. Rounding to 4 decimals when comparing so float
        round-tripping through the DB doesn't falsely keep used points alive.

        After the hand-picked pool is exhausted, fall back to a uniformly
        random point within the playable bounds — mirrors the solo mode's
        ``tryRandom`` fallback so multiplayer rounds don't get stuck when
        the curated points have no Yandex panorama coverage left."""
        used_keys = {(round(u[0], 4), round(u[1], 4)) for u in (used or [])}
        pool = [p for p in self.points if (round(p[0], 4), round(p[1], 4)) not in used_keys]
        if pool:
            return random.choice(pool)
        south, west, north, east = self.bounds
        lat = south + random.random() * (north - south)
        lng = west + random.random() * (east - west)
        return (lat, lng)


ROSTOV = MapDef(
    key='rostov',
    label='Ростов-на-Дону',
    center=(47.2357, 39.7180),
    zoom=11,
    bounds=(47.165, 39.595, 47.310, 39.840),
    points=(
        (47.2222, 39.7178),  # Бол. Садовая / Будённовский
        (47.2256, 39.7383),  # Театральная пл.
        (47.2350, 39.7050),  # Пл. Свободы
        (47.2025, 39.7460),  # Левбердон
        (47.2540, 39.6680),  # ЗЖМ Стачки
        (47.2900, 39.7200),  # СЖМ Орбитальная
        (47.2300, 39.6500),  # Стачки запад
        (47.2380, 39.6720),  # Малиновского
        (47.2750, 39.7900),  # Сельмаш
        (47.2870, 39.7400),  # Военвед
        (47.2150, 39.7170),  # ЦГБ
        (47.2110, 39.7950),  # Чкаловский
        (47.2530, 39.7390),  # Каменка
        (47.2650, 39.7430),  # Северный
        (47.2270, 39.7240),  # Гражданская
        (47.2245, 39.7186),  # Пушкинская
        (47.2289, 39.7305),  # Соколова
        (47.2356, 39.7547),  # Шолохова
        (47.2412, 39.7818),  # Новый Колхозный
        (47.2200, 39.7330),  # Кировский
        (47.2410, 39.7050),  # Текучёва
        (47.2178, 39.7250),  # Энгельса
    ),
    max_distance_m=25000,
    max_zoom=15,
)

MOSCOW = MapDef(
    key='moscow',
    label='Москва',
    center=(55.7558, 37.6173),
    zoom=9,
    bounds=(55.560, 37.380, 55.920, 37.870),
    points=(
        (55.7572, 37.6155),  # Тверская / Манежная
        (55.7497, 37.5912),  # Арбат
        (55.7396, 37.5208),  # Кутузовский
        (55.7322, 37.5076),  # Поклонная гора
        (55.7113, 37.5440),  # Воробьёвы горы
        (55.7236, 37.5921),  # Ленинский 30
        (55.7625, 37.6440),  # Чистые пруды
        (55.7905, 37.6779),  # Сокольники
        (55.7589, 37.5747),  # Красная Пресня
        (55.7867, 37.5419),  # Ходынка
        (55.7305, 37.6033),  # Парк Горького
        (55.7164, 37.5523),  # Лужники
        (55.8294, 37.6313),  # ВДНХ
        (55.8214, 37.5677),  # Тимирязевская
        (55.8195, 37.4988),  # Войковская
        (55.6638, 37.4827),  # Юго-Западная
        (55.6502, 37.6019),  # Каховская
        (55.6532, 37.6483),  # Каширская
        (55.8508, 37.6489),  # Свиблово
        (55.6422, 37.5236),  # Беляево
        (55.6745, 37.5566),  # Профсоюзная
        (55.7702, 37.6781),  # Курская
        (55.7635, 37.6086),  # Театральная
        (55.7041, 37.7382),  # Кузьминки
        (55.8156, 37.7044),  # Бабушкинская
        (55.6692, 37.4795),  # Тёплый Стан
    ),
    max_distance_m=60000,
    max_zoom=14,
)

MAPS: dict[str, MapDef] = {m.key: m for m in (ROSTOV, MOSCOW)}
MAP_CHOICES = [(m.key, m.label) for m in MAPS.values()]
