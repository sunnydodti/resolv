"""
MigrationParserSubAgent — Deterministic agent for parsing database migrations.
Operation: ParseMigrations (Prisma, SQLAlchemy, SQL scripts).
"""
import os
from pathlib import Path
from typing import List, Dict, Any

from agents.base import SubAgent
from core.logger import ResolvLogger


class MigrationParserSubAgent(SubAgent):
    """Parses migration files for schema changes."""

    def __init__(self, logger: ResolvLogger, config):
        super().__init__(logger, config)

    def parse_migrations(self, migrations_path: str) -> Dict[str, Any]:
        """Parse migration files from the given path."""
        self.logger.info(f"Parsing migrations from: {migrations_path}")
        path = Path(migrations_path)
        if not path.exists():
            self.logger.warning(f"Migrations path does not exist: {migrations_path}")
            return {"path": migrations_path, "migrations": [], "count": 0}

        migration_files = []
        for ext in ["*.sql", "*.py", "*.prisma"]:
            migration_files.extend(path.glob(ext))

        migrations = []
        for mf in migration_files:
            migrations.append({
                "file": str(mf),
                "name": mf.name,
                "type": mf.suffix.lstrip("."),
            })

        self.logger.success(f"Found {len(migrations)} migration files")
        return {
            "path": migrations_path,
            "migrations": migrations,
            "count": len(migrations),
        }
