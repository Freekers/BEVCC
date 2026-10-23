# De Balans-cookie vastleggen

BEVCC leest de aFRR-sessies en kwartierprijzen van je eigen Balans-dashboard. Balans
heeft daar geen openbare API met sleutel voor, dus BEVCC logt in zoals je browser dat
doet: met de cookie van een ingelogde sessie.

> **Behandel de cookie als je wachtwoord.** Met de cookie kan iedereen in je
> Balans-account. Zet hem alleen in `secrets.yaml` van je eigen Home Assistant, plak
> hem nergens anders (ook niet in een issue, forum of chat) en zet `secrets.yaml`
> nooit in git of een back-up die je deelt.

## Stappen (Chrome, Edge of Firefox op een computer)

1. Log in op [dashboard.balansenergie.nl](https://dashboard.balansenergie.nl).
2. Open in hetzelfde tabblad
   `https://dashboard.balansenergie.nl/customer/current-prices/api/`.
   Je ziet nu tekst die begint met `{"prices":[...`. Krijg je een inlogpagina, log dan
   eerst opnieuw in.
3. Open de ontwikkelhulpmiddelen: **F12**, of op een Mac **Cmd + Option + I**.
4. Ga naar het tabblad **Netwerk** (*Network*) en vernieuw de pagina (**F5**).
5. Klik in de lijst op het verzoek **`api/`**.
6. Zoek bij **Headers** → **Verzoekheaders** (*Request Headers*) de regel **`Cookie`**.
   Klik er met de rechtermuisknop op en kies **Waarde kopiëren** (*Copy value*), of
   selecteer de hele waarde achter `Cookie:`.
7. Zet de waarde in `/config/secrets.yaml`, tussen dubbele aanhalingstekens:

   ```yaml
   bevcc_balans_cookie: "…de hele waarde die je hebt gekopieerd…"
   ```

8. Sluit het tabblad, maar **log niet uit**: uitloggen maakt de sessie meestal
   ongeldig, en daarmee ook de cookie in Home Assistant.
9. Laad de cookie in Home Assistant: **Ontwikkelhulpmiddelen → YAML → RESTful
   herladen** (of herstart Home Assistant).
10. Controleer na een minuut dat `binary_sensor.bevcc_afrr_importsessie` *aan* of *uit*
    is, en niet *niet beschikbaar*.

## Als de cookie verloopt

Hoe lang een sessie geldig blijft bepaalt Balans. Geeft de API 10 minuten lang geen
gegevens, dan maakt BEVCC een melding in Home Assistant en staat er een rode balk op de
dashboardkaart. Herhaal dan de stappen hierboven.

Zolang de cookie niet werkt:

- ziet BEVCC geen aFRR-importsessies en rekent het met de onbalansprijs *Afnemen*
  (tijdens een sessie te hoog, dus BEVCC pauzeert eerder en boost minder);
- boost BEVCC alleen nog als **Boost bij** op *aFRR + onbalans* staat;
- blijft de pauze bij prijspieken gewoon werken op de live TenneT-prijs.

## Hoe vaak vraagt BEVCC gegevens op?

Eén keer per minuut. Dat is genoeg: Balans werkt de prijs van het lopende kwartier maar
één keer bij, een paar minuten na de start. Zet het interval niet lager; bij te veel
verzoeken antwoordt de API met een foutmelding (HTTP 429).
