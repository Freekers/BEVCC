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
        "sensor.bevcc_balans_dynamisch_prijs": S(kw.get("dyn", "unavailable")),
        # export
        "binary_sensor.bevcc_afrr_exportsessie": S(kw.get("exportsessie", "off")),
        "binary_sensor.bevcc_ems_export": S(kw.get("ems_export", "off")),
        "sensor.bevcc_exportprijs": S(kw.get("exportprijs", "unavailable")),
        "input_number.bevcc_boost_export_onder": S(kw.get("export_grens", 0)),
        "input_boolean.bevcc_boost_export_negeer_ondergrens": S(kw.get("negeer", "off")),
        "input_boolean.bevcc_boost_import": S(kw.get("boost_import", "on")),
        "input_boolean.bevcc_boost_export": S(kw.get("boost_export", "on")),
        # laadstroomregeling
        "input_boolean.bevcc_laadstroom_regelen": S(kw.get("regelen", "off")),
        f"select.{lp}_min_current": S(kw.get("min_stroom", 6)),
        f"sensor.{lp}_phases_active": S(kw.get("fasen_actief", 3)),
        f"select.{lp}_phases": S(kw.get("fasen_ingesteld", 0)),
        "input_text.bevcc_te_herstellen_stroom": S(kw.get("bewaard_stroom", "")),
        "input_text.bevcc_ingestelde_stroom": S(kw.get("ingesteld_stroom", ""), age_min=kw.get("ingesteld_leeftijd", 10)),
    }
    if kw.get("max_stroom", 16) is not None:
        db[f"select.{lp}_max_current"] = S(kw.get("max_stroom", 16), {"options": [str(i) for i in range(6, 65)]},
                                           age_min=kw.get("stroom_leeftijd", 10))
    # Boostprijs uit de afnameprijs en de dynamische prijs (sectie 3).
    db["sensor.bevcc_boostprijs"] = S(ha.render(ha.find("sensor", "BEVCC boostprijs")["state"], db))
    # Sectie 2: de koppeling rendert de bevcc-entiteiten uit de EVCC-entiteiten.
    for section, name, eid in [
        ("sensor", "BEVCC net vermogen", "sensor.bevcc_net_vermogen"),
        ("sensor", "BEVCC thuisaccu vermogen", "sensor.bevcc_thuisaccu_vermogen"),
        ("sensor", "BEVCC laadvermogen", "sensor.bevcc_laadvermogen"),
        ("sensor", "BEVCC thuisaccu SoC", "sensor.bevcc_thuisaccu_soc"),
        ("binary_sensor", "BEVCC auto aangesloten", "binary_sensor.bevcc_auto_aangesloten"),
        ("binary_sensor", "BEVCC auto laadt", "binary_sensor.bevcc_auto_laadt"),
        ("sensor", "BEVCC min. laadstroom", "sensor.bevcc_min_laadstroom"),
        ("sensor", "BEVCC laadfasen", "sensor.bevcc_laadfasen"),
    ]:
        item = ha.find(section, name)
        if "availability" in item and not ha.truthy(ha.render(item["availability"], db)):
            db[eid] = S("unavailable")
        else:
            state = ha.render(item["state"], db)
            db[eid] = S(("on" if ha.truthy(state) else "off") if section == "binary_sensor" else state)
    stroom = ha.find("select", "BEVCC EVCC max. laadstroom")
    if ha.truthy(ha.render(stroom["availability"], db)):
        db["select.bevcc_evcc_max_laadstroom"] = S(ha.render(stroom["state"], db),
                                                   {"options": ha.native(ha.render(stroom["options"], db))},
                                                   age_min=kw.get("stroom_leeftijd", 10))
    else:
        db["select.bevcc_evcc_max_laadstroom"] = S("unavailable")
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
    (dict(IMPORT, sessie="on", ems="on", boost_import="off"), "off", 60, False),  # boost uit
    (dict(net=12500, accu=-11300, kaal=-1000, sessie="on", boost_import="off"), "off", 60, False),  # uit = uit
    (dict(net=12500, accu=-11300, kaal=-1000, sessie="on", boost_import="off"), "on", 60, False),   # uitgezet: stoppen
    # negatieve grens: alleen boosten als je betaald krijgt om af te nemen. All-in onder
    # -0,05 = kaal onder ongeveer -149 EUR/MWh (onbalans, afregelen)
    (dict(net=12500, accu=-11300, kaal=-1000, sessie="on", grens=-0.05), "off", 60, True),   # -1,079 all-in
    (dict(net=12500, accu=-11300, kaal=-150, sessie="on", grens=-0.05), "off", 60, True),    # -0,0507
    (dict(net=12500, accu=-11300, kaal=-140, sessie="on", grens=-0.05), "off", 60, False),   # -0,0386
    (dict(net=12500, accu=-11300, kaal=-100, sessie="on", grens=-0.05), "off", 60, False),   # +0,0099
    (dict(IMPORT, sessie="on", grens=-0.05), "off", 60, False),                               # 0,195
    (dict(net=12500, accu=-11300, kaal=-140, sessie="on", grens=-0.05), "on", 60, True),     # door: < grens + 0,02
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


