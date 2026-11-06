# Wijzigingen

Alle noemenswaardige wijzigingen in BEVCC. Versies volgen
[Semantic Versioning](https://semver.org/lang/nl/): een nieuwe hoofdversie
(2.0.0) betekent dat je iets moet aanpassen (bijvoorbeeld in secrets.yaml of je
dashboard); dat staat dan bij die versie.

## [1.3.0] - 2026-11-06

Ondersteuning voor dynamische (day-ahead) import van Balans, in het Balans-dashboard
*Dynamisch*.

### Toegevoegd

- `sensor.bevcc_balans_dynamisch_prijs`: de dynamische prijs van het lopende kwartier.
- `sensor.bevcc_boostprijs`: de prijs waarop BEVCC een boost beslist. In een kwartier met
  alleen dynamische import is dat de dynamische prijs, anders de afnameprijs.
- *Boost bij* heeft een nieuwe keuze *aFRR + dynamisch*: ook boosten tijdens dynamische
  import. *aFRR + onbalans* telt dynamische import nu ook mee en start daar direct. De
  standaard blijft *alleen aFRR*; je huidige keuze blijft staan.

### Gewijzigd

- `sensor.bevcc_balans_kwartierprijs` toont de prijs zoals het Balans-dashboard, ook
  *Dynamisch* en *Dynamisch + aFRR*.
- De afnameprijs (pauze en dashboard) gebruikt de dynamische prijs niet: dat volume is al
  ingekocht, dus een pauze bespaart daar niets op. In een kwartier met dynamisch + aFRR
  beslist de aFRR-prijs, zoals in 1.2.
- Het logboek noemt bij een boost de boostprijs en de bron.
- Tests en testgegevens bijgewerkt voor de nieuwe vorm van de Balans-API (`dayAheadPlans`,
  `missing_bid`, `checkedAt`).

## [1.2.1] - 2026-10-26

Na een boost wacht BEVCC 5 minuten voordat een nieuwe boost kan starten. De boost
verandert zelf de vermogens die BEVCC meet (het EMS reageert op de auto); zonder die rust
kan een boost steeds aan- en uitgaan.

## [1.2.0] - 2026-10-23

Boost stopt nu wanneer de import van het net onder de 'Boost min. EMS-import' − 1 kW daalt, maar nooit minder dan 0 kW.

## [1.1.0] - 2026-10-23

Update mechanisme verbeterd

## [1.0.0] - 2026-10-23

Eerste publieke versie.

### Toegevoegd

- Pauze (EVCC-modus Uit) bij een prijspiek, alleen terwijl de auto laadt, en daarna
  terug naar de modus die er stond (Smart of Snel).
- Boost (EVCC-modus Snel) tijdens goedkope EMS-import, alleen vanuit Smart, met een
  ondergrens voor de laadtoestand van de thuisaccu.
- Keuze 'Boost bij': alleen tijdens aFRR-importsessies of ook bij onbalans-import.
- Prijs per minuut: aFRR-importsessie uit de Balans-API gecombineerd met de live
  onbalansprijs (Tenergy), met terugval op de kwartierprijs van Balans.
- Ingebouwde TenneT-onbalansprijs (`sensor.bevcc_tennet_onbalans`).
- EVCC-koppeling via `bevcc_evcc_prefix` en `bevcc_evcc_laadpunt` in secrets.yaml.
- Instelbare energiebelasting en leverkosten; instellingen blijven bewaard bij updates.
- Meldingen: Balans-API onbereikbaar (verlopen cookie), modus niet overgenomen,
  terugzetten mislukt, nieuwe BEVCC-versie beschikbaar.
- Nederlandstalige dashboardkaart.
- Tests (pytest) en controle met yamllint en de configuratiecontrole van Home Assistant.
