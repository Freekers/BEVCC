# BEVCC: Balans Energie EVCC Companion

Een Home Assistant-package dat [EVCC](https://evcc.io) laat meebewegen met de
onbalansprijs en de aFRR-sessies van je thuisbatterij bij Balans Energie:

- **Pauze** bij een prijspiek: laadt de auto en is de prijs te hoog, dan zet BEVCC
  EVCC op *Uit*.
- **Boost** bij goedkope import: laadt het Balans-EMS je thuisbatterij goedkoop uit
  het net, dan zet BEVCC EVCC op *Snel*, zodat de auto meelaadt.
- **Terugzetten**: daarna krijgt EVCC de modus terug die er stond.

EVCC blijft de baas over je laadpunt en de vermogensbegrenzing. BEVCC wisselt alleen de
modus, en alleen om prijsredenen.

> [!IMPORTANT]
> **BEVCC houdt geen rekening met een vertrektijd of een gewenste laadtoestand (SoC) van
> je auto.** Een pauze bij een prijspiek gaat ook door als er in EVCC een laadplan loopt;
> de auto kan dan op het geplande moment minder vol zijn dan je wilde. Moet je er
> absoluut zeker van zijn dat je auto op een bepaald moment een bepaalde laadtoestand
> heeft, dan is BEVCC misschien niets voor jou. Wil je dat maar af en toe, zet dan de
> automatisering *BEVCC prijssturing* zolang uit.

## Inhoud

- [Wat BEVCC doet](#wat-bevcc-doet)
- [Hoe BEVCC de prijs bepaalt](#hoe-bevcc-de-prijs-bepaalt)
- [Vereisten](#vereisten)
- [Installatie](#installatie)
- [Instellingen](#instellingen)
- [Updaten](#updaten)
- [Ontwerpkeuzes](#ontwerpkeuzes)
- [Entiteiten](#entiteiten)
- [Probleemoplossing](#probleemoplossing)
- [Bekende beperkingen](#bekende-beperkingen)
- [Ontwikkelen en testen](#ontwikkelen-en-testen)
- [Dankwoord](#dankwoord)
- [Licentie](#licentie)
- [Disclaimer](#disclaimer)

## Wat BEVCC doet

| Situatie | Voorwaarden | EVCC-modus | Daarna |
|---|---|---|---|
| **Pauze** | auto laadt, all-in afnameprijs boven *Pauze boven* (standaard € 0,35/kWh) | Smart of Snel → **Uit** | terug naar Smart of Snel als de prijs 2 minuten lang onder *Pauze boven* − € 0,02 ligt |
| **Boost** | het EMS laadt de thuisaccu uit het net, all-in prijs onder *Boost onder* (standaard € 0,20/kWh), thuisaccu op of boven de *ondergrens* (standaard 50 %) | Smart → **Snel** | terug naar Smart als de goedkope import voorbij is |
| **Rust** | geen van beide | ongewijzigd | – |

- Een prijspiek gaat altijd voor een boost.
- Pauzeren gebeurt vanuit Smart en Snel, boosten alleen vanuit Smart. Staat EVCC op
  *Uit*, dan blijft dat zo.
- Kies je zelf een andere modus tijdens een pauze of boost, dan stapt BEVCC opzij
  (status *handmatig*) tot die pauze of boost voorbij is.
- Alles wat BEVCC doet komt met de reden en de prijs in het logboek, en is te volgen op
  de dashboardkaart.

### Wanneer stopt een boost?

Een boost stopt (2 minuten vertraging tegen korte dips) zodra:

- de prijs op of boven *Boost onder* + € 0,02 komt, of
- het net minder dan 1 kW levert: het EMS importeert niet meer en de thuisaccu
  voedt de auto, of
- de thuisaccu onder de *ondergrens* − 2 % zakt, of
- bij *Boost bij* = *alleen aFRR*: de aFRR-importsessie eindigt.

Na een boost wacht BEVCC 10 minuten voordat een nieuwe boost kan starten.

## Hoe BEVCC de prijs bepaalt

Alle beslissingen gebruiken de **all-in afnameprijs per kWh**:

```text
all-in = kale prijs × 1,21 + leverkosten + energiebelasting
       = kale prijs × 1,21 + € 0,02     + € 0,11085        (2026, standaardwaarden)
```

De kale prijs komt per minuut uit deze bronnen, in deze volgorde:

| Situatie | Kale prijs | Bron in Home Assistant |
|---|---|---|
| aFRR-importsessie van jouw EMS | live onbalansprijs **Invoeden** (de afregelprijs) | `sensor.bevcc_tennet_onbalans`, attribuut `invoeden` |
| aFRR-importsessie, live prijs niet beschikbaar | aFRR-importprijs van Balans | `sensor.bevcc_balans_afrr_importprijs` |
| geen sessie | live onbalansprijs **Afnemen** | `sensor.bevcc_tennet_onbalans` |
| live prijs niet beschikbaar | all-in kwartierprijs van Balans | `sensor.bevcc_balans_kwartierprijs` |

Of er een aFRR-importsessie loopt, weet alleen Balans: dat leest BEVCC uit de
Balans-API (`binary_sensor.bevcc_afrr_importsessie`). De live onbalansprijzen per minuut
komen van de openbare pagina met actuele onbalansprijzen van
[Tenergy Services](https://services.tenergy.nl/public.aspx/actualimbalanceprices), op
basis van TenneT-gegevens.

**Voorbeeld.** *Afnemen* is 214,90 €/MWh = € 0,2149/kWh kaal. All-in:
0,2149 × 1,21 + 0,02 + 0,11085 = **€ 0,391/kWh**: boven € 0,35, dus pauze als de auto
laadt. Omgekeerd ligt de grens van € 0,35 all-in bij ongeveer 181 €/MWh kaal, en
€ 0,20 bij ongeveer 57 €/MWh. De dashboardkaart rekent dit voor je om.

Vaste kosten per dag of jaar (vastrecht, netbeheer, heffingskorting) tellen niet mee:
die betaal je ook als de auto niet laadt, dus ze veranderen de beslissing niet.

## Vereisten

- Een **Balans Energie**-contract met dynamische (onbalans)prijzen en een thuisbatterij
  die door het Balans-EMS wordt aangestuurd (aFRR). Zonder thuisbatterij werkt de
  pauze ook, maar dan heeft boost geen zin.
- **EVCC** met een laadpunt, gekoppeld aan Home Assistant via de HACS-integratie
  [ha-evcc van marq24](https://github.com/marq24/ha-evcc). BEVCC gebruikt van het
  laadpunt `select.<prefix>_<laadpunt>_mode`, `binary_sensor.<prefix>_<laadpunt>_connected`,
  `binary_sensor.<prefix>_<laadpunt>_charging` en `sensor.<prefix>_<laadpunt>_charge_power`,
  en van de site `sensor.<prefix>_grid_power`, `sensor.<prefix>_battery_power` en
  `sensor.<prefix>_battery_soc`.
- **Home Assistant 2025.1 of nieuwer** (Home Assistant OS of Container: `curl` en
  `python3` zijn daar aanwezig).
- Home Assistant moet `dashboard.balansenergie.nl`, `services.tenergy.nl` en
  `api.github.com` kunnen bereiken.
- Aanbevolen: een **circuit met maximale stroom** (hoofdzekering) in EVCC. In de modus
  Snel laadt de auto op vol vermogen terwijl de thuisaccu ook laadt; EVCC's
  vermogensbegrenzing blijft daarbij gewoon gelden, BEVCC regelt geen stroom.

## Installatie

1. **Prijsgrenzen in EVCC uitzetten.** Zet in EVCC alle tarief- en prijsgrenzen uit,
   zoals de prijs- of kostenlimiet voor slim laden bij je laadpunt of voertuig, en een
   prijsgrens voor het laden van de thuisbatterij uit het net. Anders beslissen EVCC en
   BEVCC allebei om prijsredenen over hetzelfde laden, elk met een andere prijs en
   vertraging, en wordt het gedrag onvoorspelbaar (zie
   [ontwerpkeuzes](#modus-wisselen-in-plaats-van-evccs-kostenlimiet)). Je thuisbatterij
   wordt al door het Balans-EMS aangestuurd.

2. **Packages aanzetten.** Zet in `/config/configuration.yaml` (als dat er nog niet
   staat):

   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

3. **Package plaatsen.** Download [`packages/bevcc.yaml`](packages/bevcc.yaml) en zet het
   in `/config/packages/bevcc.yaml` (bijvoorbeeld met de add-on *File editor* of
   *Studio Code Server*, of via Samba). Pas het bestand zelf niet aan: dan kun je het bij
   een update gewoon vervangen.

4. **secrets.yaml aanvullen.** Zet deze drie regels in `/config/secrets.yaml` (zie ook
   [`secrets.example.yaml`](secrets.example.yaml)):

   ```yaml
   bevcc_balans_cookie: "…de hele Cookie-header…"
   bevcc_evcc_prefix: "evcc"       # zoals in sensor.evcc_grid_power
   bevcc_evcc_laadpunt: "alfen"    # zoals in select.evcc_alfen_mode
   ```

   Hoe je de cookie vindt staat in [docs/cookie.md](docs/cookie.md). Prefix en laadpunt
   lees je af aan de entiteit-ID van de EVCC-modus (Instellingen → Apparaten en
   diensten → Entiteiten, zoek op `_mode`).

5. **Controleren en herstarten.** Ontwikkelhulpmiddelen → YAML → *Configuratie
   controleren*, daarna Home Assistant herstarten. Bij de eerste start zet BEVCC de
   standaardwaarden voor de instellingen.

6. **Dashboard.** Bewerk een dashboard → *Kaart toevoegen* → *Handmatig* en plak de
   inhoud van [`dashboard/bevcc_dashboard.yaml`](dashboard/bevcc_dashboard.yaml).

7. **Controleren.** Op de kaart hoort een prijs te staan, en geen rode balken. Na een
   minuut is `binary_sensor.bevcc_afrr_importsessie` *aan* of *uit*, niet *niet
   beschikbaar*.

## Instellingen

Alle instellingen staan op de dashboardkaart. Ze blijven bewaard bij herstarts en
updates.

| Instelling | Entiteit | Standaard | Betekenis |
|---|---|---|---|
| Pauze boven | `input_number.bevcc_pauze_boven` | € 0,35 | All-in prijs waarboven het laden pauzeert. |
| Boost onder | `input_number.bevcc_boost_onder` | € 0,20 | All-in prijs waaronder een boost mag. Op het minimum (− € 0,50) staat boost uit. |
| Boost bij | `input_select.bevcc_boost_bij` | alleen aFRR | *alleen aFRR*: alleen tijdens een aFRR-importsessie. *aFRR + onbalans*: ook bij andere EMS-import. Zie [ontwerpkeuzes](#alleen-afrr-of-ook-onbalans). |
| Boost min. EMS-import | `input_number.bevcc_boost_min_import` | 2 kW | Netafname (zonder de auto) die nodig is om een boost te starten. |
| Accu-ondergrens | `input_number.bevcc_accu_ondergrens` | 50 % | Geen boost onder deze laadtoestand; een lopende boost stopt 2 % eronder. |
| Energiebelasting | `input_number.bevcc_energiebelasting` | € 0,11085 | Per kWh incl. btw, 2026, eerste schijf. **Elk jaar per 1 januari bijwerken.** |
| Leverkosten | `input_number.bevcc_leverkosten` | € 0,02 | Opslag van Balans per kWh incl. btw. |

Zet je `input_boolean.bevcc_standaardwaarden` uit, dan zet BEVCC alle instellingen terug
op de standaardwaarden.

## Updaten

1. Klik op GitHub op **Watch → Custom → Releases** om een bericht te krijgen bij een nieuwe
   versie. Home Assistant meldt het ook zelf: BEVCC kijkt elke 6 uur naar de nieuwste
   release en maakt dan een melding en een balk op de dashboardkaart.
2. Lees bij de release (of in de [CHANGELOG](CHANGELOG.md)) wat er verandert. Een nieuwe
   hoofdversie (2.0.0) vraagt soms een aanpassing, bijvoorbeeld in `secrets.yaml`; dat
   staat er dan bij.
3. Vervang `/config/packages/bevcc.yaml` door de nieuwe versie, controleer de
   configuratie en herstart Home Assistant. Vervang zo nodig ook de dashboardkaart.

Je instellingen blijven staan: ze zitten in Home Assistant, niet in het bestand.

### Waarom niet via HACS?

HACS kan integraties, dashboardkaarten, thema's, AppDaemon- en Python-scripts en
templates installeren, maar geen YAML-packages. BEVCC als package houdt alles leesbaar en
aanpasbaar in gewone Home Assistant-YAML, zonder Python-code die bij elke Home
Assistant-versie moet meegroeien.

## Ontwerpkeuzes

### Modus wisselen in plaats van EVCC's kostenlimiet

EVCC heeft een eigen prijsgrens voor slim laden, maar die reageert met enkele minuten
vertraging en kent alleen één tariefreeks. EVCC weet niet of jouw EMS op dit moment een
aFRR-sessie heeft, en welke prijs daar dan voor geldt. Bij onbalansprijzen, die binnen
een kwartier van een paar cent naar enkele euro's kunnen springen, is snel en op de
juiste prijs reageren juist de kern. BEVCC zet daarom zelf de modus en laat de
vermogensbegrenzing aan EVCC.

Zet EVCC's eigen prijsgrenzen uit ([Installatie](#installatie), stap 1). Laten
EVCC en BEVCC allebei het laden starten en stoppen om prijsredenen, dan zitten ze elkaar
in de weg: BEVCC pauzeert bijvoorbeeld alleen terwijl de auto laadt, en een boost start
alleen vanuit Smart.

Laadplannen in EVCC blijven werken zolang BEVCC niet pauzeert of boost, maar BEVCC houdt
er geen rekening mee: een pauze gaat ook door als het plan daardoor niet gehaald wordt.

### Live minuutprijs in plaats van de kwartierprijs

Balans werkt de prijs van het lopende kwartier maar één keer bij, een paar minuten na
de start. Wie daarop wacht, loopt altijd achter: een prijspiek is dan al minuten bezig.
De onbalansprijs per minuut (met ongeveer 2 minuten vertraging gepubliceerd) is veel
eerder. De kwartierprijs van Balans is daarom alleen terugval en vergelijking.

### De aFRR-sessie uit de Balans-API, niet uit het prijsverschil

Je zou een aFRR-sessie kunnen afleiden uit een groot verschil tussen de import- en
exportprijs in het Balans-dashboard. Dat gaat vaak mis: in een steekproef van 342
kwartieren klopte die vuistregel 144 keer niet. BEVCC leest daarom de richting van de
sessie die Balans zelf meldt (`afrrDiscovery`, met de richtingen `import` en `export`).
Alleen een **import**sessie telt: dan neemt het EMS extra stroom af, en daar gaat BEVCC
over.

### Tijdens een aFRR-importsessie: de kolom *Invoeden*

De namen zijn verwarrend. Een aFRR-importsessie is voor TenneT **afregelen**: jouw EMS
neemt extra stroom af om een overschot op het net op te vangen. Die import wordt
afgerekend tegen de **afregelprijs**, en die staat in de onbalanstabel in de kolom
*Invoeden*, niet in *Afnemen*. In de bekeken gegevens van Balans was de aFRR-importprijs
van elk sessiekwartier gelijk aan de onbalansprijs voor invoeden van dat kwartier.

### Overloop bij de start van een kwartier

Balans meldt een nieuw kwartier pas na een paar minuten. Om een lopende sessie niet bij
elke kwartierwissel te onderbreken, telt in de eerste 5 minuten van een kwartier een
importsessie in het vorige kwartier ook.

### Alleen aFRR of ook onbalans?

Met **Boost bij** kies je welke EMS-import een boost mag starten:

- **alleen aFRR** (standaard): alleen tijdens een aFRR-importsessie. De prijs is dan de
  afregelprijs van het kwartier: de laagste prijs van de afregelbiedingen die TenneT
  inzet. Worden er later in het kwartier meer biedingen ingezet, dan kan die prijs
  alleen nog **dalen**. Wat BEVCC tijdens het kwartier ziet is dus een bovengrens: is
  het goedkoop genoeg, dan blijft het dat.
- **aFRR + onbalans**: ook als het EMS om een andere reden importeert. Die import wordt
  afgerekend tegen de onbalansprijs *Afnemen* van het kwartier, en die staat pas aan het
  eind vast. Een goedkope minuut kan alsnog een duur kwartier worden, bijvoorbeeld als
  TenneT later in het kwartier ook moet opregelen (regeltoestand 2): dan geldt voor
  afname de hoogste prijs. Daarom wacht BEVCC zonder aFRR-sessie eerst 90 seconden of
  de import aanhoudt.

### Pauze alleen terwijl de auto laadt

Een aangesloten auto die niet laadt (vol, of wachtend op zonne-energie of een laadplan)
kost niets. BEVCC laat EVCC dan met rust, zodat de modus niet onnodig wisselt. Een lopende pauze blijft wel staan zolang de prijspiek duurt: een gepauzeerde
auto laadt immers niet.

### Boost alleen vanuit Smart

*Uit* betekent dat je niet wilt laden; dat negeert BEVCC niet. In *Snel* laadt de auto al
op vol vermogen. Boosten heeft dus alleen zin vanuit Smart, en na de boost gaat EVCC
altijd terug naar Smart.

### Ondergrens voor de thuisaccu

Tijdens een EMS-import houdt het EMS vaak het netvermogen vast. Gaat de auto laden, dan
kan de thuisaccu (deels) de auto voeden in plaats van het net. EVCC's eigen instellingen
voor de thuisbatterij (voorrang, buffer) gelden alleen bij laden op zonne-energie, niet
in Snel. Daarom start een boost alleen als de thuisaccu op of boven de ondergrens zit, en
stopt hij 2 % eronder. Daarnaast stopt een boost als het net minder dan 1 kW levert: dan
dekt de thuisaccu het verbruik van huis en auto, en is er geen goedkope import meer.

Wil je dat de import de auto helemaal dekt, zet *Boost min. EMS-import* dan dicht bij het
laadvermogen van je auto.

### EMS-import herkennen

BEVCC ziet een EMS-import als de thuisaccu met meer dan 500 W laadt en de netafname
zonder de auto boven *Boost min. EMS-import* ligt. Laden op zonne-energie valt daarmee af:
dan is de netafname laag of negatief.

### Robuust schakelen

- **De EVCC-modus is de waarheid.** BEVCC onthoudt alleen wat het zelf deed (status) en
  welke modus terug moet. Een minuut na een pauze of boost controleert BEVCC of EVCC de
  modus echt heeft overgenomen, en meldt het als dat niet zo is.
- **Handmatig gaat voor.** Wijzigt iemand de modus tijdens een pauze of boost, dan stapt
  BEVCC opzij tot die situatie voorbij is.
- **Terugzetten met controle.** Bij het terugzetten wacht BEVCC tot de modus echt
  verandert, probeert het tot 3 keer, en meldt het als het niet lukt. Staat de modus
  intussen ergens anders op (door jou), dan blijft die staan.
- **Herstart of storing.** Komt EVCC terug na een herstart met een andere modus dan
  BEVCC verwacht, dan zet BEVCC de modus opnieuw. Valt de prijs weg tijdens een pauze,
  dan blijft de pauze nog 15 minuten staan en geeft BEVCC daarna EVCC weer vrij.
- **Hysterese.** Een pauze eindigt pas als de prijs 2 minuten onder *Pauze boven* −
  € 0,02 ligt; een boost heeft dezelfde marge, en daarna 10 minuten rust. Zo wisselt EVCC
  niet bij elke minuutprijs van modus.
- **Snel = `now`.** EVCC toont *Snel*, maar de waarde in de API is `now`. BEVCC leest de
  beschikbare waarden van de modus-entiteit en gebruikt de juiste.

### Eén plek voor de EVCC-koppeling

Alle EVCC-entiteiten lopen via `bevcc_evcc_prefix` en `bevcc_evcc_laadpunt` in
`secrets.yaml` en via eigen BEVCC-entiteiten (zoals `select.bevcc_evcc_modus`, dat de
modus doorgeeft aan EVCC). Daardoor hoeft niemand het package aan te passen, en kan een
update het bestand gewoon vervangen. Watt of kilowatt maakt niet uit: BEVCC rekent om.

### Instellingen die een update overleven

De instellingen hebben bewust geen vaste beginwaarde in het package (anders zouden ze bij
elke herstart terugspringen). Een eigen automatisering zet ze eenmalig op de
standaardwaarden; tot die tijd doet BEVCC niets.

## Entiteiten

| Entiteit | Wat |
|---|---|
| `sensor.bevcc_afnameprijs` | All-in afnameprijs voor de beslissingen (attribuut `kaal`: kale prijs in €/kWh) |
| `sensor.bevcc_prijsbron` | Welke bron de prijs nu levert |
| `sensor.bevcc_tennet_onbalans` | Live onbalansprijs *Afnemen* (€/MWh); attributen `afnemen`, `invoeden`, `tijd` |
| `binary_sensor.bevcc_afrr_importsessie` | Balans meldt een aFRR-importsessie voor jouw EMS |
| `sensor.bevcc_balans_kwartierprijs` | All-in kwartierprijs volgens Balans |
| `sensor.bevcc_balans_afrr_importprijs` | Kale aFRR-importprijs van het lopende kwartier |
| `binary_sensor.bevcc_prijspiek` | Prijs boven *Pauze boven* |
| `binary_sensor.bevcc_ems_import` | Het EMS importeert al 90 seconden |
| `binary_sensor.bevcc_goedkope_import` | Voorwaarden voor een boost |
| `sensor.bevcc_doel` | Wat BEVCC nu wil: `geen`, `pauze` of `boost` |
| `input_select.bevcc_status` | Wat BEVCC gedaan heeft: `rust`, `pauze`, `boost` of `handmatig` (niet zelf wijzigen) |
| `input_text.bevcc_te_herstellen_modus` | De modus die na een pauze terugkomt |
| `select.bevcc_evcc_modus` | Doorgeefluik naar de EVCC-modus van je laadpunt |
| `sensor.bevcc_net_vermogen`, `sensor.bevcc_thuisaccu_vermogen`, `sensor.bevcc_laadvermogen`, `sensor.bevcc_thuisaccu_soc`, `binary_sensor.bevcc_auto_aangesloten`, `binary_sensor.bevcc_auto_laadt` | EVCC-waarden in watt, met vaste tekens (net + = afname, thuisaccu + = ontladen) |
| `automation.bevcc_prijssturing` | De automatisering die de modus zet; uitzetten = BEVCC uit |
| `sensor.bevcc_versie`, `sensor.bevcc_laatste_versie`, `binary_sensor.bevcc_update_beschikbaar` | Versiecontrole |

## Probleemoplossing

**Rode balk "Balans-API niet bereikbaar".** Meestal is de cookie verlopen. Leg een nieuwe
vast ([docs/cookie.md](docs/cookie.md)) en herlaad RESTful.

**Rode balk "EVCC-laadpunt niet gevonden".** De entiteit
`select.<prefix>_<laadpunt>_mode` bestaat niet. Controleer `bevcc_evcc_prefix` en
`bevcc_evcc_laadpunt` in `secrets.yaml` en herstart. Heb je EVCC-entiteiten hernoemd, dan
moeten ook de andere namen uit [Vereisten](#vereisten) kloppen.

**Er komt geen boost.** Kijk op de kaart bij *Details* naar *Doel op dit moment* en in de
geschiedenis naar *Goedkope import*. Veelvoorkomende oorzaken: de thuisaccu zit onder de
ondergrens, *Boost bij* staat op *alleen aFRR* en er is geen aFRR-sessie, de import is
kleiner dan *Boost min. EMS-import*, de prijs ligt net boven *Boost onder*, de vorige boost
is minder dan 10 minuten geleden, of EVCC staat niet op Smart.

**Er komt geen pauze.** Een pauze komt alleen als de auto echt laadt. Staat de auto
aangesloten maar laadt hij niet, dan laat BEVCC EVCC met rust.

**Melding "modus niet overgenomen" of "terugzetten mislukt".** EVCC of de integratie
reageerde niet. Controleer of je de modus in EVCC zelf kunt wijzigen vanuit Home
Assistant.

**Oranje balk "Live TenneT-prijs niet beschikbaar".** De onbalanspagina is tijdelijk
onbereikbaar of veranderd. BEVCC rekent dan met de kwartierprijs van Balans. Blijft het zo,
meld het dan als [issue](https://github.com/Freekers/BEVCC/issues).

**Wat deed BEVCC precies?** Instellingen → Automatiseringen → *BEVCC prijssturing* →
*Traces* toont per keer welke tak is gekozen en waarom. Het logboek op de kaart toont elke
pauze, boost en vrijgave met prijs, bron, netvermogen en thuisaccu.

## Bekende beperkingen

- BEVCC houdt geen rekening met een vertrektijd of gewenste laadtoestand (SoC). Een pauze
  gaat ook door als een laadplan in EVCC daardoor niet gehaald wordt. Moet je auto
  gegarandeerd op tijd een bepaalde laadtoestand hebben, dan is BEVCC misschien niets
  voor jou.
- BEVCC werkt alleen goed als de prijsgrenzen in EVCC uit staan
  ([Installatie](#installatie), stap 1).
- De Balans-API is niet openbaar: Balans kan hem zonder aankondiging veranderen of
  afsluiten, en de cookie moet je af en toe vernieuwen.
- De onbalanspagina van Tenergy wordt uitgelezen (*scraping*); een andere opmaak kan de
  live prijs laten wegvallen (dan is er terugval op de kwartierprijs van Balans).
- De minuutprijs is een voorlopige waarde. De afrekening van Balans gebruikt de definitieve
  kwartierprijs; die kan anders uitvallen (zie [Alleen aFRR of ook
  onbalans?](#alleen-afrr-of-ook-onbalans)).
- BEVCC stuurt één laadpunt.
- De energiebelasting is die van de eerste schijf (tot 10.000 kWh per jaar).
- Getest met één opstelling: EVCC met een Alfen-laadpaal en een thuisbatterij met het
  Balans-EMS. Werkt het bij jou anders, [meld het](https://github.com/Freekers/BEVCC/issues).

## Ontwikkelen en testen

De templates en beslissingen worden getest met pytest, tegen synthetische testgegevens in
[`tests/fixtures`](tests/fixtures) (geen echte accountgegevens):

```bash
pip install -r requirements-dev.txt
yamllint --strict .
pytest
```

Bij elke push controleert GitHub Actions daarnaast het package met de
configuratiecontrole van Home Assistant (`hass --script check_config`).

Bijdragen zijn welkom via issues en pull requests. Plak daarbij nooit je cookie, je
`secrets.yaml` of ruwe API-antwoorden met accountgegevens.

Een nieuwe versie uitbrengen: verhoog de versie in `sensor.bevcc_versie` in
[`packages/bevcc.yaml`](packages/bevcc.yaml), zet de wijzigingen bovenaan de
[CHANGELOG](CHANGELOG.md) en maak op GitHub een release met tag `vX.Y.Z`.

## Dankwoord

- De Tweakers-community rond Balans Energie, voor de uitleg over de prijsberekening.
- [EVCC](https://evcc.io) en [ha-evcc van marq24](https://github.com/marq24/ha-evcc).

## Licentie

[MIT](LICENSE). Je mag BEVCC vrij gebruiken, aanpassen en delen, zolang de licentietekst
erbij blijft. Er is geen garantie.

## Disclaimer

BEVCC is een onafhankelijk fanproject. Het is niet officieel en niet gemaakt,
gecontroleerd, goedgekeurd of ondersteund door Balans Energie, en is op geen enkele manier
gelieerd aan Balans Energie. *Balans Energie* is een handelsmerk van Balans Energie; de
naam wordt alleen gebruikt om aan te geven met welke dienst BEVCC samenwerkt. Hetzelfde
geldt voor de namen van TenneT, Tenergy, EVCC en andere genoemde partijen.

BEVCC gebruikt een niet-openbare API van het Balans-dashboard en een openbare webpagina
met onbalansprijzen. Beide kunnen zonder aankondiging veranderen of verdwijnen. BEVCC
stuurt je laadpunt aan en kan daardoor laden pauzeren of op vol vermogen zetten.

**Gebruik op eigen risico.** De makers zijn niet aansprakelijk voor schade, hogere
energiekosten, een niet geladen auto of andere gevolgen van het gebruik van BEVCC.
Controleer zelf je instellingen, laadsessies en facturen. Voor vragen over je contract,
prijzen of factuur kun je alleen bij Balans Energie terecht.
