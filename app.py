from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from itsdangerous import URLSafeSerializer
from typing import Optional, List
from urllib.parse import urlparse
import os
import shutil
import uuid
import hashlib
import re

from database import get_db, init_db, seed_data

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
MEDIA_DIR = os.path.join(DATA_DIR, "media")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production-classified-secret-key")
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
    if ":" not in stored:
        return False
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
    user = get_current_user(request)
    return templates.TemplateResponse(request=request, name="index.html", context={"locations": location_data, "menu_items": menu_list, "logo_url": logo_url, "user": user})


# ─── City Page ────────────────────────────────────────────────────────

@app.get("/city/{city_name}", response_class=HTMLResponse)
def city_page(request: Request, city_name: str):
    from urllib.parse import unquote
    city_name = unquote(city_name)
    db = get_db()
    posts = db.execute(
        "SELECT * FROM posts WHERE city = ? AND status = 'active' ORDER BY created_at DESC",
        (city_name,)
    ).fetchall()
    post_list = [dict(p) for p in posts]
    menu_items = db.execute("SELECT * FROM menu_items ORDER BY sort_order, name").fetchall()
    menu_list = [{"id": m["id"], "name": m["name"], "url": m["url"]} for m in menu_items]
    # Find country and state for breadcrumb
    city_row = db.execute("SELECT c.name as city_name, s.name as state_name, co.name as country_name FROM cities c JOIN states s ON c.state_id = s.id JOIN countries co ON s.country_id = co.id WHERE c.name = ?", (city_name,)).fetchone()
    country_name = city_row["country_name"] if city_row else ""
    state_name = city_row["state_name"] if city_row else ""
    categories = db.execute("SELECT * FROM categories ORDER BY sort_order, name").fetchall()
    cat_list = [{"id": c["id"], "name": c["name"], "color": c["color"]} for c in categories]
    db.close()
    logo_url = get_logo_url()
    return templates.TemplateResponse(request=request, name="city.html", context={"city_name": city_name, "posts": post_list, "logo_url": logo_url, "menu_items": menu_list, "country_name": country_name, "state_name": state_name, "categories": cat_list})


# ─── View Ads Page ───────────────────────────────────────────────────

@app.get("/{country}/{state}/{city}/{category}/viewads", response_class=HTMLResponse)
def view_ads_page(request: Request, country: str, state: str, city: str, category: str):
    from urllib.parse import unquote
    country = unquote(country)
    state = unquote(state)
    city = unquote(city)
    category = unquote(category)
    db = get_db()
    posts = db.execute(
        "SELECT * FROM posts WHERE city = ? AND (i_am = ? OR i_see = ?) AND status = 'active' ORDER BY created_at DESC",
        (city, category, category)
    ).fetchall()
    post_list = [dict(p) for p in posts]
    categories = db.execute("SELECT * FROM categories ORDER BY sort_order, name").fetchall()
    cat_list = [{"id": c["id"], "name": c["name"], "color": c["color"]} for c in categories]
    db.close()
    logo_url = get_logo_url()
    left_banners, right_banners = get_active_banners()
    return templates.TemplateResponse(request=request, name="viewads.html", context={
        "city_name": city, "state_name": state, "country_name": country,
        "posts": post_list, "logo_url": logo_url, "categories": cat_list,
        "current_cat": category, "left_banners": left_banners, "right_banners": right_banners
    })


# ─── Ad Detail ────────────────────────────────────────────────────────

