"""Beslissingen: EVCC-koppeling, voorwaarden, doel en de takken van de automatisering."""
import pytest

import ha
from ha import S

VAST = 0.02 + 0.11085


def base(**kw):
    """Een volledige set toestanden. kw overschrijft de standaardsituatie."""
    kaal = kw.get("kaal", 80)  # EUR/MWh
    prefix, laadpunt = kw.get("prefix", "evcc"), kw.get("laadpunt", "alfen")
    lp = f"{prefix}_{laadpunt}"
    db = {
        "input_text.bevcc_evcc_prefix": S(prefix),
        "input_text.bevcc_evcc_laadpunt": S(laadpunt),
        f"sensor.{prefix}_grid_power": S(kw.get("net", 400), {"unit_of_measurement": kw.get("net_unit", "W")}),
        f"sensor.{prefix}_battery_power": S(kw.get("accu", 0), {"unit_of_measurement": "W"}),
        f"sensor.{lp}_charge_power": S(kw.get("auto_kw", 0.0), {"unit_of_measurement": "kW"}),
        f"sensor.{prefix}_battery_soc": S(kw.get("soc", 70), {"unit_of_measurement": "%"}),
        f"binary_sensor.{lp}_connected": S(kw.get("aangesloten", "on")),
        f"binary_sensor.{lp}_charging": S(kw.get("laadt", "off")),
        f"select.{lp}_mode": S(kw.get("modus", "smart"), {"options": kw.get("opties", ["off", "smart", "now"])},
                               age_min=kw.get("modus_leeftijd", 30)),
        "sensor.bevcc_afnameprijs": S(round(kaal / 1000 * 1.21 + VAST, 5)),
        "sensor.bevcc_prijsbron": S("onbalans (TenneT afnemen)"),
        "input_number.bevcc_pauze_boven": S(0.35),
        "input_number.bevcc_boost_onder": S(kw.get("grens", 0.20)),
        "input_number.bevcc_boost_min_import": S(kw.get("min_import", 2)),
        "input_number.bevcc_accu_ondergrens": S(50),
        "input_select.bevcc_boost_bij": S(kw.get("boost_bij", "aFRR + onbalans")),
        "input_select.bevcc_status": S(kw.get("status", "rust"), age_min=kw.get("status_leeftijd", 10)),
        "input_text.bevcc_te_herstellen_modus": S(kw.get("bewaard", "smart")),
        "input_boolean.bevcc_standaardwaarden": S(kw.get("standaard", "on")),
        "binary_sensor.bevcc_afrr_importsessie": S(kw.get("sessie", "off")),
        "binary_sensor.bevcc_ems_import": S(kw.get("ems", "off")),
    }
    # Sectie 2: de koppeling rendert de bevcc-entiteiten uit de EVCC-entiteiten.
    for section, name, eid in [
        ("sensor", "BEVCC net vermogen", "sensor.bevcc_net_vermogen"),
        ("sensor", "BEVCC thuisaccu vermogen", "sensor.bevcc_thuisaccu_vermogen"),
        ("sensor", "BEVCC laadvermogen", "sensor.bevcc_laadvermogen"),
        ("sensor", "BEVCC thuisaccu SoC", "sensor.bevcc_thuisaccu_soc"),
        ("binary_sensor", "BEVCC auto aangesloten", "binary_sensor.bevcc_auto_aangesloten"),
        ("binary_sensor", "BEVCC auto laadt", "binary_sensor.bevcc_auto_laadt"),
    ]:
        item = ha.find(section, name)
        if not ha.truthy(ha.render(item["availability"], db)):
            db[eid] = S("unavailable")
        else:
            state = ha.render(item["state"], db)
            db[eid] = S(("on" if ha.truthy(state) else "off") if section == "binary_sensor" else state)
    sel = ha.find("select", "BEVCC EVCC-modus")
    src = db.get(f"select.{lp}_mode")
    if ha.truthy(ha.render(sel["availability"], db)):
        db["select.bevcc_evcc_modus"] = S(ha.render(sel["state"], db),
                                          {"options": ha.native(ha.render(sel["options"], db))},
                                          age_min=kw.get("modus_leeftijd", 30))
        db["select.bevcc_evcc_modus"].last_changed = src.last_changed
    else:
        db["select.bevcc_evcc_modus"] = S("unavailable", age_min=kw.get("modus_leeftijd", 30))
    return db


