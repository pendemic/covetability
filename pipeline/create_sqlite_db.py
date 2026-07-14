"""
Create a SQLite database with the covetability schema.
This bypasses alembic migrations which use PostgreSQL-specific syntax.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "covetability.db")

def create_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE brands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug VARCHAR(80) NOT NULL UNIQUE,
        name VARCHAR(160) NOT NULL UNIQUE,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE bag_models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug VARCHAR(120) NOT NULL UNIQUE,
        brand_id INTEGER NOT NULL REFERENCES brands(id) ON DELETE RESTRICT,
        model_name VARCHAR(180) NOT NULL,
        era VARCHAR(180),
        editorial_summary TEXT,
        editorial_history TEXT,
        editorial_condition_notes TEXT,
        expected_range_note TEXT,
        initial_queries JSON NOT NULL DEFAULT '[]',
        tracking_since DATE,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE bag_aliases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bag_model_id INTEGER NOT NULL REFERENCES bag_models(id) ON DELETE CASCADE,
        alias VARCHAR(240) NOT NULL,
        type VARCHAR(40) NOT NULL,
        UNIQUE(bag_model_id, alias)
    );

    CREATE TABLE bag_variants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bag_model_id INTEGER NOT NULL REFERENCES bag_models(id) ON DELETE CASCADE,
        name VARCHAR(180) NOT NULL,
        kind VARCHAR(40) NOT NULL,
        attribution_confidence TEXT,
        is_separate_market BOOLEAN NOT NULL DEFAULT 0,
        UNIQUE(bag_model_id, name)
    );

    CREATE TABLE exclusion_terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bag_model_id INTEGER,
        term VARCHAR(240) NOT NULL,
        scope VARCHAR(40) NOT NULL,
        reason VARCHAR(40) NOT NULL,
        notes TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(bag_model_id) REFERENCES bag_models(id) ON DELETE CASCADE,
        UNIQUE(scope, bag_model_id, term)
    );

    CREATE TABLE listings_raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source VARCHAR(80) NOT NULL,
        source_type VARCHAR(40) NOT NULL,
        marketplace_item_id VARCHAR(180) NOT NULL,
        title TEXT NOT NULL,
        price NUMERIC(12, 2) NOT NULL,
        currency VARCHAR(3) NOT NULL,
        shipping_price NUMERIC(12, 2),
        shipping_currency VARCHAR(3),
        shipping_included BOOLEAN,
        seller_id VARCHAR(180),
        item_url TEXT,
        image_phash VARCHAR(64),
        price_type VARCHAR(40) NOT NULL,
        match_confidence NUMERIC(5, 4),
        matched_bag_model_id INTEGER REFERENCES bag_models(id) ON DELETE SET NULL,
        matched_variant_id INTEGER REFERENCES bag_variants(id) ON DELETE SET NULL,
        match_status VARCHAR(40) NOT NULL DEFAULT 'pending',
        rule_trace JSON NOT NULL DEFAULT '{}',
        matcher_version VARCHAR(40),
        matched_at DATETIME,
        candidate_bag_model_id INTEGER REFERENCES bag_models(id) ON DELETE SET NULL,
        candidate_query VARCHAR(240),
        condition_raw TEXT,
        condition_band VARCHAR(40),
        condition_confidence VARCHAR(40) NOT NULL DEFAULT 'indeterminate',
        auth_label VARCHAR(80) NOT NULL DEFAULT 'authentication_status_unknown',
        observed_at DATETIME NOT NULL,
        first_observed DATETIME NOT NULL,
        last_observed DATETIME NOT NULL,
        expires_at DATETIME NOT NULL,
        raw_payload JSON NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source, marketplace_item_id)
    );

    CREATE TABLE listing_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER NOT NULL REFERENCES listings_raw(id) ON DELETE CASCADE,
        type VARCHAR(40) NOT NULL,
        event_date DATE NOT NULL,
        payload JSON NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE snapshot_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at DATETIME NOT NULL,
        finished_at DATETIME,
        status VARCHAR(40) NOT NULL DEFAULT 'succeeded',
        source_type VARCHAR(40) NOT NULL,
        queries_executed INTEGER NOT NULL DEFAULT 0,
        listings_fetched INTEGER NOT NULL DEFAULT 0,
        listings_new INTEGER NOT NULL DEFAULT 0,
        listings_refreshed INTEGER NOT NULL DEFAULT 0,
        errors JSON NOT NULL DEFAULT '[]',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE daily_aggregates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bag_model_id INTEGER NOT NULL REFERENCES bag_models(id) ON DELETE CASCADE,
        variant_id INTEGER REFERENCES bag_variants(id) ON DELETE SET NULL,
        condition_band VARCHAR(40) NOT NULL,
        observation_date DATE NOT NULL,
        active_listing_count INTEGER NOT NULL DEFAULT 0,
        new_listing_count INTEGER NOT NULL DEFAULT 0,
        ended_listing_count INTEGER NOT NULL DEFAULT 0,
        possible_relist_count INTEGER NOT NULL DEFAULT 0,
        median_asking_price NUMERIC(12, 2),
        p25_asking_price NUMERIC(12, 2),
        p75_asking_price NUMERIC(12, 2),
        median_total_price NUMERIC(12, 2),
        source_count INTEGER NOT NULL DEFAULT 0,
        matched_listing_count INTEGER NOT NULL DEFAULT 0,
        average_match_confidence NUMERIC(5, 4),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE UNIQUE INDEX uq_daily_aggregates_bag_variant_band_date
    ON daily_aggregates (bag_model_id, variant_id, condition_band, observation_date);

    CREATE TABLE manual_comps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bag_model_id INTEGER NOT NULL REFERENCES bag_models(id) ON DELETE CASCADE,
        variant_id INTEGER REFERENCES bag_variants(id) ON DELETE SET NULL,
        source VARCHAR(160),
        source_type VARCHAR(40) NOT NULL,
        observed_at DATETIME,
        entered_by VARCHAR(160),
        listing_url TEXT,
        sold_confirmed BOOLEAN NOT NULL DEFAULT 0,
        price_type VARCHAR(40) NOT NULL,
        price NUMERIC(12, 2) NOT NULL,
        currency VARCHAR(3) NOT NULL,
        shipping_included BOOLEAN,
        match_confidence NUMERIC(5, 4),
        condition_raw TEXT,
        condition_band VARCHAR(40),
        condition_confidence VARCHAR(40) NOT NULL DEFAULT 'indeterminate',
        notes TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE gold_labels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER REFERENCES listings_raw(id) ON DELETE SET NULL,
        marketplace_item_id VARCHAR(180),
        verdict VARCHAR(40) NOT NULL,
        rejection_reason VARCHAR(40),
        accepted_variant_id INTEGER REFERENCES bag_variants(id) ON DELETE SET NULL,
        color_family VARCHAR(120),
        condition_band VARCHAR(40),
        strap_included BOOLEAN,
        lock_included BOOLEAN,
        key_included BOOLEAN,
        dustbag_included BOOLEAN,
        cards_included BOOLEAN,
        labeled_by VARCHAR(160),
        labeled_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        notes TEXT
    );

    CREATE TABLE score_daily (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bag_model_id INTEGER NOT NULL REFERENCES bag_models(id) ON DELETE CASCADE,
        observation_date DATE NOT NULL,
        search_component_value NUMERIC(6, 2),
        search_eligible BOOLEAN NOT NULL DEFAULT 0,
        search_weight_used NUMERIC(5, 2) NOT NULL DEFAULT 0,
        inventory_component_value NUMERIC(6, 2),
        inventory_eligible BOOLEAN NOT NULL DEFAULT 0,
        inventory_weight_used NUMERIC(5, 2) NOT NULL DEFAULT 0,
        price_component_value NUMERIC(6, 2),
        price_eligible BOOLEAN NOT NULL DEFAULT 0,
        price_weight_used NUMERIC(5, 2) NOT NULL DEFAULT 0,
        breadth_component_value NUMERIC(6, 2),
        breadth_eligible BOOLEAN NOT NULL DEFAULT 1,
        breadth_weight_used NUMERIC(5, 2) NOT NULL DEFAULT 0,
        turnover_component_value NUMERIC(6, 2),
        turnover_eligible BOOLEAN NOT NULL DEFAULT 0,
        turnover_weight_used NUMERIC(5, 2) NOT NULL DEFAULT 0,
        raw_score NUMERIC(6, 2),
        smoothed_score NUMERIC(6, 2),
        confidence_raw NUMERIC(5, 4),
        classification VARCHAR(40),
        published BOOLEAN NOT NULL DEFAULT 0,
        component_trace JSON NOT NULL DEFAULT '{}',
        notes TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(bag_model_id, observation_date)
    );
    """)

    conn.commit()
    conn.close()
    print(f"Created SQLite database at {DB_PATH}")

if __name__ == "__main__":
    create_db()
