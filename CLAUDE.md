# VoteCouncil

Voter management and election-day tracking PWA for Maldivian elections.

## Tech Stack

- **Backend:** FastAPI 0.115.6 + SQLAlchemy + SQLite (WAL mode)
- **Auth:** JWT (python-jose, HS256) + bcrypt, HTTP-only cookies with SameSite=Lax
- **Frontend:** Jinja2 templates + Bootstrap 5.3.2 + custom JS (Maldivian theme)
- **PWA:** Service Worker with offline vote queueing, IndexedDB, auto-update
- **Excel Import/Export:** openpyxl (import with image extraction via Pillow, export with styled headers)
- **Docker:** uvicorn with 4 workers, port 80 for Cloudflare compatibility

## Running

```bash
pip install -r requirements.txt
python run.py
# → http://localhost:8000
# Default login: admin / admin123
```

### Docker

```bash
docker-compose up --build
# → http://localhost:80
```

## Project Structure

```
app/
├── main.py              # FastAPI app, security headers, error logging, auth redirect middleware
├── config.py            # Settings (DB URL, JWT secret, upload limits, DEBUG=False)
├── database.py          # SQLAlchemy engine (WAL mode, pool_size=20, 64MB cache)
├── models/              # ORM models (user, voter, box, focal, candidate, log)
├── routers/
│   ├── auth.py          # Login/logout/user management/password change
│   ├── voters.py        # Voter CRUD, filtering, CSV/PDF export, print, bulk pledge
│   ├── voting.py        # Election-day marking (search by Box#, 2-step flow)
│   ├── dashboard.py     # Stats & overview (focal-scoped for focal users)
│   ├── reports.py       # Analytics, charts, candidate votes, CSV export
│   ├── import_data.py   # Excel import/export, sample file download
│   ├── admin.py         # Logs, data reset
│   ├── focals.py, candidates.py, boxes.py, pages.py
├── schemas/             # Pydantic request/response models
├── services/            # Business logic (auth, excel_import, logging, photo)
└── templates/           # Jinja2 HTML templates
    ├── base.html        # Nav with role-based menu, offline indicator
    ├── login.html, dashboard.html, import.html, change_password.html
    ├── voters/          # list, detail, form, print, pdf
    ├── voting/          # mark (2-step: voted? → who for?)
    ├── manage/          # focals, boxes, candidates, users
    ├── reports/         # index (charts, candidate rankings, tables)
    └── admin/           # logs, reset
static/
├── css/style.css        # Maldivian theme (ocean blue, flag red/green, sand tones)
├── js/app.js            # Toast, PWA registration with auto-update, escapeHtml, offline support
├── sw.js                # Service worker (offline vote queueing, cache-first for static)
├── manifest.json, icons/
uploads/                 # Voter photos
Sample Data/             # Example Excel import file
Dockerfile, docker-compose.yml
cloudflare-firewall.sh   # Restrict port 80 to Cloudflare IPs only
```

## Roles & Permissions

| Feature | Admin | Operator | Focal |
|---------|-------|----------|-------|
| Dashboard | Full | Full | Own voters only |
| Voters list | Full + pledge edit | View only | View only |
| Vote Day | Yes | Yes | No |
| Reports | Yes | Yes | Yes |
| Manage (boxes/focals/candidates) | Yes | No | No |
| Import/Export data | Yes | No | No |
| Users / Admin | Yes | No | No |

## Key Patterns

- **Routers** serve both HTML pages and JSON API endpoints
- **Auth:** `get_current_user` (optional), `get_current_user_required` (mandatory), `require_role()` factory
- **Voting page** (`/voting`): search by Box# with cached prefix (e.g. set "B2." once, then type number). Exact match only. 2-step flow: voted? → select candidate or "Not Disclosed"
- **Pledge status:** 3-state enum (yes/no/undecided), not boolean. Admin can bulk-update via checkboxes
- **Focal dashboard:** focal users see only their assigned voters' stats
- **Focals** sorted alphabetically by default
- **Security headers:** CSP, X-Frame-Options, XSS-Protection, Referrer-Policy
- **XSS protection:** `escapeHtml()` on all dynamic content in JS templates
- **Activity logging:** startup, errors, login attempts, vote changes tracked with IP
- **PWA auto-update:** checks for new service worker version on every page load, reloads automatically
- **Offline support:** vote marks queued in IndexedDB when offline, synced on reconnect

## Database Models

| Model | Key Fields |
|-------|-----------|
| User | username, password_hash, role (admin/focal/operator) |
| Voter | ec_number, voter_id, national_id, name, gender, age, party, address, contact, new_contact, previous_island, previous_address, current_location, box_number, zone, focal_comment, remarks, box_id, is_pledged (PledgeStatus enum), vote_status, voted_for, voted_at, photo_path |
| Box | name, location → has many voters |
| Focal | name, phone, user_id → many-to-many with voters |
| Candidate | name, party, number, is_pledged (boolean - one pledged candidate) |
| ActivityLog | timestamp, user_id, username, action, entity_type, entity_id, details, ip_address |

**Enums:** `VoteStatus` (not_voted, voted_pledged, voted_other, undecided), `PledgeStatus` (yes, no, undecided), `UserRole` (admin, focal, operator)

## Commands

```bash
python run.py                    # Dev server (port 8000, auto-reload)
docker-compose up --build        # Docker (port 80, 4 workers)
docker-compose build --no-cache  # Rebuild after code changes
./cloudflare-firewall.sh         # Lock port 80 to Cloudflare IPs
```

## Security Notes

- JWT SECRET_KEY in config.py / docker-compose env must be changed for production
- CORS allows all origins but credentials=False (safe)
- Debug mode defaults to False
- Passwords hashed with bcrypt via passlib
- Login attempts (success/failure) logged with IP
- Cookie: httponly=True, samesite=Lax
- Default credentials (admin/admin123) not shown on login page