def bs(name, db, this_state="off", this_age=60):
    item = ha.find("binary_sensor", name)
    return ha.truthy(ha.render(item["state"], db, this=S(this_state, age_min=this_age)))


# --- EVCC-koppeling -----------------------------------------------------------

def test_koppeling_omrekening_kw_naar_w():
    db = base(net=1.5, net_unit="kW", auto_kw=10.2)
    assert db["sensor.bevcc_net_vermogen"].state == "1500.0"
    assert db["sensor.bevcc_laadvermogen"].state == "10200.0"


def test_koppeling_ander_laadpunt():
    db = base(prefix="evcc2", laadpunt="garage", modus="now")
    assert db["select.bevcc_evcc_modus"].state == "now"
    assert db["binary_sensor.bevcc_auto_aangesloten"].state == "on"


def test_koppeling_verkeerd_laadpunt_unavailable():
    db = base()
    db["input_text.bevcc_evcc_laadpunt"] = S("bestaatniet")
    sel = ha.find("select", "BEVCC EVCC-modus")
    assert not ha.truthy(ha.render(sel["availability"], db))
    assert not ha.truthy(ha.render(ha.find("binary_sensor", "BEVCC auto laadt")["availability"], db))


def test_select_doorgeefluik_stuurt_juiste_entiteit():
    db = base(prefix="evcc", laadpunt="alfen")
    action = ha.find("select", "BEVCC EVCC-modus")["select_option"][0]
    assert action["action"] == "select.select_option"
    assert ha.render(action["target"]["entity_id"], db) == "select.evcc_alfen_mode"
    assert ha.render(action["data"]["option"], db, option="now") == "now"


# --- Voorwaarden ---------------------------------------------------------------

GI, EI = "BEVCC goedkope import", "BEVCC EMS-import"
IMPORT = dict(net=12500, accu=-11300, kaal=52.8)  # aFRR-import van 12 kW om 03:08


def test_ems_import():
    assert bs(EI, base(net=12500, accu=-11300))
    assert not bs(EI, base(net=15, accu=-2758))  # thuisaccu laadt op zonne-energie