@app.get("/ad/{post_id}", response_class=HTMLResponse)
def ad_detail_page(request: Request, post_id: int):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ? AND status = 'active'", (post_id,)).fetchone()
    if not post:
        db.close()
        return HTMLResponse("<h2>Ad not found</h2><a href='/'>Go Home</a>", status_code=404)
    photos = db.execute("SELECT * FROM post_media WHERE post_id = ? AND media_type = 'photo' ORDER BY slot", (post_id,)).fetchall()
    videos = db.execute("SELECT * FROM post_media WHERE post_id = ? AND media_type = 'video' ORDER BY slot", (post_id,)).fetchall()
    db.close()
    return templates.TemplateResponse(request=request, name="ad_detail.html", context={
        "post": dict(post),
        "photos": [dict(p) for p in photos],
        "videos": [dict(v) for v in videos],
        "logo_url": get_logo_url()
    })


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
    clean_email = email.strip().lower()
    user = db.execute("SELECT * FROM users WHERE email = ?", (clean_email,)).fetchone()
    db.close()

    if not user:
        return templates.TemplateResponse(request=request, name="user_login.html", context={"error": "No account found with this email. Please register first.", "logo_url": get_logo_url()})

    if not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(request=request, name="user_login.html", context={"error": "Incorrect password. Please try again.", "logo_url": get_logo_url()})

    token = serializer.dumps({"user_id": user["id"], "full_name": user["full_name"], "email": user["email"]})
    response = RedirectResponse(url="/user", status_code=303)
    response.set_cookie(USER_SESSION_COOKIE, token, httponly=True, max_age=86400)
    return response


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
    post_list = [{"id": p["id"], "i_am": p["i_am"], "i_see": p["i_see"], "name_alias": p["name_alias"], "age": p["age"], "headline": p["headline"], "body": p["body"], "city": p["city"], "phone_code": p["phone_code"], "phone": p["phone"], "location_area": p["location_area"], "status": p["status"], "repost_count": p["repost_count"], "created_at": p["created_at"], "updated_at": p["updated_at"]} for p in posts]
    active_count = sum(1 for p in post_list if p["status"] == "active")
    categories = db.execute("SELECT * FROM categories ORDER BY sort_order, name").fetchall()
    cat_list = [{"id": c["id"], "name": c["name"], "color": c["color"]} for c in categories]
    db.close()
    design = get_design_settings()
    return templates.TemplateResponse(request=request, name="user_dashboard.html", context={"user": user, "logo_url": get_logo_url(), "joined_date": joined_date, "balance": balance, "posts": post_list, "active_count": active_count, "categories": cat_list, "design": design})


# ─── API: User Posts ─────────────────────────────────────────────────

class PostCreate(BaseModel):
    i_am: str = ""
    i_see: str = ""
    name_alias: str = ""
    age: str = ""
    headline: str
    body: str
    city: str = ""
    phone_code: str = "+1"
    phone: str = ""
    location_area: str = ""


class PostUpdate(BaseModel):
    i_am: Optional[str] = None
    i_see: Optional[str] = None
    name_alias: Optional[str] = None
    age: Optional[str] = None
    headline: Optional[str] = None
    body: Optional[str] = None
    city: Optional[str] = None
    phone_code: Optional[str] = None
    phone: Optional[str] = None
    location_area: Optional[str] = None


