# BEVCC: Balans Energie EVCC Companion

Een Home Assistant-package dat [EVCC](https://evcc.io) laat meebewegen met de
onbalansprijs en de aFRR-sessies van je thuisbatterij bij Balans Energie:

- **Pauze** bij een prijspiek: laadt de auto en is de prijs te hoog, dan zet BEVCC
  EVCC op *Uit*.
- **Boost** bij goedkope import: laadt het Balans-EMS je thuisbatterij goedkoop uit
  het net, dan zet BEVCC EVCC op *Snel*, zodat de auto meelaadt.
- **Boost bij export** (optioneel): verkoopt het EMS stroom uit je thuisbatterij voor een
  lage prijs, dan zet BEVCC EVCC op *Snel*, zodat je die stroom zelf gebruikt.
- **Laadstroom regelen** (optioneel): tijdens een boost zet BEVCC de maximale laadstroom
  zo, dat de auto niet meer neemt dan de goedkope import levert. Zo laadt een auto van
  10 kW de thuisaccu niet leeg tijdens een import van 5 kW.
- **Terugzetten**: daarna krijgt EVCC de modus (en de maximale laadstroom) terug die er
  stond.

EVCC blijft de baas over je laadpunt en de vermogensbegrenzing. BEVCC wisselt alleen de
modus, en alleen om prijsredenen; met *Laadstroom regelen* ook de maximale laadstroom,
alleen tijdens een boost.

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
| **Boost bij export** (standaard uit) | het EMS levert stroom uit de thuisaccu terug voor een all-in prijs op of onder *Boost bij export onder*, thuisaccu op of boven de *ondergrens* (of: ondergrens genegeerd) | Smart → **Snel** | terug naar Smart als de goedkope teruglevering voorbij is |
| **Rust** | geen van beide | ongewijzigd | – |

Met **Laadstroom regelen** aan past BEVCC tijdens een boost ook de maximale laadstroom van
EVCC aan, en zet hem daarna terug (zie [Laadstroom regelen](#laadstroom-regelen)).

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
- de netafname (met de auto) onder *Boost min. EMS-vermogen* − 1 kW zakt (standaard
  2 − 1 = 1 kW): het EMS importeert (bijna) niet meer en vooral de thuisaccu voedt de
  auto, of
- de thuisaccu onder de *ondergrens* − 2 % zakt, of
- bij *Boost bij* = *alleen aFRR*: de aFRR-importsessie eindigt; bij *aFRR + dynamisch*: de
  aFRR-sessie en de dynamische import allebei voorbij zijn, of
- met *Laadstroom regelen* aan: de thuisaccu toch meer dan 1 kW ontlaadt (dan dekt de
  import de auto niet meer, ook niet op de laagste laadstroom).

Een boost bij export stopt (ook na 2 minuten) zodra de exportprijs boven *Boost bij export
onder* + € 0,02 komt, het net (met de auto) minder dan 0,2 kW terugkrijgt, of de
thuisaccu onder de *ondergrens* − 2 % zakt (tenzij je de ondergrens voor export negeert).

Na een boost wacht BEVCC 5 minuten voordat een nieuwe boost kan starten. De boost
verandert zelf de vermogens die BEVCC meet (het EMS reageert op de auto); zonder die rust
kan een boost steeds aan- en uitgaan.

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

Dat is de **afnameprijs** (`sensor.bevcc_afnameprijs`): de prijs voor een pauze en op het
dashboard. Voor een **boost** geldt de **boostprijs** (`sensor.bevcc_boostprijs`): dezelfde
prijs, behalve in een kwartier met dynamische (day-ahead) import van Balans zonder
aFRR-sessie. Dan is het de dynamische prijs, die een dag vooraf vastligt (zie
[Dynamische (day-ahead) import](#dynamische-day-ahead-import)).

Of er een aFRR-importsessie of dynamische import loopt, weet alleen Balans: dat leest BEVCC
uit de Balans-API (`binary_sensor.bevcc_afrr_importsessie`,
`sensor.bevcc_balans_dynamisch_prijs`). De live onbalansprijzen per minuut
komen van de openbare pagina met actuele onbalansprijzen van
[Tenergy Services](https://services.tenergy.nl/public.aspx/actualimbalanceprices), op
basis van TenneT-gegevens.

**Voorbeeld.** *Afnemen* is 214,90 €/MWh = € 0,2149/kWh kaal. All-in:
0,2149 × 1,21 + 0,02 + 0,11085 = **€ 0,391/kWh**: boven € 0,35, dus pauze als de auto
laadt. Omgekeerd ligt de grens van € 0,35 all-in bij ongeveer 181 €/MWh kaal, en
€ 0,20 bij ongeveer 57 €/MWh. De dashboardkaart rekent dit voor je om.

Vaste kosten per dag of jaar (vastrecht, netbeheer, heffingskorting) tellen niet mee:
die betaal je ook als de auto niet laadt, dus ze veranderen de beslissing niet.

### Exportprijs (boost bij export)

Voor een boost bij export telt wat het EMS voor teruggeleverde stroom krijgt: de
**exportprijs** (`sensor.bevcc_exportprijs`). Ook die is **all-in**, met dezelfde formule als
de afnameprijs, zodat je alle grenzen direct kunt vergelijken (zie [Boost bij
export](#boost-bij-export)). De kale prijs staat in het attribuut `kaal` en komt uit:

| Situatie | Kale exportprijs | Bron in Home Assistant |
|---|---|---|
| aFRR-exportsessie van jouw EMS | live onbalansprijs **Afnemen** (de opregelprijs) | `sensor.bevcc_tennet_onbalans`, attribuut `afnemen` |
| andere teruglevering | live onbalansprijs **Invoeden** | `sensor.bevcc_tennet_onbalans`, attribuut `invoeden` |
| live prijs niet beschikbaar | exportprijs van Balans voor het kwartier | `sensor.bevcc_balans_exportprijs` |
| dynamisch (day-ahead) exportplan | onbekend: geen boost bij export | `binary_sensor.bevcc_dynamische_export` |

Een aFRR-exportsessie is het spiegelbeeld van een importsessie: TenneT moet **opregelen**,
jouw EMS levert extra terug, en dat wordt afgerekend tegen de opregelprijs. Die staat in
de kolom *Afnemen*. In de bekeken gegevens van Balans was de aFRR-exportprijs van elk
sessiekwartier gelijk aan de onbalansprijs voor afnemen van dat kwartier.

## Vereisten

- Een **Balans Energie**-contract met dynamische (onbalans)prijzen en een thuisbatterij
  die door het Balans-EMS wordt aangestuurd (aFRR). Zonder thuisbatterij werkt de
  pauze ook, maar dan heeft boost geen zin.
- **EVCC** met een laadpunt, gekoppeld aan Home Assistant via de HACS-integratie
  [ha-evcc van marq24](https://github.com/marq24/ha-evcc). BEVCC gebruikt van het
  laadpunt `select.<prefix>_<laadpunt>_mode`, `binary_sensor.<prefix>_<laadpunt>_connected`,
  `binary_sensor.<prefix>_<laadpunt>_charging` en `sensor.<prefix>_<laadpunt>_charge_power`,
  en van de site `sensor.<prefix>_grid_power`, `sensor.<prefix>_battery_power` en
  `sensor.<prefix>_battery_soc`. Voor *Laadstroom regelen* daarnaast
  `select.<prefix>_<laadpunt>_max_current` en (als ze er zijn)
  `select.<prefix>_<laadpunt>_min_current`, `sensor.<prefix>_<laadpunt>_phases_active` en
  `select.<prefix>_<laadpunt>_phases`.
- **Home Assistant 2025.1 of nieuwer** (Home Assistant OS of Container: `curl` en
  `python3` zijn daar aanwezig).
- Home Assistant moet `dashboard.balansenergie.nl`, `services.tenergy.nl` en
  `api.github.com` kunnen bereiken.
- Aanbevolen: een **circuit met maximale stroom** (hoofdzekering) in EVCC. In de modus
  Snel laadt de auto op vol vermogen terwijl de thuisaccu ook laadt; EVCC's
  vermogensbegrenzing blijft daarbij gewoon gelden. *Laadstroom regelen* verlaagt alleen
  de maximale stroom van het laadpunt en vervangt die begrenzing niet.

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
| Boost onder | `input_number.bevcc_boost_onder` | € 0,20 | All-in prijs waaronder een boost mag. Op € 0,00 staat boost uit. |
| Boost bij | `input_select.bevcc_boost_bij` | alleen aFRR | *alleen aFRR*: alleen tijdens een aFRR-importsessie. *aFRR + dynamisch*: ook tijdens dynamische (day-ahead) import. *aFRR + onbalans*: bij alle EMS-import, dus ook dynamisch. Zie [ontwerpkeuzes](#boost-bij-afrr-dynamisch-of-onbalans). |
| Boost min. EMS-vermogen | `input_number.bevcc_boost_min_import` | 2 kW | Netafname (zonder de auto) die nodig is om een boost te starten. Een boost stopt als de netafname (met de auto) 1 kW onder deze waarde zakt. Een boost bij export start pas als het net (met de auto) minstens deze waarde terugkrijgt. |
| Accu-ondergrens | `input_number.bevcc_accu_ondergrens` | 50 % | Geen boost onder deze laadtoestand; een lopende boost stopt 2 % eronder. |
| Boost bij export onder | `input_number.bevcc_boost_export_onder` | uit (€ 0,00) | All-in exportprijs waarop of waaronder je de teruggeleverde stroom liever zelf gebruikt. Op € 0,00 staat boost bij export uit. Zie [Boost bij export](#boost-bij-export). |
| Export negeert accu-ondergrens | `input_boolean.bevcc_boost_export_negeer_ondergrens` | uit | Aan: een boost bij export kijkt niet naar de *Accu-ondergrens*. De auto mag de thuisaccu dan leeg laden zolang het EMS terug levert. |
| Laadstroom regelen | `input_boolean.bevcc_laadstroom_regelen` | uit | Aan: tijdens een boost past BEVCC de maximale laadstroom van EVCC aan. Zie [Laadstroom regelen](#laadstroom-regelen). |
| Energiebelasting | `input_number.bevcc_energiebelasting` | € 0,11085 | Per kWh incl. btw, 2026, eerste schijf. **Elk jaar per 1 januari bijwerken.** |
| Leverkosten | `input_number.bevcc_leverkosten` | € 0,02 | Opslag van Balans per kWh incl. btw. |

Zet je `input_boolean.bevcc_standaardwaarden` uit, dan zet BEVCC alle instellingen terug
op de standaardwaarden. Bij een update naar 1.4 staan de nieuwe instellingen vanzelf uit;
je bestaande instellingen blijven staan.

## Updaten

1. Klik op GitHub op **Watch → Custom → Releases** om een bericht te krijgen bij een nieuwe
   versie. Home Assistant meldt het ook zelf: BEVCC kijkt elke 6 uur naar de nieuwste
   release en maakt dan een melding en een balk op de dashboardkaart.
2. Lees bij de release (of in de [CHANGELOG](CHANGELOG.md)) wat er verandert. Een nieuwe
   hoofdversie (2.0.0) vraagt soms een aanpassing, bijvoorbeeld in `secrets.yaml`; dat
   staat er dan bij.
3. Vervang `/config/packages/bevcc.yaml` door de nieuwe versie, controleer de
   configuratie en herstart Home Assistant. Vervang zo nodig ook de dashboardkaart.

De melding en de balk verdwijnen vanzelf zodra de nieuwe versie draait; je hoeft niets weg
te klikken. Klik je de melding weg zonder bij te werken, dan komt ze terug na een herstart
of bij een nog nieuwere release. Je instellingen blijven staan: ze zitten in Home
Assistant, niet in het bestand.

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
Een **import**sessie telt voor de afnameprijs en een gewone boost: dan neemt het EMS extra
stroom af. Een **export**sessie telt alleen voor de exportprijs bij een boost bij export.

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

### Dynamische (day-ahead) import

Sinds begin november 2026 laat de Balans-API ook dynamische import zien: het EMS koopt dan
een dag vooraf (day-ahead) stroom in voor de thuisaccu. Het Balans-dashboard noemt dat
*Dynamisch*. Per kwartier staat dan vast hoeveel er wordt afgenomen (bijvoorbeeld 9,8 kW)
en tegen welke prijs. Tijdens zo'n kwartier houdt het EMS de netafname op het plan:
verbruikt het huis meer, dan laadt de thuisaccu minder. Gaat de auto laden, dan krijgt hij
dus de stroom die anders de thuisaccu in ging.

BEVCC gebruikt de dynamische prijs daarom **alleen voor een boost**, en alleen in een
kwartier met dynamische import zonder aFRR-sessie, bij *Boost bij* = *aFRR + dynamisch* of
*aFRR + onbalans*:

- **Geen pauze op de dynamische prijs.** Het dynamische volume is al ingekocht. Een pauze
  bespaart daar niets op; er gaat alleen meer naar de thuisaccu. Een pauze blijft dus de
  afnameprijs gebruiken (aFRR of *Afnemen*).
- **Dynamisch + aFRR: de aFRR-prijs.** Een kwartier kan tegelijk dynamisch zijn en een
  aFRR-importsessie hebben: bovenop het plan neemt het EMS dan extra af voor TenneT. Het
  Balans-dashboard toont daarvoor *Dynamisch + aFRR* met een gewoon gemiddelde van beide
  prijzen. BEVCC beslist in zo'n kwartier op de aFRR-prijs, net als zonder dynamische
  import: de aFRR-sessie is de goedkope import waar een boost om draait.

In de eerste dagen met dynamische import (3 en 5 november 2026) lag de dynamische prijs in
elk kwartier boven de aFRR-prijs: rond € 0,20–0,23 kaal tegen € 0,10–0,20. Een boost op de
dynamische prijs komt dus vooral voor bij lage day-ahead prijzen, zoals op zonnige
middagen.

Balans meldt een dynamisch kwartier pas een paar minuten na de start; de dynamische prijs
is daardoor pas na ongeveer 4 minuten bekend. In de eerste 5 minuten van een kwartier geldt
de dynamische prijs van het vorige kwartier, als dat ook dynamisch was: dynamische import
loopt vaak meerdere kwartieren achter elkaar. Na het laatste kwartier van zo'n blok loopt
de dynamische prijs daardoor nog een paar minuten door.

### Boost bij: aFRR, dynamisch of onbalans?

Met **Boost bij** kies je welke EMS-import een boost mag starten:

- **alleen aFRR** (standaard): alleen tijdens een aFRR-importsessie. De prijs is dan de
  afregelprijs van het kwartier: de laagste prijs van de afregelbiedingen die TenneT
  inzet. Worden er later in het kwartier meer biedingen ingezet, dan kan die prijs
  alleen nog **dalen**. Wat BEVCC tijdens het kwartier ziet is dus een bovengrens: is
  het goedkoop genoeg, dan blijft het dat.
- **aFRR + dynamisch**: ook tijdens dynamische import, op de dynamische prijs. Die staat
  een dag vooraf vast, dus nog betrouwbaarder dan aFRR. Wel krijgt de auto stroom die het
  EMS voor de thuisaccu had ingekocht; de ondergrens van de thuisaccu blijft gelden.
- **aFRR + onbalans**: ook als het EMS om een andere reden importeert (en dus ook bij
  dynamische import). Die andere import wordt
  afgerekend tegen de onbalansprijs *Afnemen* van het kwartier, en die staat pas aan het
  eind vast. Een goedkope minuut kan alsnog een duur kwartier worden, bijvoorbeeld als
  TenneT later in het kwartier ook moet opregelen (regeltoestand 2): dan geldt voor
  afname de hoogste prijs. Daarom wacht BEVCC zonder aFRR-sessie of dynamische import
  eerst 90 seconden of de import aanhoudt.

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
stopt hij 2 % eronder. Daarnaast stopt een boost als de netafname onder *Boost min.
EMS-vermogen* − 1 kW zakt: dan dekt vooral de thuisaccu het verbruik van huis en auto, en is
de goedkope import (grotendeels) voorbij.

Wil je dat de import de auto helemaal dekt, zet dan *Laadstroom regelen* aan (zie
hieronder), of zet *Boost min. EMS-vermogen* dicht bij het laadvermogen van je auto.

### EMS-import herkennen

BEVCC ziet een EMS-import als de thuisaccu met meer dan 500 W laadt en de netafname
zonder de auto boven *Boost min. EMS-vermogen* ligt. Laden op zonne-energie valt daarmee af:
dan is de netafname laag of negatief.

Starten en doorgaan meten bewust iets anders. Bij de start telt de auto niet mee: de
import moet echt van het EMS komen. Tijdens de boost telt de auto wel mee: het EMS houdt
tijdens een import vaak het netvermogen vast en laadt de thuisaccu minder (of ontlaadt
hem) zodra de auto start. De netafname zonder de auto kan dan tot onder nul zakken terwijl
de goedkope import gewoon doorloopt. Daarom blijft een boost lopen zolang het net meer
levert dan *Boost min. EMS-vermogen* − 1 kW. Die 1 kW marge werkt net als de € 0,02 bij de
prijs: korte schommelingen in het importvermogen beëindigen de boost niet.

### Laadstroom regelen

Balans meldt wel óf er een aFRR-sessie is, maar niet hoeveel vermogen: dat verandert binnen
het kwartier van seconde tot seconde. Alleen bij dynamische import staat het geplande
vermogen in de API. BEVCC regelt daarom niet op een getal uit de API, maar op wat het meet:
tijdens een import houdt het EMS de netafname vast, dus alles wat de auto meer neemt, gaat
van de thuisaccu af.

Met **Laadstroom regelen** aan doet BEVCC tijdens een boost het volgende:

- **Import**: de auto mag hebben wat hij nu laadt, plus wat er nu naar de thuisaccu gaat,
  min 300 W marge. Laadt de thuisaccu met 4,5 kW (import 5 kW, huis 0,5 kW), dan wordt dat
  (4.500 − 300) / (3 × 230 V) = 6 A. De thuisaccu laadt daarna nog net, in plaats van de
  auto te voeden.
- **Export**: de auto mag hebben wat hij nu laadt, plus wat er nog naar het net gaat, min
  300 W marge. Zolang de omvormer van de thuisaccu niet vol is, geeft dit gewoon de volle
  stroom. Is hij vol, dan neemt de auto de teruglevering over, op 300 W na (zie [Boost bij
  export](#boost-bij-export)), en neemt hij geen stroom van het net.
- Afgerond naar beneden op hele ampère, met 230 V per fase en het aantal fasen waarop de
  auto laadt (`sensor.bevcc_laadfasen`). Nooit onder de minimale stroom van EVCC (meestal
  6 A) en nooit boven de maximale stroom die er voor de boost stond.
- Omlaag gaat direct, omhoog pas bij 300 W extra ruimte. Zo springt de stroom niet heen en
  weer als de meting rond een ampèregrens schommelt.
- BEVCC zet de nieuwe waarde direct bij de start van de boost, en daarna als het doel
  20 seconden stabiel anders is. Zo hebben EVCC, de auto en het EMS tijd om te reageren.
- Na de boost (of als je de regeling uitzet) komt de oorspronkelijke maximale stroom terug,
  met controle. Lukt dat niet binnen een minuut, dan volgt een melding en probeert BEVCC het
  elke 5 minuten opnieuw.
- **Handmatig gaat voor.** Staat de maximale stroom tijdens de boost op een andere waarde
  dan BEVCC zette (door jou, of EVCC nam de waarde niet over), dan stopt BEVCC met regelen
  tot de boost voorbij is en laat het die waarde staan.

Daarnaast verandert de boost zelf een beetje:

- Een boost bij import start alleen als de auto minstens op zijn minimale stroom kan laden
  met wat er naar de thuisaccu gaat. Bij 3 fasen en 6 A is dat 4,14 kW (+ 300 W marge);
  daaronder zou de thuisaccu ook op de laagste stroom ontladen.
- Een boost stopt als de thuisaccu toch 2 minuten lang meer dan 1 kW ontlaadt: de import
  dekt de auto dan niet meer, ook niet op de laagste stroom.

EVCC bewaart de maximale stroom van een laadpunt: BEVCC wijzigt hem dus echt, niet alleen
voor de huidige sessie. Tijdens een boost is dat de bedoeling; daarna zet BEVCC hem terug.
Wil je in die tijd zelf de maximale stroom veranderen, doe dat dan na de boost.

### Boost bij export

Het Balans-EMS verkoopt soms stroom uit de thuisaccu voor een lage prijs. Dat kan BEVCC
niet tegenhouden: het EMS is van Balans. BEVCC kan wel de auto laten laden zodra het EMS
goedkoop terug levert, zodat je die stroom zelf gebruikt. Zet daarvoor **Boost bij export
onder** op de prijs waarop of waaronder je dat wilt.

De grens is **all-in**, net als *Pauze boven* en *Boost onder*: BEVCC rekent de kale
exportprijs om met dezelfde formule (kaal × 1,21 + leverkosten + energiebelasting). Zolang
je saldeert (tot en met 2026, en zolang je over het jaar meer afneemt dan teruglevert), is
een teruggeleverde kWh ook ongeveer zoveel waard: hij bespaart de energiebelasting en btw
op een kWh die je afneemt. Of de leverkosten van € 0,02 bij teruglevering meetellen, hangt
af van Balans.

**Voorbeeld.** Wil je de auto laten laden zodra het EMS teruglevert voor € 0,40 all-in of
minder, zet *Boost bij export onder* dan op € 0,40 (≈ 222 €/MWh kaal). Zet *Pauze boven*
dan ook op minstens € 0,40, anders gaat daarboven de pauze voor (zie hieronder).

Vanaf 1 januari 2027 stopt het salderen. Een teruggeleverde kWh is dan ongeveer alleen de
kale prijs waard, terwijl de exportprijs van BEVCC nog leverkosten en energiebelasting
bevat. Zelf gebruiken loont dan al bij een hogere exportprijs: zet de grens dan hoger.

Een boost bij export start als het net minstens *Boost min. EMS-vermogen* terugkrijgt uit de
thuisaccu (de thuisaccu ontlaadt met meer dan 500 W), bij een aFRR-exportsessie direct
en anders na 90 seconden, en de thuisaccu op of boven de ondergrens zit. Met **Export
negeert accu-ondergrens** aan geldt die ondergrens niet: de auto laadt dan door tot het EMS
stopt met terugleveren (bijvoorbeeld op zijn eigen minimum van de thuisaccu).

Wat er gebeurt als de auto start:

- De thuisaccu dekt het verbruik van huis en auto, tot het maximale vermogen van de
  omvormer. Wat daarboven nodig is, komt van het net.
- Naar verwachting houdt het EMS de teruglevering vast, zoals het bij import de netafname
  vasthoudt (nog niet gemeten). Zolang de omvormer niet vol is, laadt de auto dus extra uit
  de thuisaccu en loopt de verkoop door; de thuisaccu loopt sneller leeg.
- Is de omvormer vol, dan gaat de auto ten koste van de teruglevering. Bij een omvormer van
  12 kW, een auto van 10 kW en 0,5 kW huisverbruik blijft er hooguit 1,5 kW teruglevering
  over.

Een boost bij export loopt door zolang het net nog **meer dan 0,2 kW** terugkrijgt. Dat
kleine restje is nodig: buiten de handel dekt het EMS de auto ook uit de thuisaccu, maar
levert het niets terug. Neemt de auto (met het huis) de hele omvormer, dan is op de meters
niet meer te zien of het EMS nog wil terugleveren of alleen de auto dekt. Zakt de
teruglevering 2 minuten onder 0,2 kW, dan stopt de boost, zodat de auto de thuisaccu niet
leeg laadt als de verkoop al voorbij is. Met *Laadstroom regelen* houdt BEVCC daarom
minstens 0,3 kW teruglevering over; zonder regeling kan een hoog huisverbruik de boost
laten stoppen.

Om dezelfde reden telt de auto mee bij de start: laadt de auto al (bijvoorbeeld in Smart)
en dekt het EMS hem uit de thuisaccu, dan krijgt het net niets en start er geen boost.

Het logboek noemt bij elke boost het net, de thuisaccu en de auto, zodat je kunt zien wat
jouw EMS doet.

Let op:

- Een prijspiek gaat ook hier voor: ligt de afnameprijs boven *Pauze boven* terwijl de auto
  laadt, dan pauzeert BEVCC. Zet *Boost bij export onder* daarom niet hoger dan *Pauze
  boven*; de dashboardkaart waarschuwt als dat wel zo is.
- Tijdens een aFRR-exportsessie kan de opregelprijs binnen het kwartier alleen nog
  **stijgen**. Een lage minuutprijs kan dus aan het eind van het kwartier hoger uitvallen,
  en dan heeft de auto stroom gebruikt die meer waard was.
- Een dynamisch (day-ahead) exportplan heeft in de API (nog) geen eigen prijs. In zo'n
  kwartier boost BEVCC daarom niet bij export.

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
  € 0,02 ligt; een boost heeft dezelfde marge op de prijs, 1 kW marge op het
  importvermogen, en daarna 5 minuten rust. Zo wisselt EVCC niet bij elke minuutprijs of
  schommeling in het vermogen van modus.
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
| `sensor.bevcc_afnameprijs` | All-in afnameprijs voor een pauze en op het dashboard (attribuut `kaal`: kale prijs in €/kWh) |
| `sensor.bevcc_boostprijs` | All-in prijs voor een boost: de afnameprijs, of in een kwartier met alleen dynamische import de dynamische prijs (attribuut `bron`) |
| `sensor.bevcc_prijsbron` | Welke bron de prijs nu levert |
| `sensor.bevcc_tennet_onbalans` | Live onbalansprijs *Afnemen* (€/MWh); attributen `afnemen`, `invoeden`, `tijd` |
| `binary_sensor.bevcc_afrr_importsessie` | Balans meldt een aFRR-importsessie voor jouw EMS |
| `sensor.bevcc_balans_kwartierprijs` | All-in kwartierprijs zoals het Balans-dashboard hem toont (ook *Dynamisch* en *Dynamisch + aFRR*) |
| `sensor.bevcc_balans_afrr_importprijs` | Kale aFRR-importprijs van het lopende kwartier |
| `sensor.bevcc_balans_dynamisch_prijs` | Kale dynamische (day-ahead) prijs; alleen beschikbaar in kwartieren met dynamische import |
| `binary_sensor.bevcc_prijspiek` | Prijs boven *Pauze boven* |
| `binary_sensor.bevcc_ems_import` | Het EMS importeert al 90 seconden |
| `binary_sensor.bevcc_goedkope_import` | Voorwaarden voor een boost |
| `binary_sensor.bevcc_afrr_exportsessie` | Balans meldt een aFRR-exportsessie voor jouw EMS |
| `binary_sensor.bevcc_dynamische_export` | Balans meldt een dynamisch (day-ahead) exportplan voor dit kwartier |
| `sensor.bevcc_balans_exportprijs` | Kale exportprijs van Balans voor het lopende kwartier |
| `sensor.bevcc_exportprijs` | All-in exportprijs voor een boost bij export (attributen `kaal` en `bron`) |
| `binary_sensor.bevcc_ems_export` | Het EMS levert al 90 seconden terug uit de thuisaccu |
| `binary_sensor.bevcc_goedkope_export` | Voorwaarden voor een boost bij export |
| `sensor.bevcc_doel` | Wat BEVCC nu wil: `geen`, `pauze` of `boost` (attribuut `reden`: `import` of `export`) |
| `sensor.bevcc_laadstroom_doel` | Maximale laadstroom (A) die de regeling nu wil; alleen tijdens een boost met *Laadstroom regelen* aan |
| `select.bevcc_evcc_max_laadstroom` | Doorgeefluik naar de maximale laadstroom van je laadpunt in EVCC |
| `sensor.bevcc_min_laadstroom`, `sensor.bevcc_laadfasen` | Minimale laadstroom en aantal fasen van het laadpunt |
| `input_text.bevcc_te_herstellen_stroom`, `input_text.bevcc_ingestelde_stroom` | De maximale laadstroom van vóór de boost, en wat BEVCC zelf zette (`handmatig` = iemand anders wijzigde hem) |
| `automation.bevcc_laadstroomregeling` | De automatisering die de maximale laadstroom regelt en terugzet |
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
ondergrens, *Boost bij* staat op *alleen aFRR* en er is geen aFRR-sessie (dynamische import
telt dan niet mee), de import is
kleiner dan *Boost min. EMS-vermogen*, de prijs ligt net boven *Boost onder*, de vorige boost
is minder dan 5 minuten geleden, of EVCC staat niet op Smart.

**Er komt geen boost bij export.** Kijk in de geschiedenis naar *Goedkope export* en bij
*Details* naar de exportprijs en de bron. Veelvoorkomende oorzaken: *Boost bij export
onder* staat op € 0,00 (uit), de prijs ligt erboven, de pauze gaat voor (de grens
ligt boven *Pauze boven*), de
teruglevering is kleiner dan *Boost min. EMS-vermogen* of komt van zonnepanelen (de
thuisaccu ontlaadt dan niet), de thuisaccu zit onder de ondergrens, het is een dynamisch
exportplan, of EVCC staat niet op Smart.

**Oranje balk "Laadstroom regelen staat aan, maar … bestaat niet".** De entiteit
`select.<prefix>_<laadpunt>_max_current` van ha-evcc ontbreekt of is uitgeschakeld.
Zet hem aan bij de entiteiten van het laadpunt. Zonder die entiteit boost BEVCC op vol
vermogen, zoals zonder regeling.

**Melding "maximale laadstroom niet teruggezet".** EVCC nam de oorspronkelijke waarde
niet over. BEVCC probeert het elke 5 minuten opnieuw; je kunt hem ook zelf in EVCC
terugzetten.

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
  kwartierprijs; die kan anders uitvallen (zie [Boost bij: aFRR, dynamisch of
  onbalans?](#boost-bij-afrr-dynamisch-of-onbalans)).
- De dynamische prijs is pas een paar minuten na de start van een kwartier bekend, en loopt
  na een dynamisch blok nog een paar minuten door. Hoe Balans een kwartier met
  *Dynamisch + aFRR* precies afrekent, staat niet in de API (zie [Dynamische (day-ahead)
  import](#dynamische-day-ahead-import)).
- BEVCC stuurt één laadpunt.
- *Laadstroom regelen* rekent met 230 V per fase en reageert in stappen van ongeveer een
  halve minuut tot een minuut (BEVCC, EVCC en de auto). Korte pieken in het huisverbruik
  kan de thuisaccu dus nog even opvangen. BEVCC wisselt geen fasen.
- Een boost bij export ziet alleen de teruglevering die overblijft naast huis en auto. Neemt
  de auto de hele omvormer, dan stopt de boost na 2 minuten (zie [Boost bij
  export](#boost-bij-export)). Een dynamisch exportplan heeft in de API (nog) geen prijs;
  BEVCC boost dan niet bij export.
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
configuratiecontrole van Home Assistant (`check_config`), in de officiële
Home Assistant-container (`stable`).

Bijdragen zijn welkom via issues en pull requests. Plak daarbij nooit je cookie, je
`secrets.yaml` of ruwe API-antwoorden met accountgegevens.

Een nieuwe versie uitbrengen: verhoog de versie in `sensor.bevcc_versie` in
[`packages/bevcc.yaml`](packages/bevcc.yaml), zet de wijzigingen bovenaan de
[CHANGELOG](CHANGELOG.md) en maak op GitHub een release met tag `vX.Y.Z`. De tag moet
gelijk zijn aan de versie in het package: anders blijft de updatemelding na het bijwerken
staan of verschijnt ze niet. De workflow *Release-controle* controleert dat bij elke
release.

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
