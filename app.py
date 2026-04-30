from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from itsdangerous import URLSafeSerializer
from typing import Optional
from urllib.parse import urlparse
import os
import shutil
import uuid
import hashlib
import re

from database import get_db, init_db, seed_data

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

SECRET_KEY = "change-this-in-production-classified-secret-key"
serializer = URLSafeSerializer(SECRET_KEY)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

SESSION_COOKIE = "session_token"


def is_logged_in(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return False
    try:
        data = serializer.loads(token)
        return data.get("logged_in") is True
    except Exception:
        return False


def require_login(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401, detail="Not authenticated")


USER_SESSION_COOKIE = "user_session"


def hash_password(password: str) -> str:
    salt = uuid.uuid4().hex
    return salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()


def verify_password(password: str, stored: str) -> bool:
    salt, hashed = stored.split(":", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == hashed


def get_current_user(request: Request):
    token = request.cookies.get(USER_SESSION_COOKIE)
    if not token:
        return None
    try:
        data = serializer.loads(token)
        return data
    except Exception:
        return None


LOGO_FILE = os.path.join(UPLOADS_DIR, ".logo_filename")

def get_logo_url():
    if os.path.exists(LOGO_FILE):
        with open(LOGO_FILE, "r") as f:
            fname = f.read().strip()
        if fname and os.path.exists(os.path.join(UPLOADS_DIR, fname)):
            return f"/uploads/{fname}"
    return None


@app.on_event("startup")
def startup():
    init_db()
    seed_data()


# ─── Main Page ───────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/user", status_code=303)
    db = get_db()
    countries = db.execute(
        "SELECT * FROM countries ORDER BY sort_order, name"
    ).fetchall()

    location_data = []
    for country in countries:
        states = db.execute(
            "SELECT * FROM states WHERE country_id = ? ORDER BY sort_order, name",
            (country["id"],),
        ).fetchall()

        state_list = []
        for state in states:
            cities = db.execute(
                "SELECT * FROM cities WHERE state_id = ? ORDER BY sort_order, name",
                (state["id"],),
            ).fetchall()
            state_list.append({
                "id": state["id"],
                "name": state["name"],
                "cities": [{"id": c["id"], "name": c["name"]} for c in cities],
            })

        location_data.append({
            "id": country["id"],
            "name": country["name"],
            "states": state_list,
        })

    menu_items = db.execute(
        "SELECT * FROM menu_items ORDER BY sort_order, name"
    ).fetchall()
    menu_list = [{"id": m["id"], "name": m["name"], "url": m["url"]} for m in menu_items]

    db.close()
    logo_url = get_logo_url()
    return templates.TemplateResponse(request=request, name="index.html", context={"locations": location_data, "menu_items": menu_list, "logo_url": logo_url, "user": None})


# ─── User Auth ───────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
def user_login_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/user", status_code=303)
    return templates.TemplateResponse(request=request, name="user_login.html", context={"error": None, "logo_url": get_logo_url()})


@app.post("/login")
def user_login(request: Request, email: str = Form(...), password: str = Form(...)):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    db.close()

    if user and verify_password(password, user["password_hash"]):
        token = serializer.dumps({"user_id": user["id"], "full_name": user["full_name"], "email": user["email"]})
        response = RedirectResponse(url="/user", status_code=303)
        response.set_cookie(USER_SESSION_COOKIE, token, httponly=True, max_age=86400)
        return response

    return templates.TemplateResponse(request=request, name="user_login.html", context={"error": "Invalid email or password", "logo_url": get_logo_url()})


@app.get("/register", response_class=HTMLResponse)
def user_register_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/user", status_code=303)
    return templates.TemplateResponse(request=request, name="user_register.html", context={"error": None, "logo_url": get_logo_url()})


@app.post("/register")
def user_register(request: Request, full_name: str = Form(...), email: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):
    full_name = full_name.strip()
    email = email.strip().lower()

    if not full_name:
        return templates.TemplateResponse(request=request, name="user_register.html", context={"error": "Full name is required", "logo_url": get_logo_url()})
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return templates.TemplateResponse(request=request, name="user_register.html", context={"error": "Invalid email address", "logo_url": get_logo_url()})
    if len(password) < 6:
        return templates.TemplateResponse(request=request, name="user_register.html", context={"error": "Password must be at least 6 characters", "logo_url": get_logo_url()})
    if password != confirm_password:
        return templates.TemplateResponse(request=request, name="user_register.html", context={"error": "Passwords do not match", "logo_url": get_logo_url()})

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        db.close()
        return templates.TemplateResponse(request=request, name="user_register.html", context={"error": "Email already registered", "logo_url": get_logo_url()})

    password_hash = hash_password(password)
    db.execute("INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)", (full_name, email, password_hash))
    db.commit()
    db.close()

    return RedirectResponse(url="/login?registered=1", status_code=303)


@app.get("/user", response_class=HTMLResponse)
def user_dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    db = get_db()
    u = db.execute("SELECT balance, created_at FROM users WHERE id = ?", (user["user_id"],)).fetchone()
    balance = u["balance"] if u else 0.00
    joined_date = u["created_at"][:10] if u and u["created_at"] else "N/A"
    posts = db.execute("SELECT * FROM posts WHERE user_id = ? ORDER BY created_at DESC", (user["user_id"],)).fetchall()
    post_list = [{"id": p["id"], "title": p["title"], "description": p["description"], "category": p["category"], "location": p["location"], "price": p["price"], "status": p["status"], "repost_count": p["repost_count"], "created_at": p["created_at"], "updated_at": p["updated_at"]} for p in posts]
    active_count = sum(1 for p in post_list if p["status"] == "active")
    db.close()
    return templates.TemplateResponse(request=request, name="user_dashboard.html", context={"user": user, "logo_url": get_logo_url(), "joined_date": joined_date, "balance": balance, "posts": post_list, "active_count": active_count})


# ─── API: User Posts ─────────────────────────────────────────────────

class PostCreate(BaseModel):
    title: str
    description: str
    category: str = ""
    location: str = ""
    price: str = ""


class PostUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    price: Optional[str] = None


@app.get("/api/posts")
def api_get_user_posts(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    db = get_db()
    posts = db.execute("SELECT * FROM posts WHERE user_id = ? ORDER BY created_at DESC", (user["user_id"],)).fetchall()
    result = [{"id": p["id"], "title": p["title"], "description": p["description"], "category": p["category"], "location": p["location"], "price": p["price"], "status": p["status"], "repost_count": p["repost_count"], "created_at": p["created_at"]} for p in posts]
    db.close()
    return result


@app.post("/api/posts", status_code=201)
def api_create_post(request: Request, data: PostCreate):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    title = data.title.strip()
    description = data.description.strip()
    if not title or not description:
        return JSONResponse({"error": "Title and description are required"}, status_code=400)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO posts (user_id, title, description, category, location, price) VALUES (?, ?, ?, ?, ?, ?)",
        (user["user_id"], title, description, data.category.strip(), data.location.strip(), data.price.strip())
    )
    db.commit()
    post_id = cursor.lastrowid
    db.close()
    return {"id": post_id, "title": title, "description": description, "status": "active"}


@app.put("/api/posts/{post_id}")
def api_update_post(request: Request, post_id: int, data: PostUpdate):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ? AND user_id = ?", (post_id, user["user_id"])).fetchone()
    if not post:
        db.close()
        return JSONResponse({"error": "Post not found"}, status_code=404)
    title = data.title.strip() if data.title else post["title"]
    description = data.description.strip() if data.description else post["description"]
    category = data.category.strip() if data.category is not None else post["category"]
    location = data.location.strip() if data.location is not None else post["location"]
    price = data.price.strip() if data.price is not None else post["price"]
    if not title or not description:
        db.close()
        return JSONResponse({"error": "Title and description are required"}, status_code=400)
    db.execute("UPDATE posts SET title=?, description=?, category=?, location=?, price=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (title, description, category, location, price, post_id))
    db.commit()
    db.close()
    return {"id": post_id, "title": title, "description": description}


@app.post("/api/posts/{post_id}/repost")
def api_repost(request: Request, post_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ? AND user_id = ?", (post_id, user["user_id"])).fetchone()
    if not post:
        db.close()
        return JSONResponse({"error": "Post not found"}, status_code=404)
    db.execute("UPDATE posts SET repost_count = repost_count + 1, updated_at = CURRENT_TIMESTAMP, status = 'active' WHERE id = ?", (post_id,))
    db.commit()
    db.close()
    return {"id": post_id, "repost_count": post["repost_count"] + 1}


@app.delete("/api/posts/{post_id}")
def api_delete_post(request: Request, post_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ? AND user_id = ?", (post_id, user["user_id"])).fetchone()
    if not post:
        db.close()
        return JSONResponse({"error": "Post not found"}, status_code=404)
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    db.commit()
    db.close()
    return {"success": True}


class ChangePassword(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/change-password")
def api_change_password(request: Request, data: ChangePassword):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    db = get_db()
    u = db.execute("SELECT * FROM users WHERE id = ?", (user["user_id"],)).fetchone()
    if not u:
        db.close()
        return JSONResponse({"error": "User not found"}, status_code=404)

    if not verify_password(data.current_password, u["password_hash"]):
        db.close()
        return JSONResponse({"error": "Current password is incorrect"}, status_code=400)

    if len(data.new_password) < 6:
        db.close()
        return JSONResponse({"error": "New password must be at least 6 characters"}, status_code=400)

    new_hash = hash_password(data.new_password)
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["user_id"]))
    db.commit()
    db.close()
    return {"success": True}


@app.get("/logout")
def user_logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(USER_SESSION_COOKIE)
    return response


# ─── Admin Auth ──────────────────────────────────────────────────────

@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})


@app.post("/admin/login")
def admin_login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        token = serializer.dumps({"logged_in": True})
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie(SESSION_COOKIE, token, httponly=True, max_age=86400)
        return response
    return templates.TemplateResponse(request=request, name="login.html", context={"error": "Invalid credentials"})


@app.get("/admin/logout")
def admin_logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


# ─── Admin Dashboard ─────────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    return templates.TemplateResponse(request=request, name="admin.html")


# ─── Pydantic Models ─────────────────────────────────────────────────

class CountryCreate(BaseModel):
    name: str

class StateCreate(BaseModel):
    name: str
    country_id: int

class CityCreate(BaseModel):
    name: str
    state_id: int

class NameUpdate(BaseModel):
    name: str

SAFE_URL_SCHEMES = {"http", "https"}

def is_safe_url(url: str) -> bool:
    if url.startswith("/") and not url.startswith("//"):
        return True
    try:
        parsed = urlparse(url)
        return parsed.scheme.lower() in SAFE_URL_SCHEMES
    except Exception:
        return False


class MenuItemCreate(BaseModel):
    name: str
    url: str

class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None


# ─── API: Countries ──────────────────────────────────────────────────

@app.get("/api/countries")
def api_get_countries():
    db = get_db()
    countries = db.execute(
        "SELECT * FROM countries ORDER BY sort_order, name"
    ).fetchall()
    result = [{"id": c["id"], "name": c["name"]} for c in countries]
    db.close()
    return result


@app.post("/api/countries", status_code=201)
def api_add_country(request: Request, data: CountryCreate):
    require_login(request)
    name = data.name.strip()
    if not name:
        return JSONResponse({"error": "Country name is required"}, status_code=400)

    db = get_db()
    try:
        max_order = db.execute("SELECT MAX(sort_order) FROM countries").fetchone()[0]
        sort_order = (max_order or 0) + 1
        cursor = db.execute(
            "INSERT INTO countries (name, sort_order) VALUES (?, ?)",
            (name, sort_order),
        )
        db.commit()
        country_id = cursor.lastrowid
        db.close()
        return {"id": country_id, "name": name}
    except Exception as e:
        db.close()
        return JSONResponse({"error": str(e)}, status_code=400)


@app.put("/api/countries/{country_id}")
def api_update_country(request: Request, country_id: int, data: NameUpdate):
    require_login(request)
    name = data.name.strip()
    if not name:
        return JSONResponse({"error": "Country name is required"}, status_code=400)

    db = get_db()
    db.execute("UPDATE countries SET name = ? WHERE id = ?", (name, country_id))
    db.commit()
    db.close()
    return {"id": country_id, "name": name}


@app.delete("/api/countries/{country_id}")
def api_delete_country(request: Request, country_id: int):
    require_login(request)
    db = get_db()
    db.execute("DELETE FROM countries WHERE id = ?", (country_id,))
    db.commit()
    db.close()
    return {"success": True}


# ─── API: States ─────────────────────────────────────────────────────

@app.get("/api/states/{country_id}")
def api_get_states(country_id: int):
    db = get_db()
    states = db.execute(
        "SELECT * FROM states WHERE country_id = ? ORDER BY sort_order, name",
        (country_id,),
    ).fetchall()
    result = [{"id": s["id"], "name": s["name"], "country_id": s["country_id"]} for s in states]
    db.close()
    return result


@app.post("/api/states", status_code=201)
def api_add_state(request: Request, data: StateCreate):
    require_login(request)
    name = data.name.strip()
    if not name or not data.country_id:
        return JSONResponse({"error": "State name and country_id are required"}, status_code=400)

    db = get_db()
    try:
        max_order = db.execute(
            "SELECT MAX(sort_order) FROM states WHERE country_id = ?", (data.country_id,)
        ).fetchone()[0]
        sort_order = (max_order or 0) + 1
        cursor = db.execute(
            "INSERT INTO states (name, country_id, sort_order) VALUES (?, ?, ?)",
            (name, data.country_id, sort_order),
        )
        db.commit()
        state_id = cursor.lastrowid
        db.close()
        return {"id": state_id, "name": name, "country_id": data.country_id}
    except Exception as e:
        db.close()
        return JSONResponse({"error": str(e)}, status_code=400)


@app.put("/api/states/{state_id}")
def api_update_state(request: Request, state_id: int, data: NameUpdate):
    require_login(request)
    name = data.name.strip()
    if not name:
        return JSONResponse({"error": "State name is required"}, status_code=400)

    db = get_db()
    db.execute("UPDATE states SET name = ? WHERE id = ?", (name, state_id))
    db.commit()
    db.close()
    return {"id": state_id, "name": name}


@app.delete("/api/states/{state_id}")
def api_delete_state(request: Request, state_id: int):
    require_login(request)
    db = get_db()
    db.execute("DELETE FROM states WHERE id = ?", (state_id,))
    db.commit()
    db.close()
    return {"success": True}


# ─── API: Cities ─────────────────────────────────────────────────────

@app.get("/api/cities/{state_id}")
def api_get_cities(state_id: int):
    db = get_db()
    cities = db.execute(
        "SELECT * FROM cities WHERE state_id = ? ORDER BY sort_order, name",
        (state_id,),
    ).fetchall()
    result = [{"id": c["id"], "name": c["name"], "state_id": c["state_id"]} for c in cities]
    db.close()
    return result


@app.post("/api/cities", status_code=201)
def api_add_city(request: Request, data: CityCreate):
    require_login(request)
    name = data.name.strip()
    if not name or not data.state_id:
        return JSONResponse({"error": "City name and state_id are required"}, status_code=400)

    db = get_db()
    try:
        max_order = db.execute(
            "SELECT MAX(sort_order) FROM cities WHERE state_id = ?", (data.state_id,)
        ).fetchone()[0]
        sort_order = (max_order or 0) + 1
        cursor = db.execute(
            "INSERT INTO cities (name, state_id, sort_order) VALUES (?, ?, ?)",
            (name, data.state_id, sort_order),
        )
        db.commit()
        city_id = cursor.lastrowid
        db.close()
        return {"id": city_id, "name": name, "state_id": data.state_id}
    except Exception as e:
        db.close()
        return JSONResponse({"error": str(e)}, status_code=400)


@app.put("/api/cities/{city_id}")
def api_update_city(request: Request, city_id: int, data: NameUpdate):
    require_login(request)
    name = data.name.strip()
    if not name:
        return JSONResponse({"error": "City name is required"}, status_code=400)

    db = get_db()
    db.execute("UPDATE cities SET name = ? WHERE id = ?", (name, city_id))
    db.commit()
    db.close()
    return {"id": city_id, "name": name}


@app.delete("/api/cities/{city_id}")
def api_delete_city(request: Request, city_id: int):
    require_login(request)
    db = get_db()
    db.execute("DELETE FROM cities WHERE id = ?", (city_id,))
    db.commit()
    db.close()
    return {"success": True}


# ─── API: Full location tree ────────────────────────────────────────

@app.get("/api/locations")
def api_get_all_locations():
    db = get_db()
    countries = db.execute(
        "SELECT * FROM countries ORDER BY sort_order, name"
    ).fetchall()

    result = []
    for country in countries:
        states = db.execute(
            "SELECT * FROM states WHERE country_id = ? ORDER BY sort_order, name",
            (country["id"],),
        ).fetchall()

        state_list = []
        for state in states:
            cities = db.execute(
                "SELECT * FROM cities WHERE state_id = ? ORDER BY sort_order, name",
                (state["id"],),
            ).fetchall()
            state_list.append({
                "id": state["id"],
                "name": state["name"],
                "cities": [{"id": c["id"], "name": c["name"]} for c in cities],
            })

        result.append({
            "id": country["id"],
            "name": country["name"],
            "states": state_list,
        })

    db.close()
    return result


# ─── API: Menu Items ─────────────────────────────────────────────────

@app.get("/api/menu-items")
def api_get_menu_items():
    db = get_db()
    items = db.execute(
        "SELECT * FROM menu_items ORDER BY sort_order, name"
    ).fetchall()
    result = [{"id": m["id"], "name": m["name"], "url": m["url"]} for m in items]
    db.close()
    return result


@app.post("/api/menu-items", status_code=201)
def api_add_menu_item(request: Request, data: MenuItemCreate):
    require_login(request)
    name = data.name.strip()
    url = data.url.strip()
    if not name:
        return JSONResponse({"error": "Menu item name is required"}, status_code=400)
    if not url:
        url = "#"
    if url != "#" and not is_safe_url(url):
        return JSONResponse({"error": "URL must use http:// or https://"}, status_code=400)

    db = get_db()
    try:
        max_order = db.execute("SELECT MAX(sort_order) FROM menu_items").fetchone()[0]
        sort_order = (max_order or 0) + 1
        cursor = db.execute(
            "INSERT INTO menu_items (name, url, sort_order) VALUES (?, ?, ?)",
            (name, url, sort_order),
        )
        db.commit()
        item_id = cursor.lastrowid
        db.close()
        return {"id": item_id, "name": name, "url": url}
    except Exception as e:
        db.close()
        return JSONResponse({"error": str(e)}, status_code=400)


@app.put("/api/menu-items/{item_id}")
def api_update_menu_item(request: Request, item_id: int, data: MenuItemUpdate):
    require_login(request)
    db = get_db()
    item = db.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        db.close()
        return JSONResponse({"error": "Menu item not found"}, status_code=404)

    name = data.name.strip() if data.name else item["name"]
    url = data.url.strip() if data.url else item["url"]

    if not name:
        db.close()
        return JSONResponse({"error": "Menu item name is required"}, status_code=400)
    if url != "#" and not is_safe_url(url):
        db.close()
        return JSONResponse({"error": "URL must use http:// or https://"}, status_code=400)

    db.execute("UPDATE menu_items SET name = ?, url = ? WHERE id = ?", (name, url, item_id))
    db.commit()
    db.close()
    return {"id": item_id, "name": name, "url": url}


@app.delete("/api/menu-items/{item_id}")
def api_delete_menu_item(request: Request, item_id: int):
    require_login(request)
    db = get_db()
    db.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
    db.commit()
    db.close()
    return {"success": True}


# ─── API: Logo Upload ────────────────────────────────────────────────

ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

@app.get("/api/logo")
def api_get_logo():
    logo_url = get_logo_url()
    return {"logo_url": logo_url}


@app.post("/api/logo")
def api_upload_logo(request: Request, file: UploadFile = File(...)):
    require_login(request)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        return JSONResponse({"error": "Invalid file type. Use PNG, JPG, GIF, or WEBP."}, status_code=400)

    # Remove old logo
    if os.path.exists(LOGO_FILE):
        with open(LOGO_FILE, "r") as f:
            old_name = f.read().strip()
        old_path = os.path.join(UPLOADS_DIR, old_name)
        if os.path.exists(old_path):
            os.remove(old_path)

    # Save new logo
    filename = f"logo_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    with open(LOGO_FILE, "w") as f:
        f.write(filename)

    return {"logo_url": f"/uploads/{filename}"}


@app.delete("/api/logo")
def api_delete_logo(request: Request):
    require_login(request)
    if os.path.exists(LOGO_FILE):
        with open(LOGO_FILE, "r") as f:
            old_name = f.read().strip()
        old_path = os.path.join(UPLOADS_DIR, old_name)
        if os.path.exists(old_path):
            os.remove(old_path)
        os.remove(LOGO_FILE)
    return {"success": True}