AD = "aFRR + dynamisch"
# dynamisch importplan van ~10 kW; dynamische prijs 0,04 kaal (boostprijs 0,179), Afnemen 0,12 (0,276)
DYN = dict(net=10200, accu=-9100, kaal=120, dyn=0.04)


@pytest.mark.parametrize("kw, this, verwacht", [
    (dict(DYN, boost_bij=AD), "off", True),                       # dynamisch: direct
    (dict(DYN, boost_bij=A), "off", False),                       # alleen aFRR: niet
    (dict(DYN), "off", True),                                     # aFRR + onbalans: direct (geen 90 s)
    (dict(DYN, boost_bij=AD, dyn="unavailable", ems="on"), "off", False),  # onbalans-import telt niet
    (dict(DYN, boost_bij=AD), "on", True),
    (dict(DYN, boost_bij=AD, dyn="unavailable"), "on", False),    # dynamisch voorbij -> stoppen
    (dict(DYN, boost_bij=AD, dyn="unavailable", sessie="on", kaal=40), "on", True),  # aFRR loopt nog
    (dict(DYN, boost_bij=A, sessie="on", kaal=40), "on", True),
    # dynamisch + aFRR: de aFRR-prijs beslist, ook als de dynamische prijs hoger is (5 nov)
    (dict(DYN, boost_bij=A, sessie="on", kaal=30, dyn=0.20), "off", True),
    (dict(DYN, boost_bij=AD, sessie="on", kaal=30, dyn=0.20), "off", True),
    # alleen dynamisch, maar te duur: geen boost, ook al is Afnemen goedkoop
    (dict(DYN, boost_bij=AD, kaal=30, dyn=0.20), "off", False),
])
def test_boost_bij_dynamisch(kw, this, verwacht):
    assert bs(GI, base(**kw), this) is verwacht


def test_goedkope_import_prijs_onbekend():
    db = base(**IMPORT, sessie="on")
    db["sensor.bevcc_afnameprijs"] = S("unavailable")
    db["sensor.bevcc_boostprijs"] = S(ha.render(ha.find("sensor", "BEVCC boostprijs")["state"], db))
    assert db["sensor.bevcc_boostprijs"].state == "unavailable"
    assert not bs(GI, db)


def test_prijspiek_negeert_dynamisch():
    # 5 nov 11:15: dynamisch 0,202 (0,376 all-in), aFRR 0,145 (0,306): geen pauze
    assert not bs("BEVCC prijspiek", base(kaal=145, dyn=0.20239, sessie="on"))


def test_prijspiek_met_hysterese():
    assert bs("BEVCC prijspiek", base(kaal=300))
    assert not bs("BEVCC prijspiek", base(kaal=170))           # 0,336 < 0,35
    assert bs("BEVCC prijspiek", base(kaal=170), "on")         # 0,336 >= 0,33: blijft aan
    assert not bs("BEVCC prijspiek", base(kaal=150), "on")     # 0,312 < 0,33


# --- Laadstroom: koppeling -----------------------------------------------------

def test_koppeling_max_laadstroom():
    db = base(max_stroom=16)
    assert db["select.bevcc_evcc_max_laadstroom"].state == "16"
    assert db["select.bevcc_evcc_max_laadstroom"].attributes["options"][0] == "6"
    action = ha.find("select", "BEVCC EVCC max. laadstroom")["select_option"][0]
    assert ha.render(action["target"]["entity_id"], db) == "select.evcc_alfen_max_current"
    assert base(max_stroom=None)["select.bevcc_evcc_max_laadstroom"].state == "unavailable"