@app.get("/api/posts")
def api_get_user_posts(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    db = get_db()
    posts = db.execute("SELECT * FROM posts WHERE user_id = ? ORDER BY created_at DESC", (user["user_id"],)).fetchall()
    result = [{"id": p["id"], "headline": p["headline"], "body": p["body"], "city": p["city"], "status": p["status"], "repost_count": p["repost_count"], "created_at": p["created_at"]} for p in posts]
    db.close()
    return result


@app.post("/api/posts", status_code=201)
async def api_create_post(
    request: Request,
    i_am: str = Form(""),
    i_see: str = Form(""),
    name_alias: str = Form(""),
    age: str = Form(""),
    headline: str = Form(""),
    body: str = Form(""),
    city: str = Form(""),
    phone_code: str = Form("+1"),
    phone: str = Form(""),
    location_area: str = Form(""),
    photos: List[UploadFile] = File(None),
    videos: List[UploadFile] = File(None),
):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    headline = headline.strip()
    body_text = body.strip()
    if not headline or not body_text:
        return JSONResponse({"error": "Headline and body are required"}, status_code=400)
    db = get_db()
    db_user = db.execute("SELECT id FROM users WHERE id = ?", (user["user_id"],)).fetchone()
    if not db_user:
        db.close()
        return JSONResponse({"error": "Session expired. Please login again."}, status_code=401)
    ALLOWED_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
    try:
        cursor = db.execute(
            "INSERT INTO posts (user_id, i_am, i_see, name_alias, age, headline, body, city, phone_code, phone, location_area) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user["user_id"], i_am.strip(), i_see.strip(), name_alias.strip(), age.strip(), headline, body_text, city.strip(), phone_code.strip(), phone.strip(), location_area.strip())
        )
        post_id = cursor.lastrowid

        slot = 0
        if photos:
            for photo in photos:
                if photo.filename:
                    ext = os.path.splitext(photo.filename)[1].lower() or ".jpg"
                    if ext not in ALLOWED_PHOTO_EXT:
                        continue
                    fname = f"post_{post_id}_photo_{slot}_{uuid.uuid4().hex[:8]}{ext}"
                    fpath = os.path.join(MEDIA_DIR, fname)
                    content = await photo.read()
                    with open(fpath, "wb") as f:
                        f.write(content)
                    db.execute("INSERT INTO post_media (post_id, media_type, filename, slot) VALUES (?, 'photo', ?, ?)", (post_id, fname, slot))
                    slot += 1
        slot = 0
        if videos:
            for video in videos:
                if video.filename:
                    ext = os.path.splitext(video.filename)[1].lower() or ".mp4"
                    if ext not in ALLOWED_VIDEO_EXT:
                        continue
                    fname = f"post_{post_id}_video_{slot}_{uuid.uuid4().hex[:8]}{ext}"
                    fpath = os.path.join(MEDIA_DIR, fname)
                    content = await video.read()
                    with open(fpath, "wb") as f:
                        f.write(content)
                    db.execute("INSERT INTO post_media (post_id, media_type, filename, slot) VALUES (?, 'video', ?, ?)", (post_id, fname, slot))
                    slot += 1
        db.commit()
        db.close()
        return {"id": post_id, "headline": headline, "status": "active"}
    except Exception as e:
        db.rollback()
        db.close()
        return JSONResponse({"error": str(e)}, status_code=500)


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
    i_am = data.i_am.strip() if data.i_am is not None else post["i_am"]
    i_see = data.i_see.strip() if data.i_see is not None else post["i_see"]
    name_alias = data.name_alias.strip() if data.name_alias is not None else post["name_alias"]
    age = data.age.strip() if data.age is not None else post["age"]
    headline = data.headline.strip() if data.headline is not None else post["headline"]
    body = data.body.strip() if data.body is not None else post["body"]
    city = data.city.strip() if data.city is not None else post["city"]
    phone_code = data.phone_code.strip() if data.phone_code is not None else post["phone_code"]
    phone = data.phone.strip() if data.phone is not None else post["phone"]
    location_area = data.location_area.strip() if data.location_area is not None else post["location_area"]
    if not headline or not body:
        db.close()
        return JSONResponse({"error": "Headline and body are required"}, status_code=400)
    db.execute("UPDATE posts SET i_am=?, i_see=?, name_alias=?, age=?, headline=?, body=?, city=?, phone_code=?, phone=?, location_area=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (i_am, i_see, name_alias, age, headline, body, city, phone_code, phone, location_area, post_id))
    db.commit()
    db.close()
    return {"id": post_id, "headline": headline}


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

class CategoryCreate(BaseModel):
    name: str
    color: str = "#daa520"

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


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


# ─── API: Categories ─────────────────────────────────────────────────

@app.get("/api/categories")
def api_get_categories():
    db = get_db()
    items = db.execute("SELECT * FROM categories ORDER BY sort_order, name").fetchall()
    db.close()
    return [{"id": c["id"], "name": c["name"], "color": c["color"]} for c in items]

@app.post("/api/categories", status_code=201)
def api_add_category(request: Request, data: CategoryCreate):
    require_login(request)
    name = data.name.strip()
    if not name:
        return JSONResponse({"error": "Name required"}, status_code=400)
    db = get_db()
    try:
        max_order = db.execute("SELECT MAX(sort_order) FROM categories").fetchone()[0]
        sort_order = (max_order or 0) + 1
        cursor = db.execute("INSERT INTO categories (name, color, sort_order) VALUES (?, ?, ?)", (name, data.color.strip(), sort_order))
        db.commit()
        cat_id = cursor.lastrowid
        db.close()
        return {"id": cat_id, "name": name, "color": data.color.strip()}
    except Exception:
        db.close()
        return JSONResponse({"error": "Category already exists"}, status_code=400)

@app.put("/api/categories/{cat_id}")
def api_update_category(request: Request, cat_id: int, data: CategoryUpdate):
    require_login(request)
    db = get_db()
    cat = db.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)).fetchone()
    if not cat:
        db.close()
        raise HTTPException(status_code=404, detail="Category not found")
    name = (data.name.strip() if data.name else cat["name"])
    color = (data.color.strip() if data.color else cat["color"])
    db.execute("UPDATE categories SET name = ?, color = ? WHERE id = ?", (name, color, cat_id))
    db.commit()
    db.close()
    return {"id": cat_id, "name": name, "color": color}

