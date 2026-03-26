import json
import os

SETTINGS_FILE = "app_settings.json"

DEFAULT_COLUMNS = {
    "ec_number": {"label": "EC#", "print": True, "pdf": True, "detail": True},
    "voter_id": {"label": "#", "print": False, "pdf": False, "detail": True},
    "national_id": {"label": "National ID", "print": True, "pdf": True, "detail": True},
    "name": {"label": "Name", "print": True, "pdf": True, "detail": True},
    "gender": {"label": "Gender", "print": True, "pdf": True, "detail": True},
    "age": {"label": "Age", "print": True, "pdf": True, "detail": True},
    "party": {"label": "Party", "print": False, "pdf": True, "detail": True},
    "address": {"label": "Address", "print": False, "pdf": False, "detail": True},
    "contact": {"label": "Contact", "print": True, "pdf": True, "detail": True},
    "new_contact": {"label": "New Contact", "print": False, "pdf": False, "detail": True},
    "previous_island": {"label": "Previous Island", "print": False, "pdf": False, "detail": True},
    "previous_address": {"label": "Previous Address", "print": False, "pdf": False, "detail": True},
    "current_location": {"label": "Current Location", "print": False, "pdf": False, "detail": True},
    "box": {"label": "Box", "print": True, "pdf": True, "detail": True},
    "box_number": {"label": "Box#", "print": True, "pdf": True, "detail": True},
    "zone": {"label": "Zone", "print": False, "pdf": True, "detail": True},
    "focals": {"label": "Focal(s)", "print": True, "pdf": True, "detail": True},
    "focal_comment": {"label": "Focal Comment", "print": False, "pdf": False, "detail": True},
    "remarks": {"label": "Remarks", "print": False, "pdf": False, "detail": True},
    "pledged": {"label": "Pledged", "print": True, "pdf": True, "detail": True},
    "vote_status": {"label": "Vote Status", "print": True, "pdf": True, "detail": True},
    "photo": {"label": "Photo", "print": False, "pdf": True, "detail": True},
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
    """Get list of column keys visible for a view type (print/pdf/detail)"""
    settings = get_column_settings()
    return {key: val for key, val in settings.items() if isinstance(val, dict) and val.get(view_type, False)}


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
