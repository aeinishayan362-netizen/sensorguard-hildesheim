# SensorGuard Hildesheim – Challenge 3 (reale Hackathon-Daten)

## Was ist enthalten?
- `app.py`: Streamlit-Dashboard mit Ampel, Wartungsliste, Einzelsensorverlauf, vorsichtiger Batterieprognose, Meldelückenanalyse und Gateway-Karte
- `data/sensor_6h.csv.gz`: aus **2.351.128 real bereitgestellten Rohdatenzeilen** berechnete 6-Stunden-Aggregate (keine simulierten Werte)
- `data/datenprofil.csv`: Datenherkunft und Vollständigkeit
- `data/gateways.csv`, `data/Gateway_Karte.png`: Veranstalterdateien

## Kostenlos veröffentlichen
1. Bestehendes GitHub-Repository `sensorguard-hildesheim` öffnen.
2. **Add file → Upload files**. Die `app.py` und `requirements.txt` im Repository ersetzen. Den Ordner `data` samt aller vier Dateien hochladen, sodass `data/sensor_6h.csv.gz` tatsächlich existiert. Commit changes.
3. Die bestehende Streamlit-Cloud-App neu starten bzw. auf automatische Neuveröffentlichung warten. **Main file path: `app.py`**, Branch `main`.
4. Wenn die App einen Fehler zeigt: unter Manage app → Logs die Fehlermeldung prüfen.

Alternativ lokal: `pip install -r requirements.txt` und `streamlit run app.py`.

## Wichtige Einschränkungen
- Kein Frame Counter in den CSV-Dateien: **Paketverlustquote nicht nachgewiesen**. Die App zeigt stattdessen beobachtete Messlücken.
- Batteriewerte liegen für viele Geräte als Spannung (Volt) vor, nicht als Prozent. Volt ist nicht ohne gerätespezifische Kennlinie in Prozent umzurechnen.
- Das Warnsystem arbeitet mit transparenten Heuristiken, nicht mit trainierter KI.
- Zeitbezug: letzter Messzeitpunkt des bereitgestellten Datensatzes, nicht die Live-Uhrzeit.
- Für eine echte Vorhersagevalidierung braucht es bestätigte Ausfall-/Wartungsprotokolle und einen zeitlich getrennten Testdatensatz.

## Jury-Demo (90 Sekunden)
1. Dashboard: „Hier sehen Sie die historischen, von den Veranstaltern bereitgestellten Messwerte statt erfundener Demo-Sensoren.“
2. Wartungsliste: „Unsere Regeln sortieren Geräte nach nachvollziehbaren Prüfhinweisen.“
3. Einzelanalyse: Sensor mit rotem Status öffnen und Messverlauf sowie konkrete Begründung zeigen.
4. Gateway-Karte: „Wir können die offizielle Infrastruktur zeigen, behaupten aber keine nicht belegte Gerätezuordnung.“
5. Grenzen: „Eine echte Paketverlustquote erfordert Frame Counter; dafür würden wir die Datenpipeline erweitern.“

**Wichtiger Hinweis:** Die vier Pflichtanforderungen der Challenge sind nicht alle vollständig erfüllt: Paketverlust ist ohne Frame Counter nicht zuverlässig bestimmbar. Eine belastbare Batterieprognose ist nur bei geeigneten Prozent-Zeitreihen möglich. Das offen anzusprechen ist besser als eine erfundene 100%-Erkennungsquote.
