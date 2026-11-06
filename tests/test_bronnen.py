"""Bronnen: Balans-API, TenneT-onbalansprijs (Tenergy), gecombineerde prijs, versiecontrole."""
import json
import subprocess
import sys
from datetime import datetime, timezone

import pytest

import ha
from ha import S

BALANS = json.loads((ha.FIXTURES / "balans_current_prices.json").read_text(encoding="utf-8"))
RES = ha.rest_resource("balansenergie")
SESSIE = RES["binary_sensor"][0]
REST_SENSOR = {s["name"]: s for s in RES["sensor"]}
VAST = 0.02 + 0.11085  # leverkosten + energiebelasting (standaardwaarden)


def utc(hm):
    h, m = map(int, hm.split(":"))
    return datetime(2026, 10, 17, h, m, tzinfo=timezone.utc)


def rest(item, when, data=BALANS, db=None):
    """Rendert een REST-entiteit zoals HA: availability (strict) en dan de waarde."""
    ha.set_now(when)
    kw = {} if data is None else {"value_json": data}
    if not ha.truthy(ha.render(item["availability"], db, strict=True, **kw)):
        return "unavailable"
    return ha.render(item["value_template"], db, **kw)


# --- Balans-API -------------------------------------------------------------

@pytest.mark.parametrize("hm, verwacht", [
    ("10:05", "False"),   # geen sessie, wel een aFRR-bod
    ("10:20", "True"),    # aFRR-importsessie
    ("10:33", "True"),    # overloop: eerste 5 min na een sessiekwartier
    ("10:36", "False"),   # overloop voorbij; alleen controlDirections import (missing_bid) telt niet
    ("10:50", "False"),   # exportsessie telt niet
    ("11:02", "False"),   # dynamische import zonder aFRR, vorige was export
    ("11:20", "True"),    # dynamische import + aFRR-importsessie
    ("11:32", "True"),    # nieuw kwartier nog niet gemeld: overloop uit 11:15
    ("11:36", "False"),
])
def test_afrr_importsessie(hm, verwacht):
    assert rest(SESSIE, utc(hm)) == verwacht


@pytest.mark.parametrize("data", [None, "<html>inloggen</html>", {"detail": "Niet ingelogd"}])
def test_sessie_unavailable_bij_ongeldig_antwoord(data):
    assert rest(SESSIE, utc("10:20"), data) == "unavailable"


@pytest.mark.parametrize("hm, verwacht", [
    ("10:05", round(0.18 * 1.21 + VAST, 5)),     # onbalansprijs; aFRR-bod en day-ahead-velden genegeerd
    ("10:40", round(0.19 * 1.21 + VAST, 5)),     # missing_bid: geen aFRR-prijs, onbalansprijs
    ("10:20", round(0.0337 * 1.21 + VAST, 5)),   # aFRR-importprijs tijdens de sessie
    ("10:50", round(4.17 * 1.21 + VAST, 5)),     # prijspiek tijdens exportsessie
    ("11:05", round(0.05 * 1.21 + VAST, 5)),     # 'Dynamisch'
    ("11:20", round(0.04 * 1.21 + VAST, 5)),     # 'Dynamisch + aFRR': gemiddelde zoals Balans het toont
])
def test_balans_kwartierprijs(hm, verwacht):
    assert float(rest(REST_SENSOR["BEVCC Balans kwartierprijs"], utc(hm))) == pytest.approx(verwacht)


def test_balans_kwartierprijs_volgt_energiebelasting():
    db = {"input_number.bevcc_energiebelasting": S(0.12), "input_number.bevcc_leverkosten": S(0.03)}
    got = rest(REST_SENSOR["BEVCC Balans kwartierprijs"], utc("10:05"), db=db)
    assert float(got) == pytest.approx(0.18 * 1.21 + 0.15)


@pytest.mark.parametrize("hm", ["11:32"])
def test_balans_kwartierprijs_unavailable_zonder_kwartier(hm):
    assert rest(REST_SENSOR["BEVCC Balans kwartierprijs"], utc(hm)) == "unavailable"


@pytest.mark.parametrize("hm, verwacht", [("10:20", "0.0337"), ("10:40", "unavailable"), ("10:50", "unavailable"),
                                          ("11:20", "0.02"), ("11:32", "unavailable")])
def test_balans_afrr_importprijs(hm, verwacht):
    assert rest(REST_SENSOR["BEVCC Balans aFRR-importprijs"], utc(hm)) == verwacht


@pytest.mark.parametrize("hm, verwacht", [
    ("10:05", "unavailable"),   # geen dynamische import
    ("10:50", "unavailable"),
    ("11:05", "0.05"),          # dynamische import
    ("11:20", "0.06"),          # dynamisch + aFRR: alleen het dynamische deel
    ("11:32", "0.06"),          # nieuw kwartier nog niet gemeld: overloop uit 11:15
    ("11:36", "unavailable"),   # overloop voorbij
])
def test_balans_dynamisch_prijs(hm, verwacht):
    assert rest(REST_SENSOR["BEVCC Balans dynamisch prijs"], utc(hm)) == verwacht