@pytest.mark.parametrize("actief, ingesteld, verwacht", [
    (3, 0, "3"), (1, 0, "1"), (2, 3, "2"),
    (0, 1, "1"),            # laadt niet: ingestelde fasen
    (0, 0, "3"),            # automatisch: 3
    ("unavailable", 3, "3"),
])
def test_koppeling_laadfasen(actief, ingesteld, verwacht):
    assert base(fasen_actief=actief, fasen_ingesteld=ingesteld)["sensor.bevcc_laadfasen"].state == verwacht


def test_koppeling_min_laadstroom():
    assert base(min_stroom=6)["sensor.bevcc_min_laadstroom"].state == "6.0"
    assert base(min_stroom="unavailable")["sensor.bevcc_min_laadstroom"].state == "unavailable"


# --- Boost bij export ----------------------------------------------------------

GE = "BEVCC goedkope export"
# EMS levert 8 kW terug uit de thuisaccu (huis 0,4 kW), exportprijs € 0,36 all-in, grens € 0,40
EXPORT = dict(net=-8000, accu=8400, exportprijs=0.36, export_grens=0.40)


def test_ems_export():
    assert bs("BEVCC EMS-export", base(net=-8000, accu=8400))
    assert not bs("BEVCC EMS-export", base(net=-3000, accu=-200))   # zonne-energie, accu laadt
    assert not bs("BEVCC EMS-export", base(net=-1500, accu=1900))   # minder dan 2 kW
    # buiten de handel dekt het EMS de auto uit de thuisaccu: geen teruglevering
    assert not bs("BEVCC EMS-export", base(net=30, accu=10500, auto_kw=10))


@pytest.mark.parametrize("kw, this, leeftijd, verwacht", [
    (dict(EXPORT, exportsessie="on"), "off", 60, True),              # aFRR-exportsessie: direct
    (dict(EXPORT), "off", 60, False),                                # geen sessie, < 90 s
    (dict(EXPORT, ems_export="on"), "off", 60, True),                # teruglevering >= 90 s
    (dict(EXPORT, exportsessie="on", boost_export="off"), "off", 60, False),  # uit
    # negatieve grens: alleen zelf gebruiken als het EMS zou moeten betalen om terug te leveren
    (dict(EXPORT, exportsessie="on", exportprijs=-0.10, export_grens=-0.05), "off", 60, True),
    (dict(EXPORT, exportsessie="on", export_grens=-0.05), "off", 60, False),
    (dict(EXPORT, exportsessie="on", exportprijs=0.41), "off", 60, False),
    (dict(EXPORT, exportsessie="on", exportprijs=0.40), "off", 60, True),    # op de grens
    (dict(EXPORT, exportsessie="on", exportprijs="unavailable"), "off", 60, False),
    (dict(EXPORT, exportsessie="on", soc=40), "off", 60, False),    # onder de ondergrens
    (dict(EXPORT, exportsessie="on", soc=40, negeer="on"), "off", 60, True),
    (dict(EXPORT, exportsessie="on", soc="unavailable", negeer="on"), "off", 60, True),
    (dict(EXPORT, exportsessie="on", accu=300), "off", 60, False),  # niet uit de thuisaccu
    (dict(EXPORT, exportsessie="on", net=-1500, accu=1900), "off", 60, False),  # < 2 kW
    (dict(EXPORT, exportsessie="on"), "off", 4, False),             # 5 min rust
    # buiten de handel dekt het EMS de laadende auto (Smart) uit de thuisaccu: net ~0,
    # geen teruglevering, dus geen start (ook niet met een aFRR-exportsessie)
    (dict(net=50, accu=4700, auto_kw=4.14, exportprijs=0.36, export_grens=0.40, exportsessie="on"), "off", 60, False),
    (dict(net=-1900, accu=6500, auto_kw=4.14, exportprijs=0.36, export_grens=0.40, exportsessie="on"), "off", 60, False),
    (dict(net=-2100, accu=6700, auto_kw=4.14, exportprijs=0.36, export_grens=0.40, exportsessie="on"), "off", 60, True),
    # doorgaan. Teruglevering 8 kW, omvormer niet vol: auto 10 kW extra uit de thuisaccu
    (dict(net=-8000, accu=18400, auto_kw=10, exportprijs=0.41, export_grens=0.40), "on", 60, True),
    (dict(net=-8000, accu=18400, auto_kw=10, exportprijs=0.43, export_grens=0.40), "on", 60, False),
    # omvormer vol (12 kW), huis 0,5 kW, auto 10 kW: nog 1,5 kW teruglevering -> door
    (dict(net=-1500, accu=12000, auto_kw=10, exportprijs=0.36, export_grens=0.40), "on", 60, True),
    (dict(net=-300, accu=12000, auto_kw=11.2, exportprijs=0.36, export_grens=0.40), "on", 60, True),
    # auto en huis vragen de hele omvormer (rest via de bypass van het net): niet meer
    # te onderscheiden van het EMS dat de auto dekt -> stoppen (na 2 min)
    (dict(net=500, accu=12000, auto_kw=11.5, exportprijs=0.36, export_grens=0.40), "on", 60, False),
    (dict(net=-150, accu=11500, auto_kw=11, exportprijs=0.36, export_grens=0.40), "on", 60, False),
    # EMS stopte met terugleveren en dekt de auto: net ~0 -> stoppen
    (dict(net=20, accu=10500, auto_kw=10, exportprijs=0.36, export_grens=0.40), "on", 60, False),
    (dict(EXPORT, soc=48.5), "on", 60, True),
    (dict(EXPORT, soc=47), "on", 60, False),
    (dict(EXPORT, soc=10, negeer="on"), "on", 60, True),
    (dict(EXPORT, boost_export="off"), "on", 60, False),             # uitgezet tijdens de boost
])
def test_goedkope_export(kw, this, leeftijd, verwacht):
    assert bs(GE, base(**kw), this, leeftijd) is verwacht


