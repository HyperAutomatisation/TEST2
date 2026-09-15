# Corridor CD

Prédiction probabiliste du fret aérien Congo (BZV/PNR) vers Paris CDG.

**Nom de code :** Corridor CD (CD = code pays du Congo-Brazzaville)
**Propriétaire :** Franck / HYPERAUTOMATISATION
**Produit v1 :** « Votre marchandise sera disponible à CDG à [heure], confiance [X] %. »

## Dépôt temporaire

Ce dépôt GitHub (`HyperAutomatisation/TEST2`) est un **atterrissage temporaire** : le dépôt `corridor-cd` n'est pas encore créable. Traiter la racine de ce dépôt comme le projet Corridor CD.

**Nom et chemin visés :** `corridor-cd` / `projects/web/corridor-cd/`

## Périmètre actuel : chantiers 1 (squelette) et 2 (backfill)

Le mapping jour de semaine → vol est une **donnée** (`collector/data/ref_flights.json`), jamais un dur dans le code applicatif.

Hors périmètre : WhatsApp, comptes, paiements, AWB, autres corridors, collecteurs quotidiens (chantier 3), modèle (chantier 4), pages web complètes (chantier 5).

## Démarrage

```bash
cp .env.example .env
# renseigner au minimum DATABASE_URL ; pour OpenSky live voir ci-dessous
docker compose up --build
```

- Application : http://localhost:8000
- Vol du jour (JSON) : http://localhost:8000/api/v1/vol-du-jour
- Date imposée (tests) : http://localhost:8000/api/v1/vol-du-jour?date=2026-09-15

Le vrai fichier `.env` n'est jamais commité.

Si Docker échoue dans une VM imbriquée (erreur overlay), passer le démon Docker sur le stockage `vfs` puis relancer :

```bash
# exemple : /etc/docker/daemon.json  { "storage-driver": "vfs" }
sudo systemctl restart docker
docker compose up --build
```

Sans Docker, avec Postgres joignable via `DATABASE_URL` :

```bash
python3 -m pip install -r requirements.txt
OURAIRPORTS_USE_SAMPLE=1 pytest -q
```

## Backfill (chantier 2)

Objectif : 12 mois d'historique, critère de fin **au moins 6 mois d'observations par vol** (AF736, AF754, AF722, AF940) dans `flight_records`, plus météo, ATFM CDG et archives DGAC.

### Hors ligne (pas de secrets, tests et démo)

```bash
python -m backfill run --offline --months 12
python -m backfill coverage
python -m backfill charts
```

Sorties : `backfill/output/rapport_backfill.html` (Chart.js), `flight_records.csv`, `couverture.json`.

`--offline` reconstruit des objets au format OpenSky à partir de la grille `ref_flights.json` (source `opensky_sample`). Ce n'est **pas** un historique live OpenSky.

### Live

```bash
python -m backfill run --months 12
python -m backfill run --sources openmeteo,dgac
python -m backfill run --with-mesonet --sources openmeteo
```

Sources par défaut : `opensky,openmeteo,atfm,dgac`. Mesonet (Iowa) est optionnel.

### Variables d'environnement

| Variable | Rôle |
|---|---|
| `DATABASE_URL` | Postgres |
| `OPENSKY_CLIENT_ID` | Client OAuth2 OpenSky (obligatoire pour le live depuis mars 2026) |
| `OPENSKY_CLIENT_SECRET` | Secret OAuth2 OpenSky |
| `OPENSKY_USER` / `OPENSKY_PASS` | Conservés (cahier des charges). Si les CLIENT_* sont vides, le script les utilise comme couple client OAuth2. Le basic auth n'est plus accepté par OpenSky. |
| `OPENSKY_REQUEST_DELAY_S` | Délai entre requêtes OpenSky (défaut 10 s) |
| `BACKFILL_MONTHS` | Profondeur (défaut 12) |
| `AVIATIONSTACK_KEY` | Réservé au chantier 3 |