def test_balans_dynamisch_prijs_oude_api():
    # Antwoord zonder day-ahead-velden (vorm van oktober 2026): gewoon niet beschikbaar.
    import copy
    oud = copy.deepcopy(BALANS)
    oud.pop("dayAheadPlans")
    for p in oud["prices"]:
        p["values"].pop("day_ahead_import", None)
        p["values"].pop("day_ahead_afrr_import", None)
    assert rest(REST_SENSOR["BEVCC Balans dynamisch prijs"], utc("11:05"), oud) == "unavailable"
    assert float(rest(REST_SENSOR["BEVCC Balans kwartierprijs"], utc("11:05"), oud)) == pytest.approx(0.12 * 1.21 + VAST)


# --- TenneT-onbalansprijs (command_line) -------------------------------------

def _scraper_code():
    cmd = ha.CFG["command_line"][0]["sensor"]["command"]
    start = cmd.index('python3 -c "') + len('python3 -c "')
    return cmd[start:cmd.rindex('"')]


def scrape(html: str):
    out = subprocess.run([sys.executable, "-I", "-c", _scraper_code()], input=html,
                         capture_output=True, text=True, check=True, timeout=30)
    return json.loads(out.stdout)


def test_tenergy_scraper_leest_bovenste_regel():
    got = scrape((ha.FIXTURES / "tenergy_onbalans.html").read_text(encoding="utf-8"))
    assert got == {"afnemen": 214.9, "invoeden": 33.7, "tijd": "12:16"}


def test_tenergy_scraper_duizendtallen_en_negatief():
    html = (ha.FIXTURES / "tenergy_onbalans.html").read_text(encoding="utf-8")
    html = html.replace("<tr><td>1</td>", "<tr><td>x</td>", 1)  # eerste regel ongeldig maken
    html = html.replace(">12:16<", ">--<")
    assert scrape(html) == {"afnemen": 1234.56, "invoeden": -12.5, "tijd": "12:15"}


@pytest.mark.parametrize("html", ["", "<html>onderhoud</html>"])
def test_tenergy_scraper_leeg_bij_storing(html):
    assert scrape(html) == {}


def test_tennet_availability():
    item = ha.CFG["command_line"][0]["sensor"]
    assert ha.truthy(ha.render(item["availability"], strict=True, value_json={"afnemen": 214.9}))
    assert not ha.truthy(ha.render(item["availability"], strict=True, value_json={}))
    assert not ha.truthy(ha.render(item["availability"], strict=True))  # geen JSON
    assert ha.render(item["value_template"], value_json={"afnemen": 214.9}) == "214.9"


# --- Gecombineerde afnameprijs -----------------------------------------------

PRIJS = ha.find("sensor", "BEVCC afnameprijs")
BRON = ha.find("sensor", "BEVCC prijsbron")


def combo(sessie="off", afnemen=None, invoeden=None, afrr=None, balans=None, tennet_state=None, dyn=None):
    attrs = {k: v for k, v in (("afnemen", afnemen), ("invoeden", invoeden)) if v is not None}
    state = tennet_state or (afnemen if afnemen is not None else "unavailable")
    db = {
        "binary_sensor.bevcc_afrr_importsessie": S(sessie),
        "sensor.bevcc_tennet_onbalans": S(state, attrs),
        "sensor.bevcc_balans_afrr_importprijs": S("unavailable" if afrr is None else afrr),
        "sensor.bevcc_balans_kwartierprijs": S("unavailable" if balans is None else balans),
        "sensor.bevcc_balans_dynamisch_prijs": S("unavailable" if dyn is None else dyn),
        "input_number.bevcc_energiebelasting": S(0.11085),
        "input_number.bevcc_leverkosten": S(0.02),
    }
    bron = ha.render(BRON["state"], db)
    if not ha.truthy(ha.render(PRIJS["availability"], db)):
        return "unavailable", None, bron
    return ha.render(PRIJS["state"], db), ha.render(PRIJS["attributes"]["kaal"], db), bron


def test_prijs_zonder_sessie_tennet_afnemen():
    assert combo(afnemen=214.9, invoeden=33.7) == ("0.39088", "0.2149", "onbalans (TenneT afnemen)")


def test_prijs_sessie_tennet_invoeden():
    assert combo("on", afnemen=214.9, invoeden=33.7, afrr=0.0337) == ("0.17163", "0.0337", "aFRR-import (afregelprijs)")


def test_prijs_sessie_tennet_weg_balans_afrr():
    assert combo("on", afrr=0.0337) == ("0.17163", "0.0337", "aFRR-import (Balans)")


def test_prijs_tennet_weg_balans_kwartier():
    assert combo(balans=0.49385) == ("0.49385", "None", "Balans kwartierprijs")


