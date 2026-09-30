# Alexa → komplettes Home Assistant

Ziel: Echo als Sprach-Eingang für **dein ganzes HA** (Klar NLU + Geräte).

Alexa kann das **nicht mit einem einzigen Schalter**. Du brauchst **zwei Wege**:

| Weg | Wofür | Beispiel |
|-----|--------|----------|
| **A. Smart-Home-Skill** (Nabu Casa, schon aktiv) | An/Aus, Dimmen, Lautstärke, Play/Pause freigegebener Geräte | „Alexa, Licht Wohnzimmer an“ / „Alexa, Homepod lautstärke 20“ |
| **B. Assist-Skill** (einmal anlegen) | Freie Sätze → Klar (Radio, „spiel Housetime auf dem Homepod“, alles was Assist kann) | „Alexa, frage Home Assistant: spiel Housetime auf dem Homepod“ |

Ohne Weg B bleibt „Alexa, spiel Housetime…“ immer **Amazon-Musik auf dem Echo**.

---

## Status auf deinem HA (vorbereitet)

- Nabu Casa Alexa: **an**
- Remote-UI: **aktiviert** (Domain: `….ui.nabu.casa`) — nötig für den Assist-Skill
- Für Alexa freigegeben u. a.: Lights, Switches, Scripts, Scenes, **Music-Assistant-HomePod**
- Apple-TV-HomePod-Entity **nicht** an Alexa (nur der MASS-Homepod)

Nach dem Restart in der **Alexa-App**: „Geräte suchen“ bzw. *„Alexa, entdecke Geräte“*.

---

## Weg A – prüfen (Smart Home)

1. Alexa-App → Skills → **Home Assistant** verknüpft?
2. *„Alexa, entdecke Geräte“*
3. Test: *„Alexa, Licht … an“* (Name wie in HA)

Das steuert freigegebene Entities. **Keine** freien Natural-Language-Sätze wie Klar-Lab.

---

## Weg B – Assist-Skill (Klar über Echo) — einmalig ~15 Min

### 1. Long-Lived Token in HA

Profil (unten links) → **Sicherheit** → **Token erstellen**  
Name z. B. `Alexa Assist Skill` → Token **kopieren** (nur einmal sichtbar).

### 2. Agent-ID von Klar

Entwicklerwerkzeuge → Aktionen → `conversation.process`  
Agent = **Klar NLU** → YAML-Modus → `agent_id` notieren  
(üblich: `conversation.klar_nlu`)

### 3. Skill in Alexa Developer Console

1. https://developer.amazon.com/alexa/console/ask → **Create Skill**
2. Name z. B. `Home Assistant`
3. Sprache: **Deutsch (DE)**
4. Experience: **Other** · Model: **Custom** · Hosting: **Alexa-hosted (Python)**
5. Template: **Import skill**  
   Repo: `https://github.com/fabianosan/HomeAssistantAssist.git`
6. Tab **Code** → Datei `config.cfg` (unter lambda):

```txt
home_assistant_url=https://DEINE-SUBDOMAIN.ui.nabu.casa
home_assistant_token=DEIN_LONG_LIVED_TOKEN
home_assistant_agent_id=conversation.klar_nlu
home_assistant_language=de-DE
ask_for_further_commands=True
suppress_greeting=False
debug=True
```

`home_assistant_url` = deine Nabu-Casa-URL **ohne** Pfad (in HA: Einstellungen → Home Assistant Cloud → Remote-UI / externe URL).

7. **Save** → **Deploy**
8. Tab **Build** → Invocation Name z. B. `home assistant` oder `mein haus` → **Build skill**
9. Alexa-App → Skills → **Deine Skills** → **Dev** → Skill **aktivieren**

### 4. Tests

```
Alexa, öffne Home Assistant
→ spiel Housetime auf dem Homepod

Alexa, frage Home Assistant nach Licht im Flur an

Alexa, frage Home Assistant: stelle die Lautstärke vom Homepod auf 20
```

Antwort kommt von Klar; Musik landet auf dem Homepod (MASS), nicht auf dem Echo.

**Hinweis:** Alexa-Hosted Skills haben ~8 s Timeout. Klar-Hausbefehle sind schnell genug; langsame LLM-Antworten ggf. AWS-Variante des Skills.

---

## Was du *nicht* erwarten solltest

- Rein „Alexa, spiel Housetime auf dem Homepod“ **ohne** Skill-Invocation → bleibt Amazons eigener Musikpfad.
- Echo als Music-Assistant-Player ohne extra MASS-Alexa-Skill (anderes Thema; du willst den Homepod).

---

## Kurz-Checkliste

- [ ] „Alexa, entdecke Geräte“ nach dem HA-Restart
- [ ] Long-Lived Token erzeugt
- [ ] Assist-Skill importiert + `config.cfg` mit Nabu-URL + Token + `conversation.klar_nlu`
- [ ] Skill in Alexa-App (Dev) aktiviert
- [ ] Test: *„Alexa, frage Home Assistant: spiel Housetime auf dem Homepod“*
