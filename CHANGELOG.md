# Wijzigingen

Alle noemenswaardige wijzigingen in BEVCC. Versies volgen
[Semantic Versioning](https://semver.org/lang/nl/): een nieuwe hoofdversie
(2.0.0) betekent dat je iets moet aanpassen (bijvoorbeeld in secrets.yaml of je
dashboard); dat staat dan bij die versie.

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