# --- Boost bij import met laadstroomregeling -----------------------------------

@pytest.mark.parametrize("kw, this, verwacht", [
    # import 12,5 kW: de thuisaccu krijgt 11,3 kW, ruim boven 6 A x 3 x 230 V
    (dict(IMPORT, sessie="on", regelen="on"), "off", True),
    # import 5 kW, huis 1,5 kW: 3,5 kW naar de thuisaccu < 4,14 kW minimaal laden
    (dict(net=5000, accu=-3500, kaal=52.8, sessie="on"), "off", True),
    (dict(net=5000, accu=-3500, kaal=52.8, sessie="on", regelen="on"), "off", False),
    (dict(net=5000, accu=-3500, kaal=52.8, sessie="on", regelen="on", fasen_actief=1), "off", True),
    (dict(net=5000, accu=-4500, kaal=52.8, sessie="on", regelen="on"), "off", True),
    # geen regelbaar laadpunt of handmatig overgenomen: geen extra voorwaarde
    (dict(net=5000, accu=-3500, kaal=52.8, sessie="on", regelen="on", max_stroom=None), "off", True),
    (dict(net=5000, accu=-3500, kaal=52.8, sessie="on", regelen="on", ingesteld_stroom="handmatig"), "off", True),
    # doorgaan: thuisaccu ontlaadt meer dan 1 kW -> stoppen (na 2 min)
    (dict(net=5000, accu=1500, auto_kw=6.5, kaal=52.8, sessie="on", regelen="on"), "on", False),
    (dict(net=5000, accu=800, auto_kw=5.8, kaal=52.8, sessie="on", regelen="on"), "on", True),
    (dict(net=5000, accu=-300, auto_kw=4.2, kaal=52.8, sessie="on", regelen="on"), "on", True),
    (dict(net=5000, accu=5500, auto_kw=10, kaal=52.8, sessie="on"), "on", True),   # zonder regeling: door
])
def test_goedkope_import_met_regeling(kw, this, verwacht):
    assert bs(GI, base(**kw), this) is verwacht


# --- Laadstroom: doel ----------------------------------------------------------

STROOM = ha.find("sensor", "BEVCC laadstroom doel")


def stroomdoel(goedkoop_import="on", goedkoop_export="off", **kw):
    kw.setdefault("status", "boost")
    kw.setdefault("regelen", "on")
    db = base(**kw)
    db["binary_sensor.bevcc_goedkope_import"] = S(goedkoop_import)
    db["binary_sensor.bevcc_goedkope_export"] = S(goedkoop_export)
    if not ha.truthy(ha.render(STROOM["availability"], db)):
        return "unavailable"
    return ha.render(STROOM["state"], db)


