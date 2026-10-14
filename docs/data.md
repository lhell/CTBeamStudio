# Daten-Dokumentation

## AAPM Low-Dose CT Challenge 2016

Dieses Projekt ist für die Verwendung mit Daten der **AAPM Low-Dose CT 
Challenge 2016** konzipiert. Die Challenge-Daten werden **NICHT** mit 
diesem Repository verteilt.

### Registrierung und Datenzugang

1. Besuchen Sie die Challenge-Website: https://www.aapm.org/grandchallenge/lowdosect/
2. Registrieren Sie sich für ein Konto
3. Akzeptieren Sie die Nutzungsbedingungen (Data Use Agreement)
4. Laden Sie die Daten herunter

### Pflichtzitate

Wenn Sie die AAPM-Daten in Ihrer Forschung verwenden, zitieren Sie bitte:

> The AAPM TG-201 supplementary data on low-dose CT
> 
> "Low-dose CT: The phantom database testing a proton therapy treatment planning system"
> - AAPM Task Group 201

Bitte beachten Sie auch die offiziellen Zitierhinweise auf der Challenge-Website.

### Keine Datenweitergabe

**WICHTIG:** Dieses Repository enthält **KEINE** Patientendaten. Die 
AAPM-Daten dürfen aufgrund des Data Use Agreements nicht weitergegeben werden.

Dieses Projekt bietet stattdessen:
- Ein synthetisches Demo-Phantom für Tests
- Werkzeuge zum Laden eigener (lizenzierter) DICOM-Daten
- Unterstützung für selbst heruntergeladene AAPM-Daten

### Eigene DICOM-Daten

Sie können Ihre eigenen DICOM-Daten verwenden:
1. Laden Sie eine DICOM-Serie in die App
2. Die App erwartet DICOM-Dateien mit gültigen HU-Werten (RescaleSlope/Intercept)

### Andere Datensätze

Das Projekt funktioniert mit **jedem** CT-Datensatz, der folgende Struktur hat:

**DICOM:**
- Gültige HU-Werte (RescaleSlope/Intercept)
- CT-Bilder (nicht andere Modalitäten)
- Unterstützte Endungen: `.dcm`, `.ima`, `.dicom`

**NumPy:**
- Shape: `(z, y, x)` (Slice-First)
- dtype: `int16`

**Unterstützte Challenge-Daten:**
- AAPM Low-Dose CT Challenge 2016
- LIDC-IDRI
- NSCLC-Radiomics
- Eigene DICOM-Serien

Das Projekt verteilt keine Daten — Nutzer laden ihre eigenen.
