import json
import os

SETTINGS_FILE = "app_settings.json"

DEFAULT_COLUMNS = {
    "photo": {"label": "Photo", "order": 0, "list": True, "print": False, "pdf": True, "detail": True},
    "ec_number": {"label": "EC#", "order": 1, "list": False, "print": True, "pdf": True, "detail": True},
    "voter_id": {"label": "#", "order": 2, "list": False, "print": False, "pdf": False, "detail": True},
    "national_id": {"label": "National ID", "order": 3, "list": True, "print": True, "pdf": True, "detail": True},
    "name": {"label": "Name", "order": 4, "list": True, "print": True, "pdf": True, "detail": True},
    "gender": {"label": "Gender", "order": 5, "list": False, "print": True, "pdf": True, "detail": True},
    "age": {"label": "Age", "order": 6, "list": False, "print": True, "pdf": True, "detail": True},
    "party": {"label": "Party", "order": 7, "list": False, "print": False, "pdf": True, "detail": True},
    "address": {"label": "Address", "order": 8, "list": False, "print": False, "pdf": False, "detail": True},
    "contact": {"label": "Contact", "order": 9, "list": True, "print": True, "pdf": True, "detail": True},
    "new_contact": {"label": "New Contact", "order": 10, "list": False, "print": False, "pdf": False, "detail": True},
    "previous_island": {"label": "Previous Island", "order": 11, "list": False, "print": False, "pdf": False, "detail": True},
    "previous_address": {"label": "Previous Address", "order": 12, "list": False, "print": False, "pdf": False, "detail": True},
    "current_location": {"label": "Current Location", "order": 13, "list": False, "print": False, "pdf": False, "detail": True},
    "box": {"label": "Registered Box", "order": 14, "list": True, "print": True, "pdf": True, "detail": True},
    "box_number": {"label": "Box#", "order": 15, "list": False, "print": True, "pdf": True, "detail": True},
    "zone": {"label": "Zone", "order": 16, "list": False, "print": False, "pdf": True, "detail": True},
    "focals": {"label": "Focal(s)", "order": 17, "list": True, "print": True, "pdf": True, "detail": True},
    "focal_comment": {"label": "Focal Comment", "order": 18, "list": False, "print": False, "pdf": False, "detail": True},
    "remarks": {"label": "Remarks", "order": 19, "list": False, "print": False, "pdf": False, "detail": True},
    "pledged": {"label": "Pledged", "order": 20, "list": True, "print": True, "pdf": True, "detail": True},
    "vote_status": {"label": "Vote Status", "order": 21, "list": True, "print": True, "pdf": True, "detail": True},
}

def get_column_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            saved = json.load(f)
            # Merge with defaults for any new columns
            for key, val in DEFAULT_COLUMNS.items():
                if key not in saved:
                    saved[key] = val
            # Return only column entries (dicts), skip _voting_open etc.
            return {k: v for k, v in saved.items() if isinstance(v, dict)}
    return DEFAULT_COLUMNS.copy()

def save_column_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

def get_visible_columns(view_type):
    """Get list of column keys visible for a view type (list/print/pdf/detail), ordered by 'order' field."""
    settings = get_column_settings()
    visible = {key: val for key, val in settings.items() if isinstance(val, dict) and val.get(view_type, False)}
    return dict(sorted(visible.items(), key=lambda x: x[1].get('order', 999)))

def get_ordered_columns():
    """Get all columns sorted by order."""
    settings = get_column_settings()
    cols = {k: v for k, v in settings.items() if isinstance(v, dict)}
    return dict(sorted(cols.items(), key=lambda x: x[1].get('order', 999)))


# --- Voting open/closed ---

def is_voting_open():
    """Check if voting is currently open."""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            data = json.load(f)
            return data.get("_voting_open", False)
    return False


def set_voting_open(is_open):
    """Set voting open or closed."""
    data = {}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            data = json.load(f)
    data["_voting_open"] = is_open
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
