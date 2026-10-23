"""Samenhang: entiteit-ID's, secrets, versie, dashboard."""
import re

import pytest

import ha
from ha import S

PACKAGE_TEKST = ha.PACKAGE.read_text(encoding="utf-8")
DASHBOARD_TEKST = ha.DASHBOARD.read_text(encoding="utf-8")
DOMEINEN = ("sensor", "binary_sensor", "select", "input_text", "input_number",
            "input_select", "input_boolean", "automation")
VERWIJZING = re.compile(r"\b(" + "|".join(DOMEINEN) + r")\.(bevcc_[a-z0-9_]+)")


def gedefinieerd():
    """Alle entiteit-ID's die het package aanmaakt (HA leidt ze af van de naam)."""
    ids = set()
    for domein in ("input_text", "input_number", "input_select", "input_boolean"):
        ids |= {f"{domein}.{k}" for k in ha.CFG.get(domein, {})}
    for r in ha.CFG["rest"]:
        for domein in ("sensor", "binary_sensor"):
            ids |= {f"{domein}.{ha.slugify(s['name'])}" for s in r.get(domein, [])}
    for c in ha.CFG["command_line"]:
        for domein, s in c.items():
            ids.add(f"{domein}.{ha.slugify(s['name'])}")
    for blok in ha.CFG["template"]:
        for domein, items in blok.items():
            ids |= {f"{domein}.{ha.slugify(i['name'])}" for i in items}
    ids |= {f"automation.{ha.slugify(a['alias'])}" for a in ha.CFG["automation"]}
    return ids


GEDEFINIEERD = gedefinieerd()


@pytest.mark.parametrize("bron, tekst", [("package", PACKAGE_TEKST), ("dashboard", DASHBOARD_TEKST)])
def test_alle_verwijzingen_bestaan(bron, tekst):
    verwezen = {f"{d}.{o}" for d, o in VERWIJZING.findall(tekst)}
    assert verwezen, bron
    assert verwezen - GEDEFINIEERD == set(), f"{bron} verwijst naar onbekende entiteiten"


def test_alles_heeft_bevcc_prefix():
    for eid in GEDEFINIEERD:
        assert eid.split(".", 1)[1].startswith("bevcc_"), eid


def test_unique_ids_uniek_en_gelijk_aan_entiteit_id():
    gezien = set()
    items = [s for r in ha.CFG["rest"] for d in ("sensor", "binary_sensor") for s in r.get(d, [])]
    items += [s for c in ha.CFG["command_line"] for s in c.values()]
    items += [i for blok in ha.CFG["template"] for lst in blok.values() for i in lst]
    for i in items:
        assert i["unique_id"] == ha.slugify(i["name"]), i["name"]
        assert i["unique_id"] not in gezien
        gezien.add(i["unique_id"])
    ids = [a["id"] for a in ha.CFG["automation"]]
    assert len(ids) == len(set(ids))
    assert all(a["id"] == ha.slugify(a["alias"]) for a in ha.CFG["automation"])


def test_evcc_entiteiten_alleen_via_prefix():
    # Geen vaste EVCC-entiteiten: alles loopt via bevcc_evcc_prefix/-laadpunt.
    zonder_commentaar = "\n".join(r.split(" #")[0] for r in PACKAGE_TEKST.splitlines() if not r.lstrip().startswith("#"))
    assert not re.search(r"\b(sensor|binary_sensor|select)\.evcc_", zonder_commentaar)
    assert "alfen" not in zonder_commentaar


def test_secrets_voorbeeld_compleet():
    gebruikt = set(re.findall(r"!secret\s+(\S+)", PACKAGE_TEKST))
    voorbeeld = ha.load_yaml(ha.ROOT / "secrets.example.yaml")
    assert gebruikt == set(voorbeeld)


def test_versie_gelijk_aan_changelog():
    versie = ha.find("sensor", "BEVCC versie")["state"]
    changelog = (ha.ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    eerste = re.search(r"^## \[?v?(\d+\.\d+\.\d+)", changelog, re.M).group(1)
    assert versie == eerste


def test_github_repo_overal_gelijk():
    repos = set(re.findall(r"github\.com/(?:repos/)?([A-Za-z0-9_.-]+/BEVCC)", PACKAGE_TEKST))
    readme = (ha.ROOT / "README.md").read_text(encoding="utf-8")
    repos |= set(re.findall(r"github\.com/([A-Za-z0-9_.-]+/BEVCC)", readme))
    assert len(repos) == 1, repos


def test_standaardwaarden_binnen_grenzen():
    acties = ha.automation("bevcc_standaardwaarden")["actions"]
    gezet = set()
    for a in acties:
        if a["action"] == "input_number.set_value":
            key = a["target"]["entity_id"].split(".", 1)[1]
            spec = ha.CFG["input_number"][key]
            assert spec["min"] <= a["data"]["value"] <= spec["max"], key
            assert "initial" not in spec, key
            gezet.add(key)
        if a["action"] == "input_select.select_option":
            key = a["target"]["entity_id"].split(".", 1)[1]
            assert a["data"]["option"] in ha.CFG["input_select"][key]["options"]
    assert gezet == set(ha.CFG["input_number"]), "elke instelling krijgt een standaardwaarde"


def _markdown_kaarten(node):
    if isinstance(node, dict):
        if node.get("type") == "markdown":
            yield node["content"]
        for v in node.values():
            yield from _markdown_kaarten(v)
    elif isinstance(node, list):
        for v in node:
            yield from _markdown_kaarten(v)


@pytest.mark.parametrize("boost_bij, grens", [("alleen aFRR", 0.20), ("aFRR + onbalans", 0.20), ("alleen aFRR", -0.5)])
def test_dashboard_templates_renderen(boost_bij, grens):
    db = {
        "sensor.bevcc_afnameprijs": S(0.39088, {"kaal": 0.2149}),
        "sensor.bevcc_balans_kwartierprijs": S(0.4),
        "sensor.bevcc_prijsbron": S("onbalans (TenneT afnemen)"),
        "input_number.bevcc_pauze_boven": S(0.35),
        "input_number.bevcc_boost_onder": S(grens),
        "input_number.bevcc_energiebelasting": S(0.11085),
        "input_number.bevcc_leverkosten": S(0.02),
        "input_number.bevcc_accu_ondergrens": S(50),
        "input_number.bevcc_boost_min_import": S(2.0),
        "input_select.bevcc_boost_bij": S(boost_bij),
        "input_select.bevcc_status": S("rust"),
        "input_text.bevcc_te_herstellen_modus": S("smart"),
        "input_text.bevcc_evcc_prefix": S("evcc"),
        "input_text.bevcc_evcc_laadpunt": S("alfen"),
        "sensor.bevcc_laatste_versie": S("1.0.1"),
        "sensor.bevcc_versie": S("1.0.0"),
    }
    kaarten = list(_markdown_kaarten(ha.load_yaml(ha.DASHBOARD)))
    assert kaarten
    for k in kaarten:
        uit = ha.render(k, db)
        assert "€ 0,391" in uit or "<ha-alert" in uit