def test_prijs_balans_api_weg_tennet_afnemen():
    assert combo("unavailable", afnemen=214.9, invoeden=33.7) == ("0.39088", "0.2149", "onbalans (TenneT afnemen)")


def test_prijs_alles_weg():
    assert combo() == ("unavailable", None, "onbekend")


def test_prijs_tennet_unavailable_met_oude_attributen():
    # Een unavailable entiteit mag geen (verouderde) prijs leveren.
    assert combo(afnemen=214.9, invoeden=33.7, tennet_state="unavailable", balans=0.3)[2] == "Balans kwartierprijs"


def test_afnameprijs_negeert_dynamisch():
    # De afnameprijs (pauze, dashboard) gebruikt de dynamische prijs nooit.
    assert combo(dyn=0.05, afnemen=214.9, invoeden=33.7) == ("0.39088", "0.2149", "onbalans (TenneT afnemen)")
    # 3 nov 13:30: dynamisch 0,22437 + aFRR 0,16888 -> aFRR-prijs, zoals in 1.2
    assert combo("on", dyn=0.22437, invoeden=168.88, afnemen=239.23) == ("0.33519", "0.16888", "aFRR-import (afregelprijs)")
    assert combo(dyn=0.05)[0] == "unavailable"


BOOST = ha.find("sensor", "BEVCC boostprijs")


def boostprijs(sessie="off", dyn=None, afname=None, prijsbron="onbalans (TenneT afnemen)"):
    db = {
        "binary_sensor.bevcc_afrr_importsessie": S(sessie),
        "sensor.bevcc_balans_dynamisch_prijs": S("unavailable" if dyn is None else dyn),
        "sensor.bevcc_afnameprijs": S("unavailable" if afname is None else afname),
        "sensor.bevcc_prijsbron": S(prijsbron),
        "input_number.bevcc_energiebelasting": S(0.11085),
        "input_number.bevcc_leverkosten": S(0.02),
    }
    if not ha.truthy(ha.render(BOOST["availability"], db)):
        return "unavailable", None
    return ha.render(BOOST["state"], db), ha.render(BOOST["attributes"]["bron"], db)


def test_boostprijs():
    # alleen dynamisch: de dynamische prijs
    assert boostprijs(dyn=0.05, afname=0.39088) == ("0.19135", "dynamisch (day-ahead)")
    assert boostprijs(dyn=0.05) == ("0.19135", "dynamisch (day-ahead)")
    # dynamisch + aFRR: de aFRR-prijs (afnameprijs), niet de dynamische
    assert boostprijs("on", dyn=0.22437, afname=0.33519, prijsbron="aFRR-import (afregelprijs)") == \
        ("0.33519", "aFRR-import (afregelprijs)")
    # geen dynamisch: de afnameprijs
    assert boostprijs(afname=0.25) == ("0.25", "onbalans (TenneT afnemen)")
    assert boostprijs() == ("unavailable", None)


def test_prijspiek_waarde():
    assert combo(afnemen=4168.1, invoeden=4168.1)[0] == "5.17425"


# --- Versiecontrole ----------------------------------------------------------

UPDATE = ha.find("binary_sensor", "BEVCC update beschikbaar")


def update(laatste, geinstalleerd="1.0.0", bekend=None):
    """(staat, attribuut laatste_versie) van binary_sensor.bevcc_update_beschikbaar."""
    db = {"sensor.bevcc_laatste_versie": S(laatste), "sensor.bevcc_versie": S(geinstalleerd)}
    this = S("off", {} if bekend is None else {"laatste_versie": bekend})
    staat = ha.truthy(ha.render(UPDATE["state"], db, this=this))
    return staat, ha.render(UPDATE["attributes"]["laatste_versie"], db, this=this)


@pytest.mark.parametrize("laatste, verwacht", [
    ("1.0.0", False), ("1.0.1", True), ("1.10.0", True), ("0.9.9", False),
    ("2.0.0-beta", True), ("unavailable", False), ("unknown", False),
])
def test_update_beschikbaar(laatste, verwacht):
    assert update(laatste)[0] is verwacht


def test_update_verdwijnt_na_bijwerken():
    assert update("1.1.0", "1.0.0") == (True, "1.1.0")
    assert update("1.1.0", "1.1.0") == (False, "1.1.0")


def test_update_blijft_bij_github_storing():
    # GitHub even onbereikbaar: laatst bekende release blijft gelden
    assert update("unavailable", "1.0.0", bekend="1.1.0") == (True, "1.1.0")
    assert update("unavailable", "1.1.0", bekend="1.1.0") == (False, "1.1.0")


def test_update_nog_nieuwere_release():
    assert update("1.2.0", "1.0.0", bekend="1.1.0") == (True, "1.2.0")


def test_laatste_versie_zonder_v():
    item = ha.rest_resource("api.github.com")["sensor"][0]
    assert ha.render(item["value_template"], value_json={"tag_name": "v1.2.3"}) == "1.2.3"
    assert not ha.truthy(ha.render(item["availability"], strict=True, value_json={"message": "Not Found"}))
