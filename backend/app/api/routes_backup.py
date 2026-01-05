"""API routes for backup management."""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import tempfile
import shutil

from app.backup import (
    create_backup,
    list_backups,
    delete_backup,
    restore_backup,
    get_backup_stats,
    download_backup,
    cleanup_old_backups,
    DEFAULT_RETENTION,
)

router = APIRouter(prefix="/backup", tags=["backup"])


class BackupCreate(BaseModel):
    backup_type: str = "manual"
    compress: bool = True


class RetentionUpdate(BaseModel):
    daily: Optional[int] = None
    weekly: Optional[int] = None
    monthly: Optional[int] = None


@router.get("/list")
async def api_list_backups():
    """List all available backups."""
    return {"backups": list_backups()}


@router.get("/stats")
async def api_backup_stats():
    """Get backup statistics."""
    return get_backup_stats()


@router.post("/create")
async def api_create_backup(data: BackupCreate):
    """Create a new backup."""
    result = create_backup(data.backup_type, data.compress)
    if result:
        return result
    raise HTTPException(status_code=500, detail="Backup creation failed")


@router.delete("/{filename}")
async def api_delete_backup(filename: str):
    """Delete a specific backup."""
    if delete_backup(filename):
        return {"success": True, "message": f"Backup {filename} deleted"}
    raise HTTPException(status_code=404, detail="Backup not found")


@router.post("/restore/{filename}")
async def api_restore_backup(filename: str):
    """Restore database from backup."""
    if restore_backup(filename):
        return {"success": True, "message": f"Database restored from {filename}"}
    raise HTTPException(status_code=500, detail="Restore failed")


@router.get("/download/{filename}")
async def api_download_backup(filename: str):
    """Download a backup file."""
    path = download_backup(filename)
    if path:
        media_type = "application/gzip" if filename.endswith(".gz") else "application/octet-stream"
        return FileResponse(
            path=path,
            filename=filename,
            media_type=media_type,
        )
    raise HTTPException(status_code=404, detail="Backup not found")


@router.post("/cleanup")
async def api_cleanup_backups():
    """Run cleanup of old backups based on retention policy."""
    deleted = cleanup_old_backups()
    return {"deleted": deleted, "message": f"Deleted {deleted} old backups"}


@router.post("/upload")
async def api_upload_backup(file: UploadFile = File(...)):
    """Upload a backup file."""
    if not file.filename.startswith("crm_backup_"):
        raise HTTPException(status_code=400, detail="Invalid backup filename")
    
    from app.backup import get_backup_dir
    backup_dir = get_backup_dir()
    backup_path = backup_dir / file.filename
    
    # Save uploaded file
    with open(backup_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    return {
        "success": True,
        "filename": file.filename,
        "size": backup_path.stat().st_size,
    }