@pytest.mark.parametrize("kw, verwacht", [
    # import 5 kW, huis 0,5 kW, auto nog niet aan: 4,2 kW / 690 W per A -> 6 A
    (dict(net=5000, accu=-4500), "6"),
    (dict(net=5000, accu=-360, auto_kw=4.14), "6"),           # auto op 6 A: stabiel
    (dict(net=5000, accu=-2000, auto_kw=4.14), "8"),          # meer import: omhoog
    (dict(net=12500, accu=-11300), "15"),
    (dict(net=20000, accu=-19000), "16"),                     # niet boven de oorspronkelijke 16 A
    (dict(net=5000, accu=3000, auto_kw=4.14), "6"),           # niet onder de minimale stroom
    (dict(net=5000, accu=-2000, fasen_actief=1), "7"),        # 1 fase: 230 W per A
    # tijdens de regeling: de bewaarde oorspronkelijke stroom is het maximum
    (dict(net=20000, accu=-19000, max_stroom=9, bewaard_stroom="16"), "16"),
    (dict(net=20000, accu=-19000, max_stroom=9, bewaard_stroom="32"), "26"),   # omhoog: 300 W extra marge
    # hysterese: op 11 A laadt de thuisaccu 0,89 kW -> blijft 11 A (omhoog pas vanaf 1,29 kW)
    (dict(net=9000, accu=-890, auto_kw=7.59, max_stroom=11, bewaard_stroom="16"), "11"),
    (dict(net=9000, accu=-1300, auto_kw=7.59, max_stroom=11, bewaard_stroom="16"), "12"),
    (dict(net=9000, accu=-250, auto_kw=7.59, max_stroom=11, bewaard_stroom="16"), "10"),  # omlaag: direct
    (dict(net=5000, accu=-4500, min_stroom=8), "8"),
    # geen boost, regeling uit of geen meting: geen doel
    (dict(net=5000, accu=-4500, status="rust"), "None"),
    (dict(net=5000, accu=-4500, regelen="off"), "None"),
    (dict(net=5000, accu="unavailable"), "None"),
    (dict(net=5000, accu=-4500, max_stroom=None), "unavailable"),
    (dict(net=5000, accu=-4500, max_stroom=None, bewaard_stroom="16"), "6"),
])
def test_laadstroom_doel_import(kw, verwacht):
    assert stroomdoel(**kw) == verwacht


@pytest.mark.parametrize("kw, verwacht", [
    # teruglevering 8 kW, marge 0,3 kW: 7,7 kW -> 11 A
    (dict(net=-8000, accu=8400), "11"),
    # EMS houdt de teruglevering vast, omvormer niet vol: de auto mag alles
    (dict(net=-8000, accu=18400, auto_kw=10), "16"),
    # omvormer vol (12 kW), huis 0,5 kW, auto op 16 A = 11,04 kW: nog 0,46 kW
    # teruglevering, meer dan de 0,3 kW marge -> blijft 16 A
    (dict(net=-460, accu=12000, auto_kw=11.04), "16"),
    # huis 1 kW: de auto zou van het net nemen -> 15 A
    (dict(net=40, accu=12000, auto_kw=11.04), "15"),
])
def test_laadstroom_doel_export(kw, verwacht):
    assert stroomdoel(goedkoop_import="off", goedkoop_export="on", **kw) == verwacht


def test_laadstroom_doel_attributen():
    db = base(status="boost", regelen="on", fasen_actief=1, bewaard_stroom="16", max_stroom=9)
    db["binary_sensor.bevcc_goedkope_import"] = S("off")
    db["binary_sensor.bevcc_goedkope_export"] = S("on")
    attrs = STROOM["attributes"]
    assert ha.render(attrs["reden"], db) == "export"
    assert ha.render(attrs["fasen"], db) == "1"
    assert ha.render(attrs["oorspronkelijk"], db) == "16"


# --- Doel ----------------------------------------------------------------------

def doel(db, piek="off", goedkoop="off", piek_leeftijd=60, export="off"):
    db["binary_sensor.bevcc_prijspiek"] = S(piek, age_min=piek_leeftijd)
    db["binary_sensor.bevcc_goedkope_import"] = S(goedkoop)
    db["binary_sensor.bevcc_goedkope_export"] = S(export)
    return ha.render(ha.find("sensor", "BEVCC doel")["state"], db)


@pytest.mark.parametrize("args, verwacht, reden", [
    (dict(export="on"), "boost", "export"),
    (dict(goedkoop="on"), "boost", "import"),
    (dict(goedkoop="on", export="on"), "boost", "import"),
    (dict(piek="on", export="on"), "boost", "export"),        # auto laadt niet: geen pauze
    (dict(), "geen", ""),
])
def test_doel_export(args, verwacht, reden):
    db = base()
    assert doel(db, **args) == verwacht
    assert ha.render(ha.find("sensor", "BEVCC doel")["attributes"]["reden"], db) == reden