@pytest.mark.parametrize("kw, this, leeftijd, verwacht", [
    (dict(IMPORT, sessie="on"), "off", 60, True),                    # sessie: direct
    (dict(IMPORT), "off", 60, False),                                # geen sessie, import < 90 s
    (dict(IMPORT, ems="on"), "off", 60, True),                       # geen sessie, import >= 90 s
    (dict(net=400, accu=300, kaal=52.8, sessie="on"), "off", 60, False),  # sessie, maar geen import
    (dict(net=12500, accu=-11300, kaal=65, sessie="on"), "off", 60, False),  # prijs 0,21
    (dict(IMPORT, sessie="on"), "off", 4, False),                    # 5 min rust na een boost
    (dict(IMPORT, sessie="on"), "off", 6, True),                     # rust voorbij
    (dict(IMPORT, sessie="on", ems="on", grens=-0.5), "off", 60, False),  # boost uit
    (dict(net=12500, accu=-11300, kaal=-1000, sessie="on", grens=-0.5), "off", 60, False),  # uit = uit
    (dict(net=12500, accu=-11300, kaal=-1000, sessie="on"), "off", 60, True),  # negatieve prijs
    (dict(IMPORT, sessie="on", soc=36), "off", 60, False),           # onder de ondergrens
    (dict(IMPORT, sessie="on", soc=50), "off", 60, True),            # op de ondergrens
    (dict(IMPORT, soc=48.5), "on", 60, True),                        # doorgaan: >= ondergrens - 2
    (dict(IMPORT, soc=47), "on", 60, False),                         # stoppen: < ondergrens - 2
    (dict(net=30, accu=10500, auto_kw=10, kaal=52.8), "on", 60, False),  # accu voedt de auto
    # doorgaan zolang netafname (met auto) > Boost min. EMS-import - 1 kW (minimaal 0)
    (dict(net=1500, accu=8000, auto_kw=10, kaal=52.8), "on", 60, True),             # min 2 -> grens 1 kW
    (dict(net=900, accu=9000, auto_kw=10, kaal=52.8), "on", 60, False),
    (dict(net=7500, accu=2000, auto_kw=10, kaal=52.8, min_import=8), "on", 60, True),  # min 8 -> grens 7 kW
    (dict(net=6500, accu=3000, auto_kw=10, kaal=52.8, min_import=8), "on", 60, False),
    (dict(net=200, accu=9500, auto_kw=10, kaal=52.8, min_import=0.5), "on", 60, True),  # min 0,5 -> grens 0
    (dict(net=-100, accu=9800, auto_kw=10, kaal=52.8, min_import=0.5), "on", 60, False),
    # EMS houdt het net op 5 kW, auto 10 kW: netafname zonder auto negatief, boost loopt door
    (dict(net=5000, accu=5500, auto_kw=10, kaal=52.8, sessie="on", boost_bij="alleen aFRR"), "on", 60, True),
])
def test_goedkope_import(kw, this, leeftijd, verwacht):
    assert bs(GI, base(**kw), this, leeftijd) is verwacht


A = "alleen aFRR"


@pytest.mark.parametrize("kw, this, verwacht", [
    (dict(IMPORT, sessie="on", boost_bij=A), "off", True),
    (dict(IMPORT, ems="on", boost_bij=A), "off", False),  # onbalans-import telt niet
    (dict(IMPORT, sessie="on", boost_bij=A), "on", True),
    (dict(IMPORT, boost_bij=A), "on", False),             # sessie voorbij -> stoppen
    (dict(IMPORT), "on", True),                           # aFRR + onbalans: doorgaan
])
def test_boost_bij(kw, this, verwacht):
    assert bs(GI, base(**kw), this) is verwacht


def test_goedkope_import_prijs_onbekend():
    db = base(**IMPORT, sessie="on")
    db["sensor.bevcc_afnameprijs"] = S("unavailable")
    assert not bs(GI, db)


def test_prijspiek_met_hysterese():
    assert bs("BEVCC prijspiek", base(kaal=300))
    assert not bs("BEVCC prijspiek", base(kaal=170))           # 0,336 < 0,35
    assert bs("BEVCC prijspiek", base(kaal=170), "on")         # 0,336 >= 0,33: blijft aan
    assert not bs("BEVCC prijspiek", base(kaal=150), "on")     # 0,312 < 0,33


# --- Doel ----------------------------------------------------------------------

def doel(db, piek="off", goedkoop="off", piek_leeftijd=60):
    db["binary_sensor.bevcc_prijspiek"] = S(piek, age_min=piek_leeftijd)
    db["binary_sensor.bevcc_goedkope_import"] = S(goedkoop)
    return ha.render(ha.find("sensor", "BEVCC doel")["state"], db)


@pytest.mark.parametrize("kw, args, verwacht", [
    (dict(laadt="on"), dict(piek="on"), "pauze"),
    (dict(), dict(piek="on"), "geen"),                          # aangesloten maar laadt niet
    (dict(status="pauze"), dict(piek="on"), "pauze"),
    (dict(status="pauze"), dict(piek="unavailable", piek_leeftijd=5), "pauze"),
    (dict(status="pauze"), dict(piek="unavailable", piek_leeftijd=20), "geen"),
    (dict(), dict(goedkoop="on"), "boost"),
    (dict(laadt="on"), dict(piek="on", goedkoop="on"), "pauze"),  # piek gaat voor
    (dict(aangesloten="off", laadt="on"), dict(piek="on"), "geen"),
    (dict(standaard="off", laadt="on"), dict(piek="on"), "geen"),  # nog geen standaardwaarden
])
def test_doel(kw, args, verwacht):
    assert doel(base(**kw), **args) == verwacht


