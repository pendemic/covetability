"""
Seed the SQLite database with the five pilot bag models.
"""
import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "covetability.db")

BRANDS = [
    ("chloe", "Chloé"),
    ("balenciaga", "Balenciaga"),
    ("fendi", "Fendi"),
    ("dior", "Dior"),
    ("louis-vuitton", "Louis Vuitton"),
]

BAGS = [
    {
        "slug": "chloe-paddington",
        "brand_slug": "chloe",
        "model_name": "Paddington",
        "era": "Phoebe Philo for Chloé, S/S 2005-~2008",
        "initial_queries": ["chloe paddington bag", "chloe paddington satchel", "chloe padlock bag"],
    },
    {
        "slug": "balenciaga-city",
        "brand_slug": "balenciaga",
        "model_name": "City",
        "era": "Nicolas Ghesquière motorcycle line, 2001-",
        "initial_queries": ["balenciaga city bag", "balenciaga classic city", "balenciaga motorcycle bag city"],
    },
    {
        "slug": "fendi-baguette",
        "brand_slug": "fendi",
        "model_name": "Baguette",
        "era": "Silvia Venturini Fendi, 1997-; 2019 relaunch ongoing",
        "initial_queries": ["fendi baguette bag", "fendi zucca baguette", "fendi baguette vintage"],
    },
    {
        "slug": "dior-saddle",
        "brand_slug": "dior",
        "model_name": "Saddle",
        "era": "John Galliano S/S 2000; Maria Grazia Chiuri reissue 2018-",
        "initial_queries": ["dior saddle bag", "dior saddle vintage", "christian dior saddle"],
    },
    {
        "slug": "louis-vuitton-pochette-accessoires",
        "brand_slug": "louis-vuitton",
        "model_name": "Pochette Accessoires",
        "era": "1992-; current production",
        "initial_queries": ["louis vuitton pochette accessoires", "lv pochette accessoires", "louis vuitton pochette monogram"],
    },
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Insert brands
    brand_ids = {}
    for slug, name in BRANDS:
        c.execute("INSERT OR IGNORE INTO brands (slug, name) VALUES (?, ?)", (slug, name))
        c.execute("SELECT id FROM brands WHERE slug = ?", (slug,))
        brand_ids[slug] = c.fetchone()[0]

    # Insert bag models
    for bag in BAGS:
        brand_id = brand_ids[bag["brand_slug"]]
        c.execute("""
            INSERT OR IGNORE INTO bag_models (slug, brand_id, model_name, era, initial_queries)
            VALUES (?, ?, ?, ?, ?)
        """, (bag["slug"], brand_id, bag["model_name"], bag["era"], json.dumps(bag["initial_queries"])))

    conn.commit()
    
    # Print results
    c.execute("SELECT id, slug FROM bag_models")
    print("Seeded bag models:")
    for row in c.fetchall():
        print(f"  ID={row[0]}: {row[1]}")
    
    conn.close()

if __name__ == "__main__":
    seed()