def test_doel_piek_gaat_voor_export():
    assert doel(base(laadt="on"), piek="on", export="on") == "pauze"


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


def test_boost_logboek_noemt_reden():
    db = base(status="rust")
    db["sensor.bevcc_doel"] = S("boost", {"reden": "export"})
    db["sensor.bevcc_exportprijs"] = S(0.1, {"bron": "onbalans (TenneT invoeden)"})
    v = variabelen(db)
    assert v["reden"] == "export"
    tekst = TAKKEN[NAMEN.index("E boost")]["sequence"][-1]["data"]["message"]
    uit = ha.render(tekst, db, **v)
    assert "goedkope teruglevering" in uit and "onbalans (TenneT invoeden)" in uit
    db["sensor.bevcc_doel"] = S("boost", {"reden": "import"})
    assert "goedkope EMS-import" in ha.render(tekst, db, **variabelen(db))


# --- Laadstroomregeling (automatisering) ---------------------------------------

REGELING = ha.automation("bevcc_laadstroomregeling")
R_VARS = REGELING["actions"][0]["variables"]
R_TAKKEN = REGELING["actions"][1]["choose"]
R_NAMEN = ["A handmatig", "B regelen", "C terugzetten", "D opruimen"]


def regeltak(db, doel_a):
    db["sensor.bevcc_laadstroom_doel"] = S(doel_a, {"reden": "import", "fasen": 3, "oorspronkelijk": 16})
    v = {}
    for k, t in R_VARS.items():
        v[k] = ha.native(ha.render(t, db, **v))
    for naam, br in zip(R_NAMEN, R_TAKKEN, strict=True):
        if all(ha.truthy(ha.render(c, db, **v)) for c in br["conditions"]):
            return naam, v
    return None, v


def test_regeling_aantal_takken():
    assert len(R_TAKKEN) == len(R_NAMEN)


@pytest.mark.parametrize("kw, doel_a, verwacht", [
    (dict(status="boost", regelen="on"), 6, "B regelen"),                  # eerste aanpassing
    (dict(status="boost", regelen="on"), 16, None),                        # al goed
    (dict(status="boost", regelen="on", max_stroom=6, bewaard_stroom="16", ingesteld_stroom="6"), 8, "B regelen"),
    (dict(status="boost", regelen="off"), 6, None),
    (dict(status="rust", regelen="on"), "unknown", None),
    # iemand anders zette 12 A terwijl BEVCC 6 A zette (meer dan 1 min geleden)
    (dict(status="boost", regelen="on", max_stroom=12, bewaard_stroom="16", ingesteld_stroom="6"), 6, "A handmatig"),
    # BEVCC zette net 6 A, EVCC heeft het nog niet overgenomen: nog geen conclusie
    (dict(status="boost", regelen="on", max_stroom=16, bewaard_stroom="16", ingesteld_stroom="6",
          ingesteld_leeftijd=0.3), 6, "B regelen"),
    (dict(status="boost", regelen="on", ingesteld_stroom="handmatig"), 6, None),   # opzij tot het einde
    (dict(status="boost", regelen="on", max_stroom=None), 6, None),                # EVCC weg
    # boost voorbij of regeling uit: terugzetten
    (dict(status="rust", max_stroom=6, bewaard_stroom="16", ingesteld_stroom="6"), "unknown", "C terugzetten"),
    (dict(status="pauze", max_stroom=6, bewaard_stroom="16", ingesteld_stroom="6"), "unknown", "C terugzetten"),
    (dict(status="boost", regelen="off", max_stroom=6, bewaard_stroom="16", ingesteld_stroom="6"), "unknown",
     "C terugzetten"),
    (dict(status="rust", max_stroom=None, bewaard_stroom="16", ingesteld_stroom="6"), "unknown", None),  # later
    (dict(status="rust", ingesteld_stroom="handmatig"), "unknown", "D opruimen"),
    (dict(status="rust"), "unknown", None),
])
def test_regeling_takken(kw, doel_a, verwacht):
    assert regeltak(base(**kw), doel_a)[0] == verwacht