# --- Automatisering ------------------------------------------------------------

AUTO = ha.automation("bevcc_prijssturing")
VARS = AUTO["actions"][0]["variables"]
TAKKEN = AUTO["actions"][1]["choose"]
NAMEN = ["A controle", "B1 herstel", "B2 handmatig", "C einde handmatig", "D pauze", "E boost", "F vrijgeven"]


def variabelen(db):
    v = {}
    for k, t in VARS.items():  # HA rendert variabelen op volgorde
        v[k] = ha.native(ha.render(t, db, **v))
    return v


def tak(db, d, trig="doel", from_state="off"):
    db["sensor.bevcc_doel"] = S(d)
    v = variabelen(db)
    trigger = {"id": trig, "from_state": S(from_state)}
    for naam, br in zip(NAMEN, TAKKEN, strict=True):
        ok = True
        for c in br["conditions"]:
            if isinstance(c, dict) and c.get("condition") == "trigger":
                ok &= trigger["id"] == c["id"]
            else:
                tpl = c if isinstance(c, str) else c["value_template"]
                ok &= ha.truthy(ha.render(tpl, db, trigger=trigger, **v))
        if ok:
            return naam
    return None


def test_aantal_takken():
    assert len(TAKKEN) == len(NAMEN)


@pytest.mark.parametrize("kw, d, trig, van, verwacht", [
    (dict(), "pauze", "doel", "off", "D pauze"),
    (dict(modus="now"), "pauze", "doel", "off", "D pauze"),
    (dict(modus="off"), "pauze", "doel", "off", None),
    (dict(), "boost", "doel", "off", "E boost"),
    (dict(modus="now"), "boost", "doel", "off", None),                       # alleen vanuit Smart
    (dict(status="pauze", modus="off"), "boost", "doel", "off", "E boost"),
    (dict(status="pauze", modus="off", bewaard="now"), "boost", "doel", "off", "F vrijgeven"),
    (dict(status="pauze", modus="off", modus_leeftijd=5), "geen", "doel", "off", "F vrijgeven"),
    (dict(status="boost", modus="now", modus_leeftijd=5), "geen", "doel", "off", "F vrijgeven"),
    (dict(status="boost", modus="now", modus_leeftijd=5), "pauze", "doel", "off", "D pauze"),
    (dict(status="pauze", modus="smart", modus_leeftijd=1), "pauze", "modus", "off", "B2 handmatig"),
    (dict(status="pauze", modus="smart", modus_leeftijd=1), "pauze", "modus", "unavailable", "B1 herstel"),
    (dict(status="pauze", status_leeftijd=1, modus="smart", modus_leeftijd=30), "pauze", "controle", "off", "A controle"),
    (dict(status="pauze", status_leeftijd=1, modus="off", modus_leeftijd=0.9), "pauze", "controle", "off", None),
    (dict(status="handmatig"), "geen", "doel", "off", "C einde handmatig"),
    (dict(status="handmatig"), "pauze", "doel", "off", None),
    (dict(), "geen", "tik", "off", None),
])
def test_takken(kw, d, trig, van, verwacht):
    assert tak(base(**kw), d, trig, van) == verwacht


def test_evcc_weg_geen_templatefout():
    db = base(status="pauze", modus="off")
    del db["select.bevcc_evcc_modus"]
    assert tak(db, "pauze", "controle") == "A controle"


@pytest.mark.parametrize("opties, verwacht", [
    (["off", "smart", "now"], "now"),
    (["off", "pv", "minpv", "now"], "now"),
    (["off", "smart", "fast"], "fast"),
    (None, "now"),
])
def test_snel_optie(opties, verwacht):
    assert variabelen(base(opties=opties))["snel"] == verwacht


def test_boost_verwacht_now():
    assert variabelen(base(status="boost"))["verwacht"] == "now"
