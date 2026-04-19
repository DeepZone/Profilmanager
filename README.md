# Profilmanager

Profilmanager ist eine webbasierte Verwaltungsplattform für Providerprofile (`.tar`) mit Rollenmodell, Versionierung, relationaler Datenhaltung und GitLab-Merge-Request-Workflow.

## Features

- Session-Login mit rollenbasierter Zugriffskontrolle (`Admin`, `User`)
- Benutzerverwaltung (anlegen, bearbeiten, deaktivieren, löschen)
- Profil-Upload (`.tar`), Versionierung und Download
- Trennung von Dateispeicher und Metadaten in PostgreSQL
- Such-/Filter-Grundfunktionen für Profile
- GitLab-Integration via API
  - Verbindung testen
  - Branch erstellen
  - Profil-Datei ins Repository committen/aktualisieren
  - Merge Request anlegen
  - Merge Requests listen
  - MR-Detailansicht inkl. Diff
  - MR aus Weboberfläche mergen (Admin)
- Audit-Log für zentrale Aktionen
- Docker Compose Setup mit App + PostgreSQL

## Technologie

- Python 3.12
- Flask
- Flask-SQLAlchemy + Flask-Migrate (Alembic)
- Flask-Login + Flask-WTF (inkl. CSRF)
- bcrypt
- PostgreSQL
- AdminLTE (Bootstrap Admin UI)

## Projektstruktur

```text
app/
  routes/              # Auth, Profile, User, Settings, Merge Requests
  services/            # Dateispeicher + GitLab API Layer
  templates/           # Serverseitige HTML-Views (Admin Bootstrap)
  static/              # CSS
  models.py            # Relationales Datenmodell
  forms.py             # WTForms + Validierung
migrations/            # Alembic Migrationen
scripts/entrypoint.sh  # DB Migration + Admin Seed + Gunicorn Start
Dockerfile
Docker-compose.yml
manage.py              # Flask CLI (db, seed-admin)
run.py                 # App-Entry
```

## Konfiguration

1. Beispiel kopieren:

```bash
cp .env.example .env
```

2. Werte anpassen:

- `SECRET_KEY`
- `DATABASE_URL`
- `DEFAULT_ADMIN_*`
- `UPLOAD_FOLDER`

## Start mit Docker Compose

```bash
docker compose up --build
```

Die App ist danach auf `http://localhost:5000` verfügbar.

## Initiales Setup

Beim Containerstart werden automatisch ausgeführt:

1. `flask --app manage.py db upgrade`
2. `flask --app manage.py seed-admin`
3. Start via Gunicorn

Standard-Admin-Credentials kommen aus `.env` (`DEFAULT_ADMIN_*`).

## Rollenmodell

### Admin

- Benutzerverwaltung
- GitLab-Konfiguration
- Einsicht in alle Profile
- Einsicht in alle Merge Requests
- Merge-Operation in der Weboberfläche

### User

- Eigene Profile hochladen und bearbeiten
- Eigene Profile in Standardansicht
- Zugriff auf globale Profilseite (nur Lesesicht, Zugriffsschutz pro Detailseite)
- Einsicht in MR, die aus eigenen Profilen entstanden sind

## GitLab-Fluss (webbasiert, GitHub-Desktop-ähnlich)

1. Profil wählen
2. Branchname, Commit Message, Target Branch setzen
3. Push auslösen
4. Merge Request automatisch erzeugen
5. MR-Status und Diff in der Oberfläche prüfen
6. Merge direkt aus der Oberfläche (Admin)

## Annahmen / Hinweise

- GitLab-Token wird serverseitig in der Tabelle `settings` gespeichert und nie im UI angezeigt.
- Repository-Zielpfad pro Profilversion:
  `profiles/user_<user_id>/<profile_name>/v<version>.tar`
- Bei identischem Dateipfad wird von `create file` auf `update file` fallbackt.
- Für produktive Sicherheit sollte das Secret Management (z. B. Vault/KMS) erweitert werden.

## Globale Anwendungsversionierung

Der Profilmanager führt eine globale App-Version im Format `MAJOR.MINOR.BUILD`, die serverseitig in der Datenbank (`settings`) verwaltet wird.

- **Format**: `MAJOR.MINOR.BUILD` (z. B. `1.0.17`)
- **Anzeige im UI**: in der Sidebar ganz unten als `Profilmanager v<version>`
- **Automatischer Build-Increment**: `BUILD` wird genau dann um `1` erhöht, wenn ein Merge Request in der Weboberfläche erfolgreich gemergt wurde
- **Kein Increment** bei MR-Erstellung, Push oder fehlgeschlagenem Merge
- **Admin-Verwaltung**: `MAJOR` und `MINOR` sind in den Einstellungen administrativ setzbar
  - Beim Setzen von `MINOR` wird `BUILD` auf `0` zurückgesetzt
  - Beim Setzen von `MAJOR` werden `MINOR` und `BUILD` auf `0` zurückgesetzt
- **Nachvollziehbarkeit**: Jede Versionsänderung wird über das Audit-Log als `version_changed` erfasst

## Migrationen lokal (ohne Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app manage.py db upgrade
flask --app manage.py seed-admin
python run.py
```
