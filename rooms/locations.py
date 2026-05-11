"""Coordinate pools for each playable map.

Hand-picked points where Google Street View imagery is known to exist. Bounds
are used to clamp the guess map to the play area.
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
    # Max meaningful guess distance in metres — used to scale 0..5000 score.
    max_distance_m: float

    def random_point(self) -> tuple[float, float]:
        return random.choice(self.points)


SINYAVSKOE = MapDef(
    key='sinyavskoe',
    label='с. Синявское',
    center=(47.2675, 39.2580),
    zoom=14,
    bounds=(47.245, 39.215, 47.290, 39.305),
    points=(
        (47.2680, 39.2545),
        (47.2702, 39.2576),
        (47.2664, 39.2611),
        (47.2645, 39.2532),
        (47.2718, 39.2640),
        (47.2657, 39.2497),
        (47.2691, 39.2718),
        (47.2632, 39.2589),
    ),
    max_distance_m=8000,
)

ROSTOV = MapDef(
    key='rostov',
    label='Ростов-на-Дону',
    center=(47.2225, 39.7187),
    zoom=12,
    bounds=(47.150, 39.580, 47.330, 39.870),
    points=(
        (47.2225, 39.7187),
        (47.2357, 39.7015),
        (47.2156, 39.7438),
        (47.2782, 39.7619),
        (47.2089, 39.6802),
        (47.2403, 39.7351),
        (47.1978, 39.7204),
        (47.2674, 39.7048),
        (47.2294, 39.6943),
        (47.2511, 39.7752),
        (47.2188, 39.8123),
        (47.1843, 39.6611),
    ),
    max_distance_m=40000,
)

MOSCOW = MapDef(
    key='moscow',
    label='Москва',
    center=(55.7558, 37.6173),
    zoom=10,
    bounds=(55.490, 37.320, 55.960, 37.940),
    points=(
        (55.7558, 37.6173),
        (55.7522, 37.6156),
        (55.7297, 37.6019),
        (55.7887, 37.5413),
        (55.7100, 37.6602),
        (55.8431, 37.6557),
        (55.6692, 37.4795),
        (55.7965, 37.5378),
        (55.7308, 37.5870),
        (55.7178, 37.5499),
        (55.6809, 37.6098),
        (55.7505, 37.5839),
        (55.8311, 37.4844),
        (55.7039, 37.5305),
        (55.7702, 37.6781),
    ),
    max_distance_m=100000,
)

MAPS: dict[str, MapDef] = {m.key: m for m in (SINYAVSKOE, ROSTOV, MOSCOW)}
MAP_CHOICES = [(m.key, m.label) for m in MAPS.values()]
