import sqlite3
import os

DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(DATA_DIR, "classified.db")


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL DEFAULT '#',
            sort_order INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            balance REAL DEFAULT 0.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            i_am TEXT DEFAULT '',
            i_see TEXT DEFAULT '',
            name_alias TEXT DEFAULT '',
            age TEXT DEFAULT '',
            headline TEXT NOT NULL,
            body TEXT NOT NULL,
            city TEXT DEFAULT '',
            phone_code TEXT DEFAULT '+1',
            phone TEXT DEFAULT '',
            location_area TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            repost_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT '#daa520',
            sort_order INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS post_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            media_type TEXT NOT NULL DEFAULT 'photo',
            filename TEXT NOT NULL,
            slot INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
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
            "Alabama": ["Birmingham", "Montgomery", "Huntsville", "Mobile", "Tuscaloosa", "Auburn", "Dothan", "Gadsden", "Muscle Shoals"],
            "Alaska": ["Anchorage", "Fairbanks", "Juneau", "Kenai Peninsula", "Sitka", "Wasilla"],
            "Arizona": ["Phoenix", "Tucson", "Mesa", "Scottsdale", "Chandler", "Tempe", "Flagstaff", "Yuma", "Sedona"],
            "Arkansas": ["Little Rock", "Fort Smith", "Fayetteville", "Springdale", "Jonesboro", "Hot Springs", "Pine Bluff"],
            "California": ["Los Angeles", "San Francisco", "San Diego", "San Jose", "Sacramento", "Oakland", "Fresno", "Long Beach", "Bakersfield", "Anaheim", "Santa Ana", "Riverside"],
            "Colorado": ["Denver", "Colorado Springs", "Aurora", "Fort Collins", "Boulder", "Pueblo", "Aspen", "Vail"],
            "Connecticut": ["Hartford", "New Haven", "Bridgeport", "Stamford", "Waterbury", "Norwalk", "Danbury"],
            "Delaware": ["Wilmington", "Dover", "Newark", "Middletown", "Rehoboth Beach"],
            "Florida": ["Miami", "Orlando", "Tampa", "Jacksonville", "Fort Lauderdale", "St. Petersburg", "Tallahassee", "Sarasota", "Naples", "West Palm Beach"],
            "Georgia": ["Atlanta", "Savannah", "Augusta", "Columbus", "Macon", "Athens", "Roswell", "Albany"],
            "Hawaii": ["Honolulu", "Hilo", "Kailua", "Maui", "Pearl City", "Waipahu"],
            "Idaho": ["Boise", "Meridian", "Nampa", "Idaho Falls", "Pocatello", "Twin Falls", "Coeur d'Alene"],
            "Illinois": ["Chicago", "Springfield", "Peoria", "Rockford", "Naperville", "Aurora", "Joliet", "Champaign", "Evanston"],
            "Indiana": ["Indianapolis", "Fort Wayne", "Evansville", "South Bend", "Carmel", "Bloomington", "Gary", "Muncie"],
            "Iowa": ["Des Moines", "Cedar Rapids", "Davenport", "Sioux City", "Iowa City", "Waterloo", "Ames"],
            "Kansas": ["Wichita", "Overland Park", "Kansas City", "Topeka", "Olathe", "Lawrence", "Manhattan"],
            "Kentucky": ["Louisville", "Lexington", "Bowling Green", "Owensboro", "Covington", "Frankfort", "Paducah"],
            "Louisiana": ["New Orleans", "Baton Rouge", "Shreveport", "Lafayette", "Lake Charles", "Monroe", "Alexandria"],
            "Maine": ["Portland", "Lewiston", "Bangor", "South Portland", "Auburn", "Augusta", "Bar Harbor"],
            "Maryland": ["Baltimore", "Annapolis", "Frederick", "Rockville", "Bethesda", "Columbia", "Silver Spring", "Cumberland Valley", "Eastern Shore", "Western Maryland"],
            "Massachusetts": ["Boston", "Worcester", "Springfield", "Cambridge", "Lowell", "New Bedford", "Cape Cod", "South Coast"],
            "Michigan": ["Detroit", "Grand Rapids", "Ann Arbor", "Lansing", "Flint", "Kalamazoo", "Traverse City", "Dearborn"],
            "Minnesota": ["Minneapolis", "Saint Paul", "Rochester", "Duluth", "Bloomington", "Plymouth", "Woodbury"],
            "Mississippi": ["Jackson", "Gulfport", "Biloxi", "Hattiesburg", "Meridian", "Southaven", "Oxford"],
            "Missouri": ["Kansas City", "St. Louis", "Springfield", "Columbia", "Independence", "Jefferson City", "Branson"],
            "Montana": ["Billings", "Missoula", "Great Falls", "Bozeman", "Helena", "Butte", "Kalispell"],
            "Nebraska": ["Omaha", "Lincoln", "Bellevue", "Grand Island", "Kearney", "North Platte"],
            "Nevada": ["Las Vegas", "Reno", "Henderson", "North Las Vegas", "Sparks", "Carson City"],
            "New Hampshire": ["Manchester", "Nashua", "Concord", "Dover", "Rochester", "Portsmouth"],
            "New Jersey": ["Newark", "Jersey City", "Trenton", "Atlantic City", "Princeton", "Hoboken", "Camden", "Paterson"],
            "New Mexico": ["Albuquerque", "Santa Fe", "Las Cruces", "Rio Rancho", "Roswell", "Taos"],
            "New York": ["New York City", "Buffalo", "Rochester", "Syracuse", "Albany", "Yonkers", "Long Island", "White Plains"],
            "North Carolina": ["Charlotte", "Raleigh", "Durham", "Greensboro", "Winston-Salem", "Asheville", "Wilmington", "Fayetteville"],
            "North Dakota": ["Fargo", "Bismarck", "Grand Forks", "Minot", "West Fargo", "Dickinson"],
            "Ohio": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron", "Dayton", "Canton", "Youngstown"],
            "Oklahoma": ["Oklahoma City", "Tulsa", "Norman", "Broken Arrow", "Edmond", "Lawton", "Stillwater"],
            "Oregon": ["Portland", "Salem", "Eugene", "Bend", "Medford", "Corvallis", "Ashland"],
            "Pennsylvania": ["Philadelphia", "Pittsburgh", "Allentown", "Reading", "Scranton", "Harrisburg", "Erie", "York", "Williamsport", "Poconos"],
            "Rhode Island": ["Providence", "Warwick", "Cranston", "Pawtucket", "Newport", "Woonsocket"],
            "South Carolina": ["Charleston", "Columbia", "Greenville", "Myrtle Beach", "Florence", "Hilton Head", "Rock Hill"],
            "South Dakota": ["Sioux Falls", "Rapid City", "Aberdeen", "Brookings", "Watertown", "Mitchell"],
            "Tennessee": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville", "Murfreesboro", "Gatlinburg"],
            "Texas": ["Houston", "Dallas", "San Antonio", "Austin", "Fort Worth", "El Paso", "Arlington", "Corpus Christi", "Plano", "Lubbock"],
            "Utah": ["Salt Lake City", "Provo", "West Valley City", "Ogden", "St. George", "Park City", "Moab"],
            "Vermont": ["Burlington", "South Burlington", "Rutland", "Montpelier", "Barre", "Stowe"],
            "Virginia": ["Virginia Beach", "Norfolk", "Richmond", "Arlington", "Alexandria", "Chesapeake", "Newport News", "Charlottesville", "Roanoke"],
            "Washington": ["Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue", "Olympia", "Everett", "Redmond"],
            "West Virginia": ["Charleston", "Huntington", "Morgantown", "Parkersburg", "Wheeling", "Martinsburg"],
            "Wisconsin": ["Milwaukee", "Madison", "Green Bay", "Kenosha", "Racine", "Appleton", "Waukesha"],
            "Wyoming": ["Cheyenne", "Casper", "Laramie", "Gillette", "Rock Springs", "Jackson Hole"],
        },
        "Canada": {
            "Alberta": ["Calgary", "Edmonton", "Red Deer", "Lethbridge", "Medicine Hat", "Fort McMurray", "Grande Prairie", "Airdrie", "Spruce Grove", "St. Albert"],
            "British Columbia": ["Vancouver", "Victoria", "Surrey", "Burnaby", "Richmond", "Kelowna", "Kamloops", "Nanaimo", "Prince George", "Abbotsford", "Whistler"],
            "Manitoba": ["Winnipeg", "Brandon", "Steinbach", "Thompson", "Portage la Prairie", "Selkirk", "Winkler", "Dauphin"],
            "New Brunswick": ["Fredericton", "Saint John", "Moncton", "Dieppe", "Miramichi", "Edmundston", "Bathurst", "Campbellton"],
            "Newfoundland and Labrador": ["St. John's", "Mount Pearl", "Corner Brook", "Conception Bay South", "Grand Falls-Windsor", "Paradise", "Gander", "Happy Valley-Goose Bay"],
            "Nova Scotia": ["Halifax", "Dartmouth", "Sydney", "Truro", "New Glasgow", "Glace Bay", "Yarmouth", "Kentville", "Amherst"],
            "Ontario": ["Toronto", "Ottawa", "Mississauga", "Brampton", "Hamilton", "London", "Markham", "Vaughan", "Kitchener", "Windsor", "Richmond Hill", "Burlington", "Oshawa", "Barrie", "Kingston", "Thunder Bay", "Niagara Falls"],
            "Prince Edward Island": ["Charlottetown", "Summerside", "Stratford", "Cornwall", "Montague"],
            "Quebec": ["Montreal", "Quebec City", "Laval", "Gatineau", "Longueuil", "Sherbrooke", "Saguenay", "Levis", "Trois-Rivieres", "Terrebonne", "Saint-Jean-sur-Richelieu"],
            "Saskatchewan": ["Saskatoon", "Regina", "Prince Albert", "Moose Jaw", "Swift Current", "Yorkton", "North Battleford", "Estevan"],
            "Northwest Territories": ["Yellowknife", "Hay River", "Inuvik", "Fort Smith", "Behchoko"],
            "Nunavut": ["Iqaluit", "Rankin Inlet", "Arviat", "Baker Lake", "Cambridge Bay"],
            "Yukon": ["Whitehorse", "Dawson City", "Watson Lake", "Haines Junction", "Carmacks"],
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

    # Seed default categories
    default_categories = [
        ("Categories 1", "#c62828", 1),
        ("Categories 2", "#1565c0", 2),
        ("Categories 3", "#2e7d32", 3),
        ("Categories 4", "#6a1b9a", 4),
        ("Categories 5", "#e65100", 5),
    ]
    for cat_name, cat_color, cat_order in default_categories:
        cursor.execute(
            "INSERT OR IGNORE INTO categories (name, color, sort_order) VALUES (?, ?, ?)",
            (cat_name, cat_color, cat_order),
        )

    conn.commit()
    conn.close()
