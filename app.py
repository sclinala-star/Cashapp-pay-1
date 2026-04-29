from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
from database import get_db, init_db, seed_data

app = Flask(__name__)
app.secret_key = "change-this-in-production-classified-secret-key"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ─── Main Page ───────────────────────────────────────────────────────

@app.route("/")
def index():
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

    db.close()
    return render_template("index.html", locations=location_data)


# ─── Admin Auth ──────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("logged_in", None)
    return redirect(url_for("admin_login"))


# ─── Admin Dashboard ─────────────────────────────────────────────────

@app.route("/admin")
@login_required
def admin_dashboard():
    return render_template("admin.html")


# ─── API: Countries ──────────────────────────────────────────────────

@app.route("/api/countries", methods=["GET"])
def api_get_countries():
    db = get_db()
    countries = db.execute(
        "SELECT * FROM countries ORDER BY sort_order, name"
    ).fetchall()
    result = [{"id": c["id"], "name": c["name"]} for c in countries]
    db.close()
    return jsonify(result)


@app.route("/api/countries", methods=["POST"])
@login_required
def api_add_country():
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Country name is required"}), 400

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
        return jsonify({"id": country_id, "name": name}), 201
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 400


@app.route("/api/countries/<int:country_id>", methods=["PUT"])
@login_required
def api_update_country(country_id):
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Country name is required"}), 400

    db = get_db()
    db.execute("UPDATE countries SET name = ? WHERE id = ?", (name, country_id))
    db.commit()
    db.close()
    return jsonify({"id": country_id, "name": name})


@app.route("/api/countries/<int:country_id>", methods=["DELETE"])
@login_required
def api_delete_country(country_id):
    db = get_db()
    db.execute("DELETE FROM countries WHERE id = ?", (country_id,))
    db.commit()
    db.close()
    return jsonify({"success": True})


# ─── API: States ─────────────────────────────────────────────────────

@app.route("/api/states/<int:country_id>", methods=["GET"])
def api_get_states(country_id):
    db = get_db()
    states = db.execute(
        "SELECT * FROM states WHERE country_id = ? ORDER BY sort_order, name",
        (country_id,),
    ).fetchall()
    result = [{"id": s["id"], "name": s["name"], "country_id": s["country_id"]} for s in states]
    db.close()
    return jsonify(result)


@app.route("/api/states", methods=["POST"])
@login_required
def api_add_state():
    data = request.get_json()
    name = data.get("name", "").strip()
    country_id = data.get("country_id")
    if not name or not country_id:
        return jsonify({"error": "State name and country_id are required"}), 400

    db = get_db()
    try:
        max_order = db.execute(
            "SELECT MAX(sort_order) FROM states WHERE country_id = ?", (country_id,)
        ).fetchone()[0]
        sort_order = (max_order or 0) + 1
        cursor = db.execute(
            "INSERT INTO states (name, country_id, sort_order) VALUES (?, ?, ?)",
            (name, country_id, sort_order),
        )
        db.commit()
        state_id = cursor.lastrowid
        db.close()
        return jsonify({"id": state_id, "name": name, "country_id": country_id}), 201
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 400


@app.route("/api/states/<int:state_id>", methods=["PUT"])
@login_required
def api_update_state(state_id):
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "State name is required"}), 400

    db = get_db()
    db.execute("UPDATE states SET name = ? WHERE id = ?", (name, state_id))
    db.commit()
    db.close()
    return jsonify({"id": state_id, "name": name})


@app.route("/api/states/<int:state_id>", methods=["DELETE"])
@login_required
def api_delete_state(state_id):
    db = get_db()
    db.execute("DELETE FROM states WHERE id = ?", (state_id,))
    db.commit()
    db.close()
    return jsonify({"success": True})


# ─── API: Cities ─────────────────────────────────────────────────────

@app.route("/api/cities/<int:state_id>", methods=["GET"])
def api_get_cities(state_id):
    db = get_db()
    cities = db.execute(
        "SELECT * FROM cities WHERE state_id = ? ORDER BY sort_order, name",
        (state_id,),
    ).fetchall()
    result = [{"id": c["id"], "name": c["name"], "state_id": c["state_id"]} for c in cities]
    db.close()
    return jsonify(result)


@app.route("/api/cities", methods=["POST"])
@login_required
def api_add_city():
    data = request.get_json()
    name = data.get("name", "").strip()
    state_id = data.get("state_id")
    if not name or not state_id:
        return jsonify({"error": "City name and state_id are required"}), 400

    db = get_db()
    try:
        max_order = db.execute(
            "SELECT MAX(sort_order) FROM cities WHERE state_id = ?", (state_id,)
        ).fetchone()[0]
        sort_order = (max_order or 0) + 1
        cursor = db.execute(
            "INSERT INTO cities (name, state_id, sort_order) VALUES (?, ?, ?)",
            (name, state_id, sort_order),
        )
        db.commit()
        city_id = cursor.lastrowid
        db.close()
        return jsonify({"id": city_id, "name": name, "state_id": state_id}), 201
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 400


@app.route("/api/cities/<int:city_id>", methods=["PUT"])
@login_required
def api_update_city(city_id):
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "City name is required"}), 400

    db = get_db()
    db.execute("UPDATE cities SET name = ? WHERE id = ?", (name, city_id))
    db.commit()
    db.close()
    return jsonify({"id": city_id, "name": name})


@app.route("/api/cities/<int:city_id>", methods=["DELETE"])
@login_required
def api_delete_city(city_id):
    db = get_db()
    db.execute("DELETE FROM cities WHERE id = ?", (city_id,))
    db.commit()
    db.close()
    return jsonify({"success": True})


# ─── API: Full location tree (for admin) ────────────────────────────

@app.route("/api/locations", methods=["GET"])
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
    return jsonify(result)


if __name__ == "__main__":
    init_db()
    seed_data()
    app.run(debug=True, port=5000)
