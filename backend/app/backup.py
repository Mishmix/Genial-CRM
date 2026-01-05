"""Database backup system with rotation (daily, weekly, monthly)."""
import os
import shutil
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import json

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Default backup directory
BACKUP_DIR = Path(__file__).parent.parent / "backups"

# Retention settings (how many backups to keep)
DEFAULT_RETENTION = {
    "daily": 7,      # Keep last 7 daily backups
    "weekly": 4,     # Keep last 4 weekly backups  
    "monthly": 12,   # Keep last 12 monthly backups
}


def get_backup_dir() -> Path:
    """Get backup directory, create if not exists."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def get_db_path() -> Path:
    """Get database file path."""
    return Path(__file__).parent.parent / "crm.db"


def create_backup(backup_type: str = "manual", compress: bool = True) -> Optional[Dict]:
    """
    Create a database backup.
    
    Args:
        backup_type: Type of backup (daily, weekly, monthly, manual)
        compress: Whether to compress the backup with gzip
    
    Returns:
        Dict with backup info or None if failed
    """
    try:
        db_path = get_db_path()
        if not db_path.exists():
            logger.error(f"Database not found: {db_path}")
            return None
        
        backup_dir = get_backup_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create filename
        ext = ".db.gz" if compress else ".db"
        filename = f"crm_backup_{backup_type}_{timestamp}{ext}"
        backup_path = backup_dir / filename
        
        # Copy and optionally compress
        if compress:
            with open(db_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(db_path, backup_path)
        
        # Get file size
        size = backup_path.stat().st_size
        original_size = db_path.stat().st_size
        
        logger.info(f"Backup created: {filename} ({size} bytes)")
        
        return {
            "filename": filename,
            "path": str(backup_path),
            "type": backup_type,
            "size": size,
            "original_size": original_size,
            "compressed": compress,
            "created_at": datetime.now().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return None


def list_backups() -> List[Dict]:
    """List all available backups."""
    backup_dir = get_backup_dir()
    backups = []
    
    for f in backup_dir.glob("crm_backup_*"):
        try:
            stat = f.stat()
            # Parse filename: crm_backup_{type}_{timestamp}.db[.gz]
            parts = f.stem.replace(".db", "").split("_")
            backup_type = parts[2] if len(parts) > 2 else "unknown"
            
            # Parse timestamp
            if len(parts) >= 4:
                ts_str = f"{parts[3]}_{parts[4]}" if len(parts) > 4 else parts[3]
                try:
                    created = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                except:
                    created = datetime.fromtimestamp(stat.st_mtime)
            else:
                created = datetime.fromtimestamp(stat.st_mtime)
            
            backups.append({
                "filename": f.name,
                "type": backup_type,
                "size": stat.st_size,
                "compressed": f.suffix == ".gz",
                "created_at": created.isoformat(),
            })
        except Exception as e:
            logger.warning(f"Error reading backup {f}: {e}")
    
    # Sort by creation date, newest first
    backups.sort(key=lambda x: x["created_at"], reverse=True)
    return backups


def delete_backup(filename: str) -> bool:
    """Delete a specific backup."""
    backup_path = get_backup_dir() / filename
    if backup_path.exists() and backup_path.is_file():
        backup_path.unlink()
        logger.info(f"Backup deleted: {filename}")
        return True
    return False


def restore_backup(filename: str) -> bool:
    """
    Restore database from backup.
    Creates a backup of current DB before restoring.
    """
    backup_path = get_backup_dir() / filename
    if not backup_path.exists():
        logger.error(f"Backup not found: {filename}")
        return False
    
    db_path = get_db_path()
    
    try:
        # Create safety backup of current DB
        create_backup(backup_type="pre_restore", compress=True)
        
        # Restore
        if filename.endswith(".gz"):
            with gzip.open(backup_path, 'rb') as f_in:
                with open(db_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(backup_path, db_path)
        
        logger.info(f"Database restored from: {filename}")
        return True
    
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return False


def cleanup_old_backups(retention: Dict[str, int] = None) -> int:
    """
    Remove old backups based on retention policy.
    
    Returns:
        Number of backups deleted
    """
    if retention is None:
        retention = DEFAULT_RETENTION
    
    backups = list_backups()
    deleted = 0
    
    # Group by type
    by_type: Dict[str, List[Dict]] = {}
    for b in backups:
        t = b["type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(b)
    
    # Apply retention
    for backup_type, type_backups in by_type.items():
        max_keep = retention.get(backup_type, 10)  # Default keep 10
        
        # Skip manual backups from auto-cleanup
        if backup_type == "manual":
            continue
        
        # Delete excess backups (already sorted newest first)
        for b in type_backups[max_keep:]:
            if delete_backup(b["filename"]):
                deleted += 1
    
    if deleted > 0:
        logger.info(f"Cleanup: deleted {deleted} old backups")
    
    return deleted


def run_scheduled_backup():
    """
    Run scheduled backup based on current date.
    Called by scheduler (e.g., daily at midnight).
    """
    now = datetime.now()
    
    # Always create daily backup
    create_backup("daily", compress=True)
    
    # Weekly backup on Sunday
    if now.weekday() == 6:
        create_backup("weekly", compress=True)
    
    # Monthly backup on 1st day
    if now.day == 1:
        create_backup("monthly", compress=True)
    
    # Cleanup old backups
    cleanup_old_backups()


def get_backup_stats() -> Dict:
    """Get backup statistics."""
    backups = list_backups()
    backup_dir = get_backup_dir()
    
    total_size = sum(b["size"] for b in backups)
    
    by_type = {}
    for b in backups:
        t = b["type"]
        if t not in by_type:
            by_type[t] = {"count": 0, "size": 0}
        by_type[t]["count"] += 1
        by_type[t]["size"] += b["size"]
    
    # Find latest backup
    latest = backups[0] if backups else None
    
    return {
        "total_count": len(backups),
        "total_size": total_size,
        "by_type": by_type,
        "latest": latest,
        "backup_dir": str(backup_dir),
        "retention": DEFAULT_RETENTION,
    }


def download_backup(filename: str) -> Optional[Path]:
    """Get path to backup file for download."""
    backup_path = get_backup_dir() / filename
    if backup_path.exists() and backup_path.is_file():
        return backup_path
    return None
