"""Preferences: the YAML file the matcher reads, validated by Pydantic.

REGIONS maps canonical city names (models.CITIES) to the regions the rules talk about.
It is code, not YAML, because it is a fact about Israel, not a preference.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator

REGIONS: dict[str, str] = {
    # south (Be'er Sheva area and the southern coastal plain)
    "Beer Sheva": "south", "Omer": "south", "Dimona": "south", "Ofakim": "south", "Sderot": "south",
    "Kiryat Gat": "south", "Ashkelon": "south", "Yeruham": "south", "Netivot": "south",
    # center (Gush Dan, Sharon, Shfela). Ashdod is counted as center: 1h+ from Be'er Sheva.
    "Ashdod": "center", "Tel Aviv": "center", "Ramat Gan": "center", "Petah Tikva": "center",
    "Rosh HaAyin": "center", "Herzliya": "center", "Raanana": "center", "Hod HaSharon": "center",
    "Kfar Saba": "center", "Netanya": "center", "Rehovot": "center", "Ness Ziona": "center",
    "Rishon LeZion": "center", "Holon": "center", "Airport City": "center", "Lod": "center", "Modiin": "center",
    "Or Yehuda": "center",
    # north
    "Yokneam": "north", "Haifa": "north", "Caesarea": "north", "Migdal HaEmek": "north",
    # jerusalem
    "Jerusalem": "jerusalem",
}


def region_of(city: Optional[str]) -> Optional[str]:
    if not city:
        return None
    if city in REGIONS:
        return REGIONS[city]
    low = city.strip().lower()
    for k, v in REGIONS.items():
        if k.lower() == low:
            return v
    return "other"


class Target(BaseModel):
    cv: str
    accept_seniority: list[str] = Field(default_factory=lambda: ["mid", "senior"])
    prefer_hardware: bool = False
    web_score: int = Field(25, ge=0, le=50)


class LocationRule(BaseModel):
    region: str
    modes: list[Optional[str]]
    points: int = Field(ge=0, le=30)


class LocationPrefs(BaseModel):
    home_region: str = "south"
    rules: list[LocationRule]
    unknown_location_points: int = Field(15, ge=0, le=30)
    default_points: int = Field(5, ge=0, le=30)


class ExperiencePrefs(BaseModel):
    ok_up_to_years: int = 6
    stretch_up_to_years: int = 8
    stretch_points: int = Field(8, ge=0, le=20)
    junior_points: int = Field(5, ge=0, le=20)
    lead_points: int = Field(8, ge=0, le=20)


class Thresholds(BaseModel):
    match: int = Field(90, ge=0, le=100)
    maybe: int = Field(60, ge=0, le=100)


class Preferences(BaseModel):
    owner: str = "Me"
    experience_years: int = 5
    targets: dict[str, Target]
    location: LocationPrefs
    experience: ExperiencePrefs = ExperiencePrefs()
    thresholds: Thresholds = Thresholds()
    secondary_points: int = Field(35, ge=0, le=50)
    show_other_jobs: bool = True
    morning_only_sources: list[str] = Field(default_factory=lambda: ["airtable"])

    @field_validator("targets")
    @classmethod
    def _known_categories(cls, v: dict) -> dict:
        from .models import CATEGORIES

        bad = [k for k in v if k not in CATEGORIES]
        if bad:
            raise ValueError(f"unknown target categories: {bad}; allowed: {list(CATEGORIES)}")
        return v


DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "preferences.yaml"


def load_prefs(path: Union[str, Path, None] = None) -> Preferences:
    data = yaml.safe_load(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    return Preferences.model_validate(data)


def save_prefs(prefs: Preferences, path: Union[str, Path]) -> None:
    Path(path).write_text(yaml.safe_dump(prefs.model_dump(), allow_unicode=True, sort_keys=False), encoding="utf-8")
