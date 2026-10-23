"""Minimale nabootsing van de Home Assistant-templateomgeving voor de tests.

Laadt packages/bevcc.yaml en rendert de Jinja-templates tegen gesimuleerde
toestanden. Alleen de HA-functies die BEVCC gebruikt zijn nagebouwd.
"""
from __future__ import annotations

import ast
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from jinja2 import StrictUndefined
from jinja2.sandbox import ImmutableSandboxedEnvironment

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "packages" / "bevcc.yaml"
DASHBOARD = ROOT / "dashboard" / "bevcc_dashboard.yaml"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class _Loader(yaml.SafeLoader):
    pass


_Loader.add_constructor("!secret", lambda loader, node: f"<secret:{node.value}>")


def load_yaml(path: Path):
    with open(path, encoding="utf-8") as f:
        return yaml.load(f, Loader=_Loader)  # noqa: S506 - eigen SafeLoader-subklasse


CFG = load_yaml(PACKAGE)

# Vast tijdstip voor de tests; per test aan te passen met set_now().
NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
_MISSING = object()


def set_now(dt: datetime) -> None:
    global NOW
    NOW = dt


class S:
    """Een entiteitstoestand: state, attributen en leeftijd in minuten."""

    def __init__(self, state, attrs=None, age_min=60):
        self.state = str(state)
        self.attributes = attrs or {}
        self.last_changed = NOW - timedelta(minutes=age_min)
        self.last_updated = self.last_changed


class _Domain:
    def __init__(self, db, domain):
        self._db, self._d = db, domain

    def __getattr__(self, object_id):
        if object_id.startswith("_") or object_id in ("unsafe_callable", "alters_data"):
            raise AttributeError(object_id)
        return self._db.get(f"{self._d}.{object_id}")


class _States:
    def __init__(self, db):
        self._db = db

    def __call__(self, entity_id):
        s = self._db.get(entity_id)
        return s.state if s else "unknown"

    def __getattr__(self, domain):
        if domain.startswith("_") or domain in ("unsafe_callable", "alters_data"):
            raise AttributeError(domain)
        return _Domain(self._db, domain)


def _is_number(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return f == f and f not in (float("inf"), float("-inf"))


def _float(v, default=_MISSING):
    try:
        return float(v)
    except (TypeError, ValueError):
        if default is _MISSING:
            raise ValueError(f"float kreeg {v!r} zonder standaardwaarde") from None
        return default


def _int(v, default=_MISSING, base=10):
    try:
        if isinstance(v, str) and base != 10:
            return int(v, base)
        return int(float(v))
    except (TypeError, ValueError):
        if default is _MISSING:
            raise ValueError(f"int kreeg {v!r} zonder standaardwaarde") from None
        return default


def make_env(db, strict=False):
    env = ImmutableSandboxedEnvironment(undefined=StrictUndefined) if strict else ImmutableSandboxedEnvironment()

    def is_state(entity_id, value):
        s = db.get(entity_id)
        if s is None:
            return False
        return s.state in value if isinstance(value, list) else s.state == value

    def state_attr(entity_id, attr):
        s = db.get(entity_id)
        return s.attributes.get(attr) if s else None

    def has_value(entity_id):
        s = db.get(entity_id)
        return s is not None and s.state not in ("unknown", "unavailable")

    env.filters.update(
        float=_float,
        int=_int,
        is_number=_is_number,
        regex_replace=lambda v, find="", replace="": re.sub(find, replace, str(v)),
    )
    env.tests["is_number"] = _is_number
    env.globals.update(
        states=_States(db), is_state=is_state, state_attr=state_attr, has_value=has_value,
        is_number=_is_number, now=lambda: NOW, timedelta=timedelta,
        as_timestamp=lambda d: d.timestamp(),
    )
    return env


def render(template: str, db: dict | None = None, strict=False, **variables) -> str:
    """Rendert zoals HA: resultaat als getrimde tekst."""
    return make_env(db or {}, strict).from_string(template).render(**variables).strip()


def native(text: str):
    """HA zet een gerenderde variabele om naar een Python-type als dat kan."""
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


def truthy(text: str) -> bool:
    return text.strip().lower() in ("true", "on", "1", "yes")


def slugify(text: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", text.lower())).strip("_")


def find(section: str, name: str) -> dict:
    """Een template-entiteit (sectie 'sensor', 'binary_sensor', 'select') op naam."""
    for block in CFG["template"]:
        for item in block.get(section, []):
            if item["name"] == name:
                return item
    raise KeyError(name)


def automation(automation_id: str) -> dict:
    for a in CFG["automation"]:
        if a["id"] == automation_id:
            return a
    raise KeyError(automation_id)


def rest_resource(fragment: str) -> dict:
    for r in CFG["rest"]:
        if fragment in r["resource"]:
            return r
    raise KeyError(fragment)