Créer le client API sur le compte OpenSky (Account), jamais inventer de secrets, jamais committer `.env`.

### OpenSky : quotas et reprise

- Arrivées `LFPG` (CDG) et départs `FCBB` (BZV), callsigns `AFR736`, `AFR754`, `AFR722`, `AFR940`.
- Fenêtres d'**un jour UTC** (l'API actuelle limite à 1-2 jours, plus à 7).
- Crédits `/flights` : anonyme 400/jour, compte standard 4000/jour. Un backfill 12 mois dépasse souvent le quota du jour : le script enregistre `backfill/.state/opensky.json` et reprend au lancement suivant. Sur HTTP 429 il attend `Retry-After`.
- Un collecteur en erreur n'arrête pas les autres (`collection_runs`).

### Open-Meteo

Archive `archive-api.open-meteo.com` (précipitations, vent, weather_code) pour CDG, FIH, BZV, PNR. La visibilité ERA5 est souvent vide : elle est complétée via `historical-forecast-api.open-meteo.com` (mètres → km). `risk_storm` si weather_code 95, 96 ou 99. Sans clé.

### Iowa Mesonet (optionnel)

Vérification METAR horaire LFPG. Ne remplace pas Open-Meteo. Rapport `backfill/output/mesonet_verification.json` si `--with-mesonet`.

### Eurocontrol ATFM (CDG)

Fichiers mensuels / annuels `apt_dly_AAAA.csv.bz2` du portail [ansperformance.eu/csv](https://ansperformance.eu/csv/) (Airport Arrival ATFM Delays). Filtre `APT_ICAO=LFPG`, `delay_avg_min = DLY_APT_ARR_1 / FLT_ARR_1`.

Le portail est souvent derrière Cloudflare. En live, déposer les fichiers dans `backfill/data/incoming/` (noms `apt_dly_2025.csv.bz2`, etc.). Le parser est testé sur un échantillon figé.

### DGAC (semi-auto v1)

Page [statistiques du trafic aérien](https://www.ecologie.gouv.fr/politiques-publiques/statistiques-du-trafic-aerien) : liens tendanCiel. Extraction du pourcentage « vols retardés de plus de 15 min » (toutes causes, tous pavillons). Les parts de causes Air France (contrôle aérien, grève, compagnie) se saisissent dans `backfill/data/dgac_causes.manual.json` (`share_pct` à `null` tant que le chiffre n'est pas lu).

### Critère 6 mois

`python -m backfill coverage` réussit si chaque numéro a au moins 12 observations réelles (arrivée ou départ) sur une plage ≥ 180 jours.

## Tests

```bash
docker compose up -d --build
docker compose exec app pytest -q
```

Sans Docker :

```bash
OURAIRPORTS_USE_SAMPLE=1 pytest -q
```

Les tests chantier 1 vérifient la grille section 4. Les tests chantier 2 couvrent parseurs, upsert, reprise, rapport, et le critère 6 mois via `--offline`.

## Structure

```
collector/     import OurAirports (fetch / parse / save)
web/           FastAPI + Jinja2 (SSR minimal)
backfill/      scripts batch d'historique (chantier 2)
corridor/      connexion Postgres, bootstrap, lecture de la grille
sql/schema.sql schéma section 8
```

Stack : Python 3.12, FastAPI, Jinja2, PostgreSQL 16, Docker Compose (app + postgres).

## Grille de saison

Saisie IATA été 2026 (`active_from` 2026-03-29, `active_to` 2026-10-24). Quatre numéros couvrent le fret AF Congo : 736, 754, 722, 940. L'itinéraire d'un même numéro peut changer selon le jour : c'est la ligne en base qui l'emporte.

Aéroports importés depuis OurAirports : LFPG (CDG), FZAA (FIH), FCBB (BZV), FCPP (PNR).
