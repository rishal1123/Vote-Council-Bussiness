# VoteCouncil

Voter management and election-day tracking PWA.

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy + SQLite (`votecouncil.db`)
- **Auth:** JWT (python-jose, HS256) + bcrypt, stored in HTTP-only cookies
- **Frontend:** Jinja2 templates + Bootstrap 5.3.2 + custom JS
- **PWA:** Service Worker + manifest for offline/installable support
- **Excel Import:** openpyxl (with embedded image extraction via Pillow)

## Running

```bash
pip install -r requirements.txt
python run.py
# → http://localhost:8000
# Default login: admin / admin123
```

## Project Structure

```
app/
├── main.py              # FastAPI app init, middleware, static mounts
├── config.py            # Settings (DB URL, JWT secret, upload limits)
├── database.py          # SQLAlchemy engine/session setup
├── models/              # ORM models (user, voter, box, focal, candidate, log)
├── routers/             # Route handlers per resource
│   ├── auth.py          # Login/logout/user management
│   ├── voters.py        # Voter CRUD + filtering
│   ├── voting.py        # Election-day marking + search
│   ├── dashboard.py     # Stats & overview
│   ├── reports.py       # Analytics
│   ├── import_data.py   # Excel import
│   ├── admin.py         # Logs, data reset
│   ├── focals.py, candidates.py, boxes.py, pages.py
├── schemas/             # Pydantic request/response models
├── services/            # Business logic (auth, excel_import, logging, photo)
└── templates/           # Jinja2 HTML (base, login, dashboard, voters/, voting/, manage/, reports/, admin/)
static/                  # CSS, JS, PWA icons, manifest.json, sw.js
uploads/                 # Voter photos
Sample Data/             # Example Excel import file
```

## Key Patterns

- **Routers** serve both HTML pages and JSON API endpoints
- **Auth dependencies:** `get_current_user` (optional), `get_current_user_required` (mandatory), `require_role()` factory
- **Roles:** admin (full access), focal (assigned voters), operator (election-day marking)
- **Database:** SQLAlchemy declarative models with relationship definitions; session via dependency injection
- **Activity logging:** centralized service tracking user/action/entity/IP for audit
- **Voting page** (`/voting`): search by national ID only (no name search)
- **Focals** are sorted alphabetically by name by default

## Database Models

| Model | Key Fields |
|-------|-----------|
| User | username, password_hash, role (admin/focal/operator) |
| Voter | ec_number, voter_id, national_id, name, gender, age, party, address, contact, new_contact, previous_island, previous_address, current_location, box_number, zone, focal_comment, remarks, box_id, is_pledged, vote_status, voted_for, photo_path |
| Box | name, location → has many voters |
| Focal | name, phone, user_id → many-to-many with voters |
| Candidate | name, party, number, is_pledged |
| ActivityLog | timestamp, user_id, username, action, entity_type, entity_id, details, ip_address |

**Enums:** `VoteStatus` (not_voted, voted_pledged, voted_other, undecided), `UserRole` (admin, focal, operator)

## Commands

```bash
python run.py          # Start dev server (port 8000, auto-reload)
```

## Security Notes

- JWT SECRET_KEY in config.py must be changed for production
- CORS is open (all origins) — restrict for production
- Passwords hashed with bcrypt via passlib
