import os
import subprocess
import logging
from sqlalchemy import create_engine, inspect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    database_url = os.environ.get('DATABASE_URL')
    
    # In sqlite/local Fallback mode
    if not database_url:
        logger.info("DATABASE_URL not set, checking for local sqlite...")
        database_url = "sqlite:///./crm.db"
        # Set os.environ for alembic subprocesses
        os.environ['DATABASE_URL'] = database_url

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    logger.info(f"Connecting to database to check migration status...")
    engine = create_engine(database_url)
    inspector = inspect(engine)
    
    tables = inspector.get_table_names()
    
    if 'clients' in tables and 'alembic_version' not in tables:
        logger.warning("Existing database detected without Alembic tracking.")
        logger.info("Stamping database with revision just before BigInt PR: 20260102_orders")
        subprocess.run(['alembic', 'stamp', '20260102_orders'], check=True)
    elif 'clients' not in tables:
        logger.info("Empty database detected. Alembic will run full migration from scratch.")
    else:
        logger.info("Database is properly tracked by Alembic. Proceeding with normal upgrade.")

    logger.info("Running `alembic upgrade head`...")
    result = subprocess.run(['alembic', 'upgrade', 'head'], capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Migration failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        exit(1)
    
    logger.info("Database migrations applied successfully!")

if __name__ == "__main__":
    main()
