# Classified Ads - Location Directory

A classified ads website with a location directory showing countries, states, and cities. Includes an admin dashboard for dynamic management.

## Live Site

**https://classified-website-mympkbeo.fly.dev/**

## Features

- **Main Page**: Browse locations organized by Country > State > City (pink/magenta themed)
- **Admin Dashboard**: Login-protected panel to add, edit, and delete countries, states, and cities
- **REST API**: Full CRUD endpoints for all location entities
- **SQLite Database**: Lightweight, file-based storage with seed data

## Setup (Local Development)

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

The app runs at `http://localhost:8000`

## Admin Login

- **Username**: `admin`
- **Password**: `admin123`
- **URL**: `/admin`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/countries` | List all countries |
| POST | `/api/countries` | Add a country |
| PUT | `/api/countries/<id>` | Update a country |
| DELETE | `/api/countries/<id>` | Delete a country |
| GET | `/api/states/<country_id>` | List states for a country |
| POST | `/api/states` | Add a state |
| PUT | `/api/states/<id>` | Update a state |
| DELETE | `/api/states/<id>` | Delete a state |
| GET | `/api/cities/<state_id>` | List cities for a state |
| POST | `/api/cities` | Add a city |
| PUT | `/api/cities/<id>` | Update a city |
| DELETE | `/api/cities/<id>` | Delete a city |
| GET | `/api/locations` | Full location tree |
