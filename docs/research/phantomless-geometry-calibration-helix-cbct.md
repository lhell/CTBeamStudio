# Zusammenfassung: Phantomlose geometrische Kalibrierung von Helix-CBCT

## 1. Ausgangslage und Zielsetzung

Untersucht werden soll eine phantomlose geometrische Kalibrierung eines Cone-Beam-CT-Systems (CBCT) mit Helixtrajektorie.

Die verfügbaren Rohdaten bestehen aus einem 3D-Projektionsdatensatz mit den Dimensionen:

- Projektionswinkel bzw. Aufnahmeindex
- Detektorhöhe
- Detektorbreite

Das Ziel ist, die statischen geometrischen Detektorparameter zu bestimmen, sodass simulierte Projektionen möglichst gut mit den gemessenen Projektionen übereinstimmen. Die korrigierte Geometrie soll anschließend für eine iterative Rekonstruktion verwendet werden.

Wichtig ist die Abgrenzung: Es geht zunächst nicht um die Schätzung periodischer oder aufnahmeabhängiger Bewegungen des Detektors, sondern um eine konstante geometrische Fehlstellung über den gesamten Scan.

Ein wesentliches Ziel ist außerdem, die Kalibrierung möglichst direkt im Projektionsraum durchzuführen, ohne zuvor ein vollständiges 3D-Volumen rekonstruieren zu müssen.

## 2. Grundidee der vorgeschlagenen Methode

Die Kalibrierung soll auf automatisch erkannten Bildmerkmalen in den Projektionen beruhen:

- Kanten und Linien
- markante Punkte und Strukturen
- gegebenenfalls wiedererkennbare Merkmale über mehrere Projektionen hinweg

Diese Merkmale werden über verschiedene Projektionswinkel hinweg verfolgt. Aus ihren Positionen auf dem Detektor lässt sich auf die zugrunde liegende Geometrie schließen.

Die zentrale Idee ist eine gemeinsame Optimierung aus:

1. statischer Detektorgeometrie,
2. unbekannten 3D-Positionen der erkannten Merkmale,
3. Abweichungen zwischen gemessenen und vorhergesagten Detektorpositionen.

Das entspricht konzeptionell einer Bundle-Adjustment-Optimierung, wie sie auch aus der Photogrammetrie und Structure-from-Motion bekannt ist.

## 3. Mathematische Formulierung

Für einen unbekannten 3D-Merkmalspunkt \(X_i\) und seine gemessene Detektorposition \(m_{ij}=(u_{ij},v_{ij})\) in Projektion \(j\) wird eine Projektionsfunktion definiert:

\[ \hat m_{ij}=\Pi(X_i,\beta_j,\theta) \]

Dabei sind:

- \(X_i\): unbekannte 3D-Position des Merkmals
- \(\beta_j\): bekannte oder nominale Scanpose der jeweiligen Projektion
- \(\theta\): gesuchte statische Detektorgeometrie
- \(\Pi\): Projektionsmodell des CBCT-Systems

Die Optimierung lautet:

\[ \min_{\theta,X_i} \sum_{i,j} w_{ij} \left\| m_{ij}-\Pi(X_i,\beta_j,\theta) \right\|^2 + \lambda Q(\theta) \]

Der erste Term minimiert den Reprojektionsfehler. Der zweite Term \(Q(\theta)\) enthält physikalische Nebenbedingungen oder Regularisierungen, beispielsweise plausible Grenzen für Detektorverschiebungen und -rotationen.

### Alternative für Kanten

Statt ausschließlich einzelne Punkte zu verfolgen, können auch Kanteninformationen genutzt werden.

Dazu wird aus jeder Projektion eine Kantenkarte \(E_j\) und eine zugehörige Distanztransformation \(D_j\) erzeugt. Der Fehler eines vorhergesagten Merkmals lässt sich dann über seinen Abstand zur nächsten Kante bewerten:

\[ E_{\mathrm{edge}}= \sum_{i,j}w_{ij} D_j\left(\Pi(X_i,\beta_j,\theta)\right)^2 \]

Das erlaubt eine Optimierung auch dann, wenn keine zuverlässige punktweise Zuordnung zwischen Projektionen möglich ist.

Allerdings können reine Kantenabstände mehrdeutig sein. Eine robuste Methode sollte deshalb möglichst Kantenorientierungen, lokale Bildmerkmale und gegebenenfalls Punktkorrespondenzen kombinieren.

### Mögliche hybride Zielfunktion

\[ E(\theta)= \lambda_1 E_{\mathrm{tracks}} +\lambda_2 E_{\mathrm{edges}} +\lambda_3 E_{\mathrm{DCC}} +\lambda_4 E_{\mathrm{prior}} \]

Damit könnten Featuretracks, Kanten, Helix-Projektionskonsistenz und physikalische Vorinformationen gemeinsam berücksichtigt werden.

## 4. Zu schätzende Geometrieparameter

Die statische Detektorgeometrie kann zunächst durch folgende Parameter beschrieben werden:

| Parameter      | Bedeutung                                 |
| -------------- | ----------------------------------------- |
| \(\Delta u\)   | Detektorverschiebung horizontal           |
| \(\Delta v\)   | Detektorverschiebung vertikal             |
| \(\rho\)       | Rotation innerhalb der Detektorebene      |
| \(\alpha\)     | Detektorneigung um eine Achse             |
| \(\gamma\)     | Detektorneigung um die zweite Achse       |
| \(\Delta n\)   | Verschiebung entlang der Detektornormalen |

Nicht alle Parameter sind zwangsläufig unabhängig bestimmbar. Beispielsweise können Detektorverschiebungen mit der Objektposition oder der Rotationsachse gekoppelt sein. Eine Verschiebung entlang der Detektornormalen kann wiederum mit dem Abstand zwischen Quelle und Detektor sowie der Vergrößerung zusammenhängen.

Empfohlene Vorgehensweise:

1. Zunächst \(\Delta u,\Delta v,\rho\) schätzen.
2. Anschließend die Detektorneigungen \(\alpha,\gamma\) ergänzen.
3. Erst danach testen, ob \(\Delta n\) aus den vorhandenen Daten zuverlässig identifizierbar ist.

Die nominale Quelltrajektorie, die Rotationswinkel, der Helixvorschub und die übrigen bekannten Systemparameter sollten dabei möglichst festgehalten oder explizit regularisiert werden.

## 5. Besonderheiten der Helixtrajektorie

Die Helixtrajektorie ist für die Kalibrierung interessant, weil sich die Quelle während der Rotation zusätzlich in axialer Richtung bewegt.

Das kann zusätzliche geometrische Information liefern und die Identifizierbarkeit bestimmter Parameter verbessern. Es muss jedoch experimentell überprüft werden, welche Parameter tatsächlich unabhängig geschätzt werden können.

Besonders relevant sind hier die sogenannten Data-Consistency-Conditions (DCC) für Helix-CBCT. Diese beschreiben mathematische Konsistenzbedingungen zwischen unterschiedlichen Projektionen und können als zusätzliche Optimierungsbedingungen eingesetzt werden.

DCC können helfen, eine geometrisch plausible Lösung zu finden, ersetzen aber nicht automatisch die merkmalsbasierte Schätzung der Detektorpose.

## 6. Vorgeschlagener Arbeitsablauf

1. **Nominale Geometrie festlegen**
   
   Vorhandene Systemparameter, Quelltrajektorie, Detektorabmessungen, Pixelgröße und Helixvorschub definieren.

2. **Projektionsdaten vorbereiten**
   
   Falls erforderlich Dark- und Flatfield-Korrektur durchführen, fehlerhafte Pixel behandeln und geeignete Projektionsdaten erzeugen. Für erste Versuche können logarithmierte, korrigierte Projektionen verwendet werden.

3. **Merkmale extrahieren**
   
   Kanten, markante Punkte und Linien in den einzelnen Projektionen automatisch erkennen.

4. **Merkmale über Projektionen verknüpfen**
   
   Wiedererkennbare Merkmale über mehrere Winkel hinweg verfolgen und Zuverlässigkeitsgewichte bestimmen.

5. **Geometrie optimieren**
   
   Statische Detektorparameter und unbekannte 3D-Merkmalspositionen gemeinsam anhand des Reprojektionsfehlers schätzen.

6. **Ergebnis validieren**
   
   Reprojektionsfehler, geometrische Plausibilität und die Übereinstimmung in nicht zur Optimierung verwendeten Projektionen prüfen.

7. **Iterative Rekonstruktion durchführen**
   
   Die geschätzte Geometrie für die Vorwärtsprojektion und iterative Rekonstruktion verwenden.

8. **Optional alternierend verfeinern**
   
   Bei Bedarf Geometrie und Volumen abwechselnd optimieren, um die Übereinstimmung zwischen simulierten und gemessenen Projektionen weiter zu verbessern.

Ein wichtiger methodischer Punkt: Wenn Objekt und Geometrie gleichzeitig optimiert werden, können sie sich gegenseitig kompensieren. Deshalb sind geeignete Nebenbedingungen, Referenzkoordinaten und physikalische Priors notwendig.

## 7. Relevante wissenschaftliche Arbeiten

