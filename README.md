# Corridor CD

Prédiction probabiliste du fret aérien Congo (BZV/PNR) vers Paris CDG.

**Nom de code :** Corridor CD (CD = code pays du Congo-Brazzaville)
**Propriétaire :** Franck / HYPERAUTOMATISATION
**Produit v1 :** « Votre marchandise sera disponible à CDG à [heure], confiance [X] %. »

## Dépôt temporaire

Ce dépôt GitHub (`HyperAutomatisation/TEST2`) est un **atterrissage temporaire** : le dépôt `corridor-cd` n'est pas encore créable. Traiter la racine de ce dépôt comme le projet Corridor CD.

**Nom et chemin visés :** `corridor-cd` / `projects/web/corridor-cd/`

## Périmètre : chantiers 1 à 5

Le mapping jour de semaine → vol est une **donnée** (`collector/data/ref_flights.json`), jamais un dur dans `corridor/` ou `web/*.py`.

Hors périmètre de cette branche : Telegram (chantier 6), WhatsApp, comptes, paiements, AWB, autres corridors. Les alertes passent par `notify.send()` ; seule l'implémentation `LogChannel` est active.

Cible de déploiement : **Hostinger VPS** (Docker Compose). Pas Hetzner.

## Démarrage local

```bash
cp .env.example .env
# renseigner DATABASE_URL ; ne jamais committer le vrai .env
docker compose up --build
```

- Baromètre : http://localhost:8000
- Vol : http://localhost:8000/vol/AF754
- Meilleur jour : http://localhost:8000/meilleur-jour
- Fiabilité : http://localhost:8000/fiabilite
- API : http://localhost:8000/api/v1
- Vol du jour (JSON) : http://localhost:8000/api/v1/vol-du-jour?date=2026-09-15

Pas de login, pas de paiement, pas de cookie de suivi.

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

Démo hors ligne (échantillon OpenSky-shaped + prédictions) :

```bash
python -m backfill run --offline --months 12
python -m model generate --from-records
python -m model brier
uvicorn web.main:app --host 0.0.0.0 --port 8000
```

## Déploiement Hostinger (VPS)

Cible : un VPS Hostinger avec Docker et Docker Compose. **Ne pas déployer depuis cet agent** tant que le VPS et les secrets ne sont pas fournis. Ne jamais inventer de clés.

1. Créer un VPS Hostinger (Ubuntu) et y installer Docker Engine + le plugin Compose.
2. Cloner ce dépôt, par exemple dans `/opt/corridor-cd`.
3. `cp .env.example .env` puis renseigner au minimum `DATABASE_URL` (Compose fournit déjà Postgres interne) et, pour la collecte live, `AVIATIONSTACK_KEY`. OpenSky live : `OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET`. Ne pas committer `.env`.
4. Ouvrir le port 8000 (ou placer Nginx / le proxy Hostinger devant `127.0.0.1:8000`).
5. `docker compose up -d --build`
6. Vérifier `http://<ip>:8000/health` puis le baromètre.
7. Premier historique : `docker compose exec app python -m backfill run --offline --months 12` (ou live si les secrets OpenSky sont là), puis `docker compose exec app python -m model generate --from-records`.
8. Le service `collector` lance APScheduler (21h, 9h30, adsb 5 min dans la fenêtre 19h00-07h15 Africa/Brazzaville).

Si `overlay` échoue sur un VPS imbriqué ou un noyau restreint : `"storage-driver": "vfs"` dans `/etc/docker/daemon.json`, puis `sudo systemctl restart docker`.

Les variables Node.js / hPanel Hostinger ne s'appliquent pas : l'app est Python + Compose, pas un site Node statique.

## Backfill (chantier 2)

Objectif : 12 mois d'historique, critère **au moins 6 mois d'observations par vol** (AF736, AF754, AF722, AF940) dans `flight_records`, plus météo, ATFM CDG et archives DGAC.

```bash
python -m backfill run --offline --months 12
python -m backfill coverage
python -m backfill charts
```

`--offline` reconstruit des objets au format OpenSky à partir de la grille (source `opensky_sample`). Ce n'est **pas** un historique live OpenSky.

Live : `python -m backfill run --months 12`. Sources par défaut : `opensky,openmeteo,atfm,dgac`. Mesonet optionnel (`--with-mesonet`). ATFM : si Cloudflare bloque, déposer `apt_dly_AAAA.csv.bz2` dans `backfill/data/incoming/`.

### OpenSky

