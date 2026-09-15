# Corridor CD

Prédiction probabiliste du fret aérien Congo (BZV/PNR) vers Paris CDG.

**Nom de code :** Corridor CD (CD = code pays du Congo-Brazzaville)
**Propriétaire :** Franck / HYPERAUTOMATISATION
**Produit v1 :** « Votre marchandise sera disponible à CDG à [heure], confiance [X] %. »

## Dépôt temporaire

Ce dépôt GitHub (`HyperAutomatisation/TEST2`) est un **atterrissage temporaire** : le dépôt `corridor-cd` n'est pas encore créable. Traiter la racine de ce dépôt comme le projet Corridor CD.

**Nom et chemin visés :** `corridor-cd` / `projects/web/corridor-cd/`

## Périmètre actuel : chantier 1 (squelette) uniquement

Critère de fin : la grille Air France est en PostgreSQL et l'API renvoie le vol du jour correct (section 4 du cahier des charges). Le mapping jour de semaine → vol est une **donnée** (`collector/data/ref_flights.json`), jamais un dur dans le code.

Hors périmètre (ne pas construire) : WhatsApp, comptes, paiements, AWB, autres corridors, modules éditoriaux. Les chantiers 2 et suivants (backfill, collecteurs quotidiens, modèle, pages web complètes, notifications) ne commencent qu'après validation de ce squelette.

## Démarrage

```bash
cp .env.example .env
# renseigner AVIATIONSTACK_KEY, OPENSKY_USER, OPENSKY_PASS quand les collecteurs arriveront
docker compose up --build
```

- Application : http://localhost:8000
- Vol du jour (JSON) : http://localhost:8000/api/v1/vol-du-jour
- Date imposée (tests) : http://localhost:8000/api/v1/vol-du-jour?date=2026-09-15

Le vrai fichier `.env` n'est jamais commité.

## Tests

```bash
docker compose up -d --build
docker compose exec app pytest -q
```

Sans Docker, avec Postgres joignable via `DATABASE_URL` :

```bash
python3 -m pip install -r requirements.txt
OURAIRPORTS_USE_SAMPLE=1 pytest -q
```

Les tests vérifient que la grille section 4 est en base et que l'API renvoie le bon vol pour chaque jour de semaine.

## Structure

```
collector/     import OurAirports (fetch / parse / save)
web/           FastAPI + Jinja2 (SSR minimal, Tailwind CDN plus tard)
backfill/      réservé au chantier 2
corridor/      connexion Postgres, bootstrap, lecture de la grille
sql/schema.sql schéma section 8
```

Stack : Python 3.12, FastAPI, Jinja2, PostgreSQL 16, Docker Compose (app + postgres). Tailwind CDN et Chart.js sont prévus pour le chantier web, pas pour ce squelette.

## Grille de saison

Saisie IATA été 2026 (`active_from` 2026-03-29, `active_to` 2026-10-24). Quatre numéros couvrent le fret AF Congo : 736, 754, 722, 940. L'itinéraire d'un même numéro peut changer selon le jour : c'est la ligne en base qui l'emporte.

Aéroports importés depuis OurAirports : LFPG (CDG), FZAA (FIH), FCBB (BZV), FCPP (PNR).
