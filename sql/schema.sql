-- Schéma Corridor CD (cahier des charges, section 8).
-- SQL simple, sans ORM. Les tables hors chantier 1 restent vides.

CREATE TABLE IF NOT EXISTS ref_airports (
    ident TEXT PRIMARY KEY,
    iata_code TEXT,
    icao_code TEXT NOT NULL,
    name TEXT,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    timezone TEXT
);

CREATE TABLE IF NOT EXISTS ref_flights (
    id SERIAL PRIMARY KEY,
    flight_number TEXT NOT NULL,
    airline TEXT NOT NULL,
    aircraft TEXT,
    departure_airport TEXT NOT NULL,
    escale TEXT,
    days_of_week INTEGER[] NOT NULL,
    sched_dep_local TIME NOT NULL,
    sched_arr_cdg TIME NOT NULL,
    active_from DATE,
    active_to DATE
);

CREATE INDEX IF NOT EXISTS idx_ref_flights_days
    ON ref_flights USING GIN (days_of_week);

CREATE TABLE IF NOT EXISTS flight_records (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    flight_number TEXT NOT NULL,
    sched_dep TIMESTAMPTZ,
    actual_dep TIMESTAMPTZ,
    sched_arr_cdg TIMESTAMPTZ,
    actual_arr_cdg TIMESTAMPTZ,
    delay_min INTEGER,
    aircraft_reg TEXT,
    itinerary TEXT,
    source TEXT,
    CONSTRAINT flight_records_itinerary_chk
        CHECK (itinerary IS NULL OR itinerary IN ('direct', 'fih', 'pnr'))
);

CREATE TABLE IF NOT EXISTS aircraft_rotations (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    aircraft_reg TEXT NOT NULL,
    retard_troncon_aller_min INTEGER
);

CREATE TABLE IF NOT EXISTS weather (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    airport TEXT NOT NULL,
    forecast_bool BOOLEAN NOT NULL,
    precip_mm NUMERIC,
    vis_km NUMERIC,
    wind_kmh NUMERIC,
    risk_storm BOOLEAN
);

CREATE TABLE IF NOT EXISTS atfm_delays (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    airport TEXT NOT NULL,
    delay_avg_min NUMERIC
);

CREATE TABLE IF NOT EXISTS dgac_causes (
    id SERIAL PRIMARY KEY,
    periode TEXT NOT NULL,
    airline TEXT NOT NULL,
    cause TEXT NOT NULL,
    share_pct NUMERIC
);

CREATE TABLE IF NOT EXISTS calendar_days (
    date DATE NOT NULL,
    country TEXT NOT NULL,
    label TEXT,
    is_pont BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (date, country)
);

CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    flight_number TEXT NOT NULL,
    model_version TEXT NOT NULL,
    p_0_15 NUMERIC,
    p_15_30 NUMERIC,
    p_30_60 NUMERIC,
    p_60_120 NUMERIC,
    p_120_plus NUMERIC,
    p_cancel NUMERIC,
    factors_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notification_channels (
    id SERIAL PRIMARY KEY,
    channel TEXT NOT NULL UNIQUE,
    recipient_pattern TEXT,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS notification_log (
    id SERIAL PRIMARY KEY,
    channel TEXT NOT NULL,
    recipient TEXT,
    subject TEXT,
    text TEXT,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'logged'
);

CREATE TABLE IF NOT EXISTS collection_runs (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL,
    records_fetched INTEGER,
    error TEXT
);

-- Unicité pour reprise du backfill (chantier 2).
CREATE UNIQUE INDEX IF NOT EXISTS idx_flight_records_natural
    ON flight_records (date, flight_number, source);
CREATE UNIQUE INDEX IF NOT EXISTS idx_weather_natural
    ON weather (date, airport, forecast_bool);
CREATE UNIQUE INDEX IF NOT EXISTS idx_atfm_natural
    ON atfm_delays (date, airport);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dgac_natural
    ON dgac_causes (periode, airline, cause);

CREATE TABLE IF NOT EXISTS adsb_snapshots (
    id SERIAL PRIMARY KEY,
    seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    callsign TEXT NOT NULL,
    flight_number TEXT,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    alt_baro DOUBLE PRECISION,
    gs DOUBLE PRECISION,
    track DOUBLE PRECISION,
    seen_pos DOUBLE PRECISION,
    inferred_event TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_aircraft_rotations_natural
    ON aircraft_rotations (date, aircraft_reg);
CREATE UNIQUE INDEX IF NOT EXISTS idx_predictions_natural
    ON predictions (date, flight_number, model_version);