OAuth2 depuis mars 2026 (`OPENSKY_CLIENT_ID` / `SECRET`). Fenêtres d'un jour UTC. Reprise : `backfill/.state/opensky.json`.

### Open-Meteo / DGAC

Archive sans clé pour CDG, FIH, BZV, PNR. DGAC : page tendanCiel, plus saisie manuelle des causes AF dans `backfill/data/dgac_causes.manual.json`.

## Collecteurs quotidiens (chantier 3)

Modules indépendants `fetch` / `parse` / `save`, tests sur échantillons figés :

- AviationStack (max 4 req/jour, clé `AVIATIONSTACK_KEY`, jamais inventée)
- adsb.lol (poll 5 min uniquement 19h00-07h15)
- adsbdb
- tableaux aéroports congolais (BeautifulSoup, parser tolérant)
- Open-Meteo prévision
- Aviation Weather Center METAR/TAF
- Nager.Date (fériés FR + ponts)

Socle `collector/socle.py` : `run_evening` 21:00, `run_closure` 09:30. Un collecteur en erreur n'arrête pas les autres (`collection_runs`). Alerte log si l'heure prévue diverge de `ref_flights`.

```bash
python -m collector
```

## Modèle (chantier 4)

Trois couches, moyenne pondérée, probabilités de somme 1 :

1. Empirique vol + jour de semaine (6 classes), dégradation corridor si moins de 40 observations.
2. Retard hérité (0.55) et météo (0.20).
3. Fériés / ponts FR (0.15) et cause DGAC du mois (0.10).

Génération à 21 h, clôture 9 h 30. Fenêtre d'entrepôt v1 : samedi +48 h, sinon +4 h, +2 h si escale FIH/PNR, mention « estimation v1, se fiabilise avec l'historique ».

Brier vs naïve (toute la masse sur 0-15 min). Le produit doit battre la naïve sur le backfill hors ligne.

```bash
python -m model generate --date 2026-09-15
python -m model generate --from-records
python -m model brier
```

## Web app (chantier 5)

Pages en français (accents), bleu marine et blanc, mobile d'abord, sans emoji :

| Route | Contenu |
|---|---|
| `/` | Baromètre 7 jours + chiffre signature |
| `/vol/{flight_number}` | Grille, statut, distribution, entrepôt, historique 90 j |
| `/meilleur-jour` | Classement par ponctualité |
| `/fiabilite` | Brier vs naïve |
| `/api/v1/...` | JSON public, usage raisonnable |

SEO : **suivi fret aérien Congo Brazzaville Pointe-Noire Paris**.

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `DATABASE_URL` | Postgres |
| `AVIATIONSTACK_KEY` | Collecte live AviationStack (chantier 3) |
| `AVIATIONSTACK_MAX_REQ_PER_DAY` | Défaut 4 |
| `OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET` | Backfill OpenSky live |
| `OPENSKY_USER` / `OPENSKY_PASS` | Repli couple client OAuth2 |
| `OPENSKY_REQUEST_DELAY_S` | Délai entre requêtes (défaut 10 s) |
| `BACKFILL_MONTHS` | Profondeur (défaut 12) |
| `COLLECTORS_USE_SAMPLE` | `1` = échantillons figés |
| `TIMEZONE` | Défaut `Africa/Brazzaville` |

Créer les clients API sur les comptes fournisseurs, jamais inventer de secrets, jamais committer `.env`.

## Tests

```bash
OURAIRPORTS_USE_SAMPLE=1 pytest -q
```

Avec Docker : `docker compose exec app pytest -q`.

## Structure

```
collector/     collecteurs quotidiens, grille JSON, OurAirports
model/         3 couches, Brier, fenêtre d'entrepôt
web/           FastAPI + Jinja2 (SSR)
backfill/      historique OpenSky / météo / ATFM / DGAC
corridor/      Postgres, bootstrap, lecture de la grille
notify/        LogChannel (send unique)
sql/schema.sql schéma section 8
```

Stack : Python 3.12, FastAPI, Jinja2, PostgreSQL 16, APScheduler, Docker Compose (app + postgres + collector).

## Grille de saison

Saisie IATA été 2026 (`active_from` 2026-03-29, `active_to` 2026-10-24). Quatre numéros couvrent le fret AF Congo : 736, 754, 722, 940. L'itinéraire d'un même numéro peut changer selon le jour : c'est la ligne en base qui l'emporte.

Aéroports importés depuis OurAirports : LFPG (CDG), FZAA (FIH), FCBB (BZV), FCPP (PNR).
