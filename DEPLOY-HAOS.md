# Deploy Fork auf HAOS (Proxmox-VM)

Ziel: Engine mit Weltfragen→LLM auf Home Assistant OS.

## 0. Voraussetzung

- GitHub-Account
- Dieses Repo als **dein** Fork/Repo auf GitHub
- Packages (GHCR) dürfen vom Account geschrieben werden

## 1. Repo pushen

```bash
cd klar-ha-nlu
git init
git add -A
git commit -m "fork: world questions route to LLM chat"
git branch -M main
git remote add origin https://github.com/DEIN_USER/klar-ha-nlu.git
git push -u origin main
```

Repo vorher auf GitHub anlegen (leer, ohne README).

## 2. Image bauen

Actions → Workflow **Fork image** → läuft bei Push auf `main` automatisch  
oder manuell **Run workflow**.

Danach existieren z. B.:

- `ghcr.io/DEIN_USER/klar-nlu-amd64:fork-llm`
- `ghcr.io/DEIN_USER/klar-nlu-aarch64:fork-llm`

**Wichtig:** Unter GitHub → Packages das Image auf **Public** stellen  
(sonst zieht HAOS es nicht ohne Token).

## 3. Add-on auf HAOS

1. In `haos-addon-fork/config.yaml` überall `REPLACE_GITHUB_USER` durch deinen GitHub-User ersetzen.
2. Ordner nach HA kopieren, z. B. Samba/SSH:

   `/addons/klar_nlu_fork/`  
   (Inhalt von `haos-addon-fork/`)

3. Einstellungen → Add-ons → Add-on Store → ⋮ → **Repositories prüfen / lokal neu laden**
4. Unter **Lokal** erscheint **Klar NLU (Fork LLM)** → installieren → starten
5. **Offizielle Klar-App stoppen** (nur eine Engine)

## 4. Integration umbiegen

Einstellungen → Geräte & Dienste → Klar NLU → Konfigurieren:

- Engine: App/Docker
- URL: `http://klar-nlu-fork:10520`
- Write-Token: derselbe Wert wie in der Fork-App (falls gesetzt)

## 5. Test (Lab)

- `Erzähl einen Witz` → `chat` + Antwort
- `Wie hoch ist der Eiffelturm?` → `chat` + LLM-Antwort (nicht reject)
- `Licht im Flur an` → `execute` (kein LLM)

## Hinweis Proxmox / amd64

HAOS in einer normalen x86-VM → Image-Tag **amd64**.  
Nur bei ARM-Board (Pi o. Ä.) brauchst du aarch64.
