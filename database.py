import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "classified.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS countries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            country_id INTEGER NOT NULL,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE,
            UNIQUE(name, country_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            state_id INTEGER NOT NULL,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (state_id) REFERENCES states(id) ON DELETE CASCADE,
            UNIQUE(name, state_id)
        )
    """)

    conn.commit()
    conn.close()


def seed_data():
    conn = get_db()
    cursor = conn.cursor()

    count = cursor.execute("SELECT COUNT(*) FROM countries").fetchone()[0]
    if count > 0:
        conn.close()
        return

    data = {
        "United States": {
            "Alabama": ["Auburn", "Birmingham", "Dothan", "Gadsden", "Huntsville", "Mobile", "Montgomery", "Muscle Shoals", "Tuscaloosa"],
            "Alaska": ["Anchorage", "Fairbanks", "Juneau", "Kenai Peninsula"],
            "Louisiana": ["Monroe", "New Orleans", "Shreveport"],
            "Maine": ["Maine"],
            "Maryland": ["Annapolis", "Baltimore", "Cumberland Valley", "Eastern Shore", "Frederick", "Western Maryland"],
            "Massachusetts": ["Boston", "Cape Cod", "South Coast", "Springfield", "Worcester"],
            "Pennsylvania": ["Pittsburgh", "Poconos", "Reading", "Scranton", "Williamsport", "York"],
            "Rhode Island": ["Providence", "Warwick"],
            "South Carolina": ["Charleston", "Columbia", "Florence", "Greenville", "Hilton Head", "Myrtle Beach"],
        },
        "Canada": {
            "Alberta": ["Calgary", "Edmonton", "Red Deer"],
            "British Columbia": ["Vancouver", "Victoria", "Kelowna"],
            "Ontario": ["Toronto", "Ottawa", "Hamilton", "London"],
            "Quebec": ["Montreal", "Quebec City", "Laval"],
        },
        "Indonesia": {
            "Java": ["Batam", "Jakarta", "Makassar", "Medan", "Surabaya"],
        },
        "Japan": {
            "Kanto": ["Fukuoka", "Hiroshima", "Nagoya", "Okinawa", "Osaka-Kobe-Kyoto", "Sapporo", "Sendai", "Tokyo"],
        },
        "Jordan": {
            "Amman": ["Amman"],
        },
        "Austria": {
            "Austria": ["Innsbruck", "Linz", "Salzburg", "Wien"],
        },
        "Belarus": {
            "Belarus": ["Minsk"],
        },
        "Belgium": {
            "Belgium": ["Antwerp", "Brussel", "Charleroi", "Ghent", "Liege"],
        },
        "Bosnia and Herzegovina": {
            "Bosnia": ["Sarajevo"],
        },
        "Spain": {
            "Spain": ["Bilbao", "Cadiz", "Canarias", "Coruna", "Granada", "Ibiza", "Madrid", "Malaga", "Mallorca", "Murcia", "Oviedo", "Salamanca", "San Sebastian", "Sevilla", "Valencia", "Valladolid", "Zaragoza"],
        },
    }

    sort_order = 0
    for country_name, states in data.items():
        cursor.execute(
            "INSERT INTO countries (name, sort_order) VALUES (?, ?)",
            (country_name, sort_order),
        )
        country_id = cursor.lastrowid
        sort_order += 1

        state_sort = 0
        for state_name, cities in states.items():
            cursor.execute(
                "INSERT INTO states (name, country_id, sort_order) VALUES (?, ?, ?)",
                (state_name, country_id, state_sort),
            )
            state_id = cursor.lastrowid
            state_sort += 1

            city_sort = 0
            for city_name in cities:
                cursor.execute(
                    "INSERT INTO cities (name, state_id, sort_order) VALUES (?, ?, ?)",
                    (city_name, state_id, city_sort),
                )
                city_sort += 1

    conn.commit()
    conn.close()
