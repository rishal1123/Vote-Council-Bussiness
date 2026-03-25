import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException

from app.config import settings


def get_file_extension(filename: str) -> str:
    """Get file extension from filename."""
    if "." in filename:
        return filename.rsplit(".", 1)[1].lower()
    return ""


async def save_photo(file: UploadFile) -> str:
    """
    Save an uploaded photo and return the file path.
    """
    # Validate file extension
    ext = get_file_extension(file.filename)
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {settings.ALLOWED_EXTENSIONS}"
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB"
        )

    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}.{ext}"
    file_path = settings.UPLOAD_DIR / unique_filename

    # Write file
    with open(file_path, "wb") as f:
        f.write(content)

    return str(unique_filename)


def delete_photo(filename: str) -> bool:
    """Delete a photo file."""
    if not filename:
        return False

    file_path = settings.UPLOAD_DIR / filename
    if file_path.exists():
        file_path.unlink()
        return True
    return False
