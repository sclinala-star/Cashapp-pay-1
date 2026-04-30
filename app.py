from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from itsdangerous import URLSafeSerializer
from typing import Optional
import os

from database import get_db, init_db, seed_data

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
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
    return templates.TemplateResponse(request=request, name="index.html", context={"locations": location_data, "menu_items": menu_list})


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