| Paper | Essenz und Eignung |
|-------|-------------------|
| Sawall, Knaup & Kachelrieß (2012) – A robust geometry estimation method for spiral, sequential and circular cone-beam micro-CT | Schätzt die Geometrie aus der projizierten Bahn einer einzelnen Metallkugel, auch für Spiral-CT. Ohne dediziertes Kalibrierphantom, aber mit künstlichem Marker. Der direkteste Vorläufer für eine merkmalsbasierte Helix-Kalibrierung. |
| Panetta et al. (2008) – An optimization-based method for geometrical calibration in cone-beam CT without dedicated phantoms | Phantomlose geometrische Kalibrierung anhand allgemeiner Projektionsdaten und einer Optimierungszielfunktion. Grundlegende Referenz für die phantomlose Kalibrierung. |
| Lesaint et al. (2017) – Calibration for Circular Cone-Beam CT Based on Consistency Conditions | Nutzt Projektionskonsistenzbedingungen für eine phantomlose Kalibrierung bei Kreisbahnen. Methodisch interessant als Grundlage für zusätzliche Konsistenzterme. |
| Mouchet et al. (2023) – Cone-Beam Pair-Wise Data Consistency Conditions in Helical CT | Entwickelt paarweise DCC für Helix-CT. Besonders relevant für die mathematische Beschreibung von Projektionskonsistenz und als mögliche Regularisierung. |
| Stayman et al. (2024) – Fully automatic online geometric calibration for non-circular cone-beam CT orbits using fiducials with unknown placement | Schätzt Geometrie und unbekannte Fiduzialpositionen gemeinsam. Relevant für die gemeinsame Optimierung von Geometrie und unbekannten 3D-Punkten, benötigt aber weiterhin Marker. |
| Phantom-Free Geometric Refinement for Industrial CBCT Using Physical Constraints and a Normalized Low-Rank Projection Prior (2026) | Phantomlose Verfeinerung mit Projektionsmerkmalen, physikalischen Grenzen und Low-Rank-Projektionsprior. Sehr aktueller Vergleichsansatz. |
| Shim et al. (2026) – Self-Operating Geometry Calibration for Cone-Beam Computed Tomography Using Brute-Force Search | Phantomlose Schätzung von Detektorverschiebungen und In-Plane-Rotation durch mehrstufige Suche und Bildähnlichkeitsoptimierung. |

### Literatur-Links

- Sawall et al. 2012: https://pubmed.ncbi.nlm.nih.gov/22957606/
- Panetta et al. 2008: https://pubmed.ncbi.nlm.nih.gov/18583729/
- Lesaint et al. 2017: https://ieeexplore.ieee.org/document/7999272/
- Mouchet et al. 2023: https://pubmed.ncbi.nlm.nih.gov/37053055/
- Stayman et al. 2024: https://pmc.ncbi.nlm.nih.gov/articles/PMC11963847/
- Phantom-Free Geometric Refinement 2026: https://pmc.ncbi.nlm.nih.gov/articles/PMC13517192/
- Shim et al. 2026: https://eurekamag.com/research/104/262/104262982.php

## 8. Forschungsansatz und mögliche Forschungslücke

Die Literatur zeigt, dass phantomlose Geometriekalibrierung, Feature-basierte Geometrieschätzung und Projektionskonsistenz bereits untersucht wurden.

Die Kombination der folgenden Eigenschaften erscheint jedoch als interessanter Ansatz:

- Helix-CBCT-Daten
- automatisch extrahierte natürliche Kanten und Featuretracks statt dedizierter Metallmarker
- ausschließlich statische Detektorpose als gesuchte Geometrie
- gemeinsame Optimierung von Detektorpose und unbekannten 3D-Merkmalspunkten
- keine vorherige vollständige 3D-Rekonstruktion
- Verwendung der geschätzten Geometrie für iterative Rekonstruktion

Die Forschungslücke sollte nicht als gesichert oder vollständig neuartig dargestellt werden, bevor eine systematische Literaturrecherche erfolgt ist. Insbesondere Sawall et al. (2012) sind ein wichtiger Vorläufer, weil dort bereits eine Geometrieschätzung aus einer projizierten Featuretrajektorie durchgeführt wird.

## 9. Möglicher Arbeitstitel und Forschungsfrage

**Arbeitstitel:**

Feature-Based Phantomless Detector Geometry Calibration for Helical Cone-Beam CT Without Full Volume Reconstruction

**Zentrale Forschungsfrage:**

Kann die statische Detektorgeometrie eines Helix-CBCT-Systems allein anhand automatisch extrahierter Kanten und Featuretrajektorien im Projektionsraum zuverlässig geschätzt werden, ohne zuvor ein vollständiges 3D-Volumen zu rekonstruieren?

**Mögliche wissenschaftliche Beiträge:**

1. Entwicklung einer automatischen Methode zur Extraktion und Verknüpfung natürlicher Bildmerkmale über Helixprojektionen.
2. Entwicklung einer gemeinsamen Optimierung zur Schätzung der statischen Detektorpose und der unbekannten 3D-Merkmalspositionen.
3. Untersuchung der Identifizierbarkeit der einzelnen Geometrieparameter und Vergleich mit DCC-basierten sowie vollständigen volumenbasierten Kalibrierungsverfahren.

## 10. Wichtigste Schlussfolgerung

Der vielversprechendste Ansatz ist eine projektionsbasierte, merkmalsgestützte Optimierung nach dem Prinzip des Bundle Adjustments, ergänzt durch Helix-DCC und physikalische Nebenbedingungen.

Damit könnte die statische Detektorgeometrie ohne vollständige Volumenrekonstruktion geschätzt werden. Der zentrale technische und wissenschaftliche Knackpunkt wird sein, natürliche Merkmale über die Projektionen zuzuordnen und nachzuweisen, welche statischen Geometrieparameter aus diesen Daten tatsächlich eindeutig bestimmbar sind.
