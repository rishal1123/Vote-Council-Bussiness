# VoteCouncil

Voter management and election-day tracking PWA for Maldivian elections.

## Tech Stack

- **Backend:** FastAPI 0.115.6 + SQLAlchemy + SQLite (WAL mode)
- **Auth:** JWT (python-jose, HS256) + bcrypt, HTTP-only cookies with SameSite=Lax
- **Frontend:** Jinja2 templates + Bootstrap 5.3.2 + custom JS (Maldivian theme)
- **PWA:** Service Worker with offline vote queueing, IndexedDB, auto-update on every page load
- **Excel Import/Export:** openpyxl (import with image extraction via Pillow, export with styled headers)
- **Docker:** uvicorn with 4 workers, port 80 for Cloudflare compatibility, auto-restart

## Running

```bash
pip install -r requirements.txt
python run.py
# → http://localhost:8000
# Default login: admin / admin123
```

### Docker

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
# → http://localhost:80
```

**Important:** After code changes, always `docker-compose build --no-cache` — cached layers use old code. On Windows dev, delete `__pycache__` dirs and restart to avoid stale `.pyc` issues.

## Project Structure

```
app/
├── main.py              # FastAPI app, security headers (CSP, XSS, CORS), error/auth middleware
├── config.py            # Settings (DB URL, JWT secret, upload limits, DEBUG=False)
├── database.py          # SQLAlchemy engine (WAL mode, pool_size=5, 30s timeout)
├── models/              # ORM models (user, voter, box, focal, candidate, log)
├── routers/
│   ├── auth.py          # Login/logout/user CRUD/password reset/change
│   ├── voters.py        # Voter CRUD, filtering, CSV/PDF export, print, bulk pledge
│   ├── voting.py        # Election-day marking (Box# prefix + National ID search, 2-step flow)
│   ├── dashboard.py     # Stats & overview (focal-scoped for focal users, auto-refresh)
│   ├── reports.py       # Analytics, charts, candidate votes, CSV export
│   ├── import_data.py   # Excel import (duplicate detection), export, sample file download
│   ├── admin.py         # Logs, column settings, backups, system stats, voting toggle, data reset
│   ├── focals.py, candidates.py, boxes.py, pages.py
├── schemas/             # Pydantic request/response models (VoterListResponse uses model_validate)
├── services/
│   ├── auth.py          # JWT token creation, password hashing, user authentication
│   ├── excel_import.py  # Parse Excel (3-column pledge Y/N/NA, photo extraction, all columns)
│   ├── logging.py       # Activity logging (separate session to avoid transaction conflicts)
│   ├── settings.py      # Column visibility/order config, voting open/closed state
│   ├── backup.py        # SQLite backup API (consistent WAL copies), scheduled 15-min backups
│   └── photo.py         # Voter photo upload handling
└── templates/           # Jinja2 HTML templates (unified Maldivian theme)
    ├── base.html        # Nav with role-based menu, offline indicator, PWA
    ├── login.html       # Ocean gradient background, centered card
    ├── dashboard.html   # Stat cards, vote breakdown, focal performance, candidate votes
    ├── import.html, change_password.html
    ├── voters/          # list (column selector), detail, form, print, pdf
    ├── voting/          # mark (Box# prefix + National ID search, quick pledge button)
    ├── manage/          # focals, boxes, candidates, users (with password reset)
    ├── reports/         # index (turnout hero, charts, candidate rankings, box/focal tables)
    └── admin/           # logs (Maldives timezone), settings (drag-reorder columns), stats, backups