def test_regeling_zet_hele_ampere():
    db = base(status="boost", regelen="on")
    naam, v = regeltak(db, 6)
    stappen = R_TAKKEN[R_NAMEN.index(naam)]["sequence"]
    bewaar = stappen[0]["then"][0]
    assert bewaar["target"]["entity_id"] == "input_text.bevcc_te_herstellen_stroom"
    assert ha.render(bewaar["data"]["value"], db, **v) == "16"
    assert ha.render(stappen[0]["then"][1]["data"]["message"], db, **v).startswith("Laadstroom geregeld (import)")
    assert ha.render(stappen[-1]["data"]["option"], db, **v) == "6"
    assert stappen[-1]["target"]["entity_id"] == "select.bevcc_evcc_max_laadstroom"


@pytest.mark.parametrize("kw, van_bevcc", [
    (dict(status="rust", max_stroom=6, bewaard_stroom="16", ingesteld_stroom="6"), True),
    # na de boost door iemand anders op 10 A gezet: laten staan
    (dict(status="rust", max_stroom=10, bewaard_stroom="16", ingesteld_stroom="6"), False),
])
def test_regeling_terugzetten_alleen_eigen_waarde(kw, van_bevcc):
    db = base(**kw)
    naam, v = regeltak(db, "unknown")
    assert naam == "C terugzetten"
    stappen = R_TAKKEN[R_NAMEN.index(naam)]["sequence"]
    v["van_bevcc"] = ha.native(ha.render(stappen[0]["variables"]["van_bevcc"], db, **v))
    assert v["van_bevcc"] is van_bevcc
    assert ha.truthy(ha.render(stappen[1]["if"][0]["value_template"], db, **v)) is van_bevcc
    assert ha.render(stappen[1]["then"][0]["data"]["option"], db, **v) == "16"
    log = ha.render(stappen[2]["then"][-1]["data"]["message"], db, **v)
    assert log == ("Maximale laadstroom terug naar 16 A" if van_bevcc
                   else "Maximale laadstroom niet teruggezet: staat op 10 A (handmatig gewijzigd)")


# --- Standaardwaarden en bijwerken naar 1.4 ------------------------------------

STANDAARD = ha.automation("bevcc_standaardwaarden")


@pytest.mark.parametrize("markering, versie, verwacht", [
    ("off", "unknown", True),   # nieuwe installatie
    ("off", "2", True),         # standaardwaarden herstellen
    ("on", "unknown", True),    # bijwerken van 1.3 of ouder
    ("on", "", True),
    ("on", "2", False),         # al bijgewerkt: niets doen
])
def test_standaardwaarden_wanneer(markering, versie, verwacht):
    db = {"input_boolean.bevcc_standaardwaarden": S(markering), "input_text.bevcc_instellingen_versie": S(versie)}
    assert ha.truthy(ha.render(STANDAARD["conditions"][0], db)) is verwacht


@pytest.mark.parametrize("boost_onder, export_onder, import_aan, export_aan", [
    (0.20, -2.0, True, False),     # 1.3 met boost aan; exportgrens nieuw (minimum)
    (-0.10, -2.0, True, False),    # 1.3: negatieve grens was ook 'aan' en blijft dat
    (-0.50, -2.0, False, False),   # 1.3: -0,50 was 'uit'
    (0.20, 0.40, True, True),      # testversie met een positieve exportgrens
    (0.20, 0.0, True, False),      # testversie: 0,00 was 'uit'
])
def test_bijwerken_naar_1_4(boost_onder, export_onder, import_aan, export_aan):
    db = {"input_number.bevcc_boost_onder": S(boost_onder), "input_number.bevcc_boost_export_onder": S(export_onder)}
    stappen = STANDAARD["actions"][0]["else"]
    v = {}
    for k, t in stappen[0]["variables"].items():
        v[k] = ha.native(ha.render(t, db, **v))
    assert (v["import_aan"], v["export_aan"]) == (import_aan, export_aan)
    assert ha.render(stappen[1]["action"], db, **v) == f"input_boolean.turn_{'on' if import_aan else 'off'}"
    assert ha.render(stappen[2]["action"], db, **v) == f"input_boolean.turn_{'on' if export_aan else 'off'}"
    # zonder boost: de grens krijgt de standaardwaarde, zodat 'aan' later meteen werkt
    assert ha.truthy(ha.render(stappen[3]["if"][0], db, **v)) is not import_aan
    assert ha.truthy(ha.render(stappen[4]["if"][0], db, **v)) is not export_aan
