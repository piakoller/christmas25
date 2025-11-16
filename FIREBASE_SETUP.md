Schritte zum Einrichten von Firebase (Firestore) für die Wunschliste

1) Firebase-Projekt anlegen
- Gehe zu https://console.firebase.google.com/ und lege ein neues Projekt an.
- Öffne im Projekt das Menü "Einstellungen" → "Dienstkonten" (Service accounts).
- Erstelle einen neuen privaten Schlüssel (JSON). Lade die JSON-Datei herunter.

2) Firestore aktivieren
- In der Firebase Console: "Cloud Firestore" → Datenbank erstellen → Modus: Test oder Produktionsregeln nach Bedarf.

3) Streamlit Secrets setzen
- Öffne deine App auf Streamlit Cloud (oder `streamlit` im lokalen Dev mit `secrets.toml`).
- Füge den Inhalt der heruntergeladenen Service-Account-JSON als Secret mit dem Schlüssel `firebase` hinzu.

Beispiel `secrets.toml` (lokal):

```toml
[firebase]
project_id = "mein-projekt-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "firebase-adminsdk-abcde@mein-projekt-id.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
# ... rest of the fields from the JSON
```

Wichtig: Achte auf korrekte Escape-Sequenzen in `private_key` (Zeilenumbrüche als `\n`), wenn du `secrets.toml` manuell erstellst.

4) Rechte und Sicherheit
- Für einfache Projekte kannst du die Standardregeln verwenden. Für Produktionen solltest du die Firestore-Sicherheitsregeln prüfen.

5) Tests
- Sobald die Secrets gesetzt sind, sollte die App automatisch Firestore verwenden.
- Wenn Firestore nicht erreichbar ist, fällt die App auf die lokale `wunschliste.json` Datei zurück.

Wenn du möchtest, übernehme ich das Hochladen des Service-Account-JSON in eure Streamlit-Secrets (du müsstest mir den Inhalt nicht hier geben — ich gebe die genaue Anweisung, wie du es kopierst).