static/
├── css/style.css        # Maldivian theme (CSS variables, responsive, mobile-first)
├── js/app.js            # Toast, PWA registration with auto-update, escapeHtml, offline support
├── sw.js                # Service worker (offline vote queueing, cache-first for static)
├── manifest.json, icons/
uploads/                 # Voter photos
Sample Data/             # Example Excel import file
app_settings.json        # Column visibility/order + voting open state (auto-created)
Dockerfile, docker-compose.yml
cloudflare-firewall.sh   # Restrict port 80 to Cloudflare IPs only
```

## Roles & Permissions

| Feature | Admin | Operator | Focal |
|---------|-------|----------|-------|
| Dashboard | Full | Full | Own voters only |
| Voters list | Full + pledge edit + column config | View only | View only |
| Vote Day | Mark votes | Mark votes (closed = view only) | No access |
| Reports | Full + CSV export | View + CSV export | View + CSV export |
| Manage (boxes/focals/candidates) | Full CRUD | No | No |
| Import/Export data | Yes | No | No |
| Users (CRUD + password reset) | Yes | No | No |
| Admin (logs/settings/backups/stats) | Yes | No | No |

## Key Patterns

- **Routers** serve both HTML pages and JSON API endpoints
- **Auth:** `get_current_user` (optional), `get_current_user_required` (mandatory), `require_role()` factory
- **Voting page** (`/voting`): Two search modes — Box# prefix (cached in localStorage) or National ID. Exact match only. 2-step flow: voted? → select candidate or "Not Disclosed". Quick "Vote as Pledged" button for pledged voters
- **Pledge status:** 3-state enum (yes/no/undecided), not boolean. Admin can bulk-update via checkboxes
- **Column selector:** Voters list has toggleable columns (21 columns, saved in localStorage). Admin can configure default visibility and order via Display Settings (drag-to-reorder)
- **Focal dashboard:** focal users see only their assigned voters' stats
- **Focals** sorted alphabetically by default
- **Security headers:** CSP (with Cloudflare analytics), X-Frame-Options, XSS-Protection, Referrer-Policy
- **XSS protection:** `escapeHtml()` on all dynamic content in JS templates
- **Activity logging:** ALL CRUD operations logged (candidates/boxes/focals/voters/import). Login attempts, vote changes, system events tracked with IP. Uses separate DB session to avoid transaction conflicts
- **Activity logs timezone:** Timestamps stored in UTC, frontend converts to Local/Maldives(UTC+5)/UTC via dropdown
- **PWA auto-update:** checks for new service worker version on every page load, reloads automatically
- **Offline support:** vote marks queued in IndexedDB when offline, synced on reconnect
- **Database backups:** SQLite backup API (not file copy) for consistent WAL-mode backups. Auto-backup every 15 mins when voting is open. Admin can download backups
- **System stats:** Admin page shows Python version, DB size, platform info
- **VoterListResponse** uses `model_validate()` not manual construction — ensures all ORM fields are serialized

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

## Excel Import

The sample file has these columns (all imported):
EC#, #, ID, Photo, Name, G(ender), Age, P(arty), Address, Contact, New Contact, Previous Island, Previous Address, Current Location, Registered Box, Box#, Zone, Focal, Focal Comment, Remarks, Pledged (3 sub-columns: Y/N/N/A)

- Duplicate national IDs are detected and rejected (within file and against DB)
- Photos are extracted from embedded Excel images
- Boxes and focals are auto-created from Excel data
- Sub-header row (Y/N/N/A under Pledged) is auto-detected and skipped

## Commands

```bash
python run.py                    # Dev server (port 8000, auto-reload)
docker-compose up --build -d     # Docker (port 80, 4 workers, background)
docker-compose build --no-cache  # Rebuild after code changes
docker-compose down              # Stop containers
./cloudflare-firewall.sh         # Lock port 80 to Cloudflare IPs
```

## Security Notes

- JWT SECRET_KEY in config.py / docker-compose env must be changed for production
- CORS allows all origins but credentials=False (safe)
- CSP allows cdn.jsdelivr.net (Bootstrap) and static.cloudflareinsights.com (analytics)
- Debug mode defaults to False
- Passwords hashed with bcrypt via passlib
- All CRUD operations logged with user and IP
- Login attempts (success/failure) logged with IP
- Cookie: httponly=True, samesite=Lax
- Default credentials (admin/admin123) not shown on login page
- Admin can reset any user's password

## Known Dev Issues

- **Windows pyc caching:** After editing Python files, delete `__pycache__` directories AND kill the Python process before restarting. The reloader may not detect changes, and stale `.pyc` files (which can be newer than `.py`) will be loaded instead of recompiled source
- **log_activity uses separate session:** Because the main DB session may already be committed, `log_activity()` creates its own `SessionLocal()` to avoid transaction conflicts