@app.delete("/api/categories/{cat_id}")
def api_delete_category(request: Request, cat_id: int):
    require_login(request)
    db = get_db()
    db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
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


# ─── API: Admin User Management ──────────────────────────────────────

@app.get("/api/admin/users")
def api_admin_users(request: Request):
    require_login(request)
    db = get_db()
    users = db.execute("SELECT id, full_name, email, balance, created_at FROM users ORDER BY created_at DESC").fetchall()
    result = []
    for u in users:
        total = db.execute("SELECT COUNT(*) as cnt FROM posts WHERE user_id = ?", (u["id"],)).fetchone()["cnt"]
        active = db.execute("SELECT COUNT(*) as cnt FROM posts WHERE user_id = ? AND status = 'active'", (u["id"],)).fetchone()["cnt"]
        draft = total - active
        result.append({
            "id": u["id"],
            "full_name": u["full_name"],
            "email": u["email"],
            "balance": u["balance"],
            "total_posts": total,
            "active_posts": active,
            "draft_posts": draft,
            "created_at": u["created_at"]
        })
    db.close()
    return result


@app.get("/api/admin/users/{user_id}")
def api_admin_user_detail(request: Request, user_id: int):
    require_login(request)
    db = get_db()
    u = db.execute("SELECT id, full_name, email, balance, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    if not u:
        db.close()
        return JSONResponse({"error": "User not found"}, status_code=404)
    posts = db.execute("SELECT id, headline, body, city, i_am, i_see, status, repost_count, created_at FROM posts WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    post_list = [dict(p) for p in posts]
    db.close()
    return {
        "user": {"id": u["id"], "full_name": u["full_name"], "email": u["email"], "balance": u["balance"], "created_at": u["created_at"]},
        "posts": post_list
    }


@app.put("/api/admin/users/{user_id}/balance")
def api_admin_update_balance(request: Request, user_id: int, data: dict):
    require_login(request)
    new_balance = data.get("balance", 0)
    db = get_db()
    db.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
    db.commit()
    db.close()
    return {"success": True}


# ─── API: Site Design Settings ───────────────────────────────────────

DEFAULT_DESIGN = {
    "sidebar_bg": "#1a1a2e",
    "sidebar_text": "#ffffff",
    "sidebar_active_bg": "#daa520",
    "sidebar_active_text": "#1a1a2e",
    "header_bg": "#16213e",
    "header_text": "#ffffff",
    "page_bg": "#f0f2f5",
    "card_bg": "#ffffff",
    "card_text": "#333333",
    "accent_color": "#daa520",
    "btn_primary_bg": "#daa520",
    "btn_primary_text": "#1a1a2e",
    "btn_danger_bg": "#dc3545",
    "btn_danger_text": "#ffffff",
    "stats_color1": "#4caf50",
    "stats_color2": "#2196f3",
    "stats_color3": "#ff9800",
    "stats_color4": "#e91e63",
    "table_header_bg": "#f8f9fa",
    "table_border": "#dee2e6",
    "link_color": "#daa520",
    "font_family": "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
}

def get_design_settings():
    db = get_db()
    rows = db.execute("SELECT key, value FROM site_settings WHERE key LIKE 'design_%'").fetchall()
    db.close()
    settings = dict(DEFAULT_DESIGN)
    for r in rows:
        k = r["key"].replace("design_", "", 1)
        settings[k] = r["value"]
    return settings


@app.get("/api/admin/design")
def api_get_design(request: Request):
    require_login(request)
    return get_design_settings()


@app.put("/api/admin/design")
def api_save_design(request: Request, data: dict):
    require_login(request)
    db = get_db()
    for key, value in data.items():
        if key in DEFAULT_DESIGN:
            db.execute("INSERT OR REPLACE INTO site_settings (key, value) VALUES (?, ?)", (f"design_{key}", value))
    db.commit()
    db.close()
    return {"success": True}


@app.post("/api/admin/design/reset")
def api_reset_design(request: Request):
    require_login(request)
    db = get_db()
    db.execute("DELETE FROM site_settings WHERE key LIKE 'design_%'")
    db.commit()
    db.close()
    return {"success": True}


# ─── API: Ad Banners ─────────────────────────────────────────────────

@app.get("/api/admin/banners")
def api_get_banners(request: Request):
    require_login(request)
    db = get_db()
    banners = db.execute("SELECT * FROM ad_banners ORDER BY position, sort_order").fetchall()
    db.close()
    return [{"id": b["id"], "position": b["position"], "title": b["title"], "image_url": b["image_url"], "link_url": b["link_url"], "is_active": b["is_active"], "sort_order": b["sort_order"]} for b in banners]


@app.post("/api/admin/banners")
def api_add_banner(request: Request, position: str = Form("left"), title: str = Form(""), image_url: str = Form(""), link_url: str = Form("")):
    require_login(request)
    db = get_db()
    db.execute("INSERT INTO ad_banners (position, title, image_url, link_url) VALUES (?, ?, ?, ?)", (position, title, image_url, link_url))
    db.commit()
    db.close()
    return {"success": True}


@app.put("/api/admin/banners/{banner_id}")
def api_update_banner(request: Request, banner_id: int, data: dict):
    require_login(request)
    db = get_db()
    db.execute("UPDATE ad_banners SET position=?, title=?, image_url=?, link_url=?, is_active=? WHERE id=?",
               (data.get("position", "left"), data.get("title", ""), data.get("image_url", ""), data.get("link_url", ""), data.get("is_active", 1), banner_id))
    db.commit()
    db.close()
    return {"success": True}


@app.delete("/api/admin/banners/{banner_id}")
def api_delete_banner(request: Request, banner_id: int):
    require_login(request)
    db = get_db()
    db.execute("DELETE FROM ad_banners WHERE id = ?", (banner_id,))
    db.commit()
    db.close()
    return {"success": True}


def get_active_banners():
    db = get_db()
    banners = db.execute("SELECT * FROM ad_banners WHERE is_active = 1 ORDER BY position, sort_order").fetchall()
    db.close()
    left = [{"id": b["id"], "title": b["title"], "image_url": b["image_url"], "link_url": b["link_url"]} for b in banners if b["position"] == "left"]
    right = [{"id": b["id"], "title": b["title"], "image_url": b["image_url"], "link_url": b["link_url"]} for b in banners if b["position"] == "right"]
    return left, right
