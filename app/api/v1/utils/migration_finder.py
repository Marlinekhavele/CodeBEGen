import logging
import os
import re

logger = logging.getLogger(__name__)


def get_latest_migration_id(alembic_dir: str = "alembic") -> str:
    """
    Determine the latest migration ID for a specific project.

    Args:
        project_id: The ID of the project
        repo_dir: The repository directory (default: "repo")

    Returns:
        The latest migration ID or "0001" as default if no migrations found
    """
    # Method 1: Use Alembic's API (preferred)
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        # Find alembic.ini in the project directory (parent of alembic_dir)
        project_dir = os.path.dirname(os.path.abspath(alembic_dir))
        alembic_ini_path = os.path.join(project_dir, "alembic.ini")

        if not os.path.exists(alembic_ini_path):
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")

        alembic_cfg = Config(alembic_ini_path)
        script = ScriptDirectory.from_config(alembic_cfg)
        heads = script.get_heads()

        if heads and len(heads) > 0:
            logger.info(f"Found head revision using Alembic API: {heads[0]}")
            return heads[0]
    except Exception as e:
        logger.warning(
            f"Could not determine latest migration using Alembic API: {str(e)}"
        )
        logger.info("Falling back to file parsing method...")

    # Method 2: Parse migration files directly (fallback)
    try:
        versions_dir = os.path.join(alembic_dir, "versions")
        logger.debug(f"Looking for migrations in: {os.path.abspath(versions_dir)}")

        if not os.path.exists(versions_dir):
            logger.warning(f"Directory does not exist: {versions_dir}")
            return "0001"

        migration_files = [f for f in os.listdir(versions_dir) if f.endswith(".py")]
        logger.debug(
            f"Found {len(migration_files)} migration files in versions directory"
        )

        # Log the first few files for debugging
        if migration_files:
            sample = (
                migration_files[:5] if len(migration_files) > 5 else migration_files
            )
            logger.debug(f"Sample migration files: {', '.join(sample)}")

        latest_id = None
        revision_ids = {}

        for filename in migration_files:
            file_path = os.path.join(versions_dir, filename)

            with open(file_path, "r") as f:
                content = f.read()

                # Extract revision ID and down_revision from the file
                rev_match = re.search(r"revision\s*=\s*['\"]([^'\"]+)['\"]", content)

                if rev_match:
                    rev_id = rev_match.group(1)

                    # Check if this revision has a down_revision of None
                    down_rev_match = re.search(
                        r"down_revision\s*=\s*([^,\n]+)", content
                    )
                    if down_rev_match:
                        down_rev = down_rev_match.group(1).strip()

                        # Store for debugging
                        revision_ids[rev_id] = (
                            down_rev.replace("'", "").replace('"', "")
                            if down_rev != "None"
                            else None
                        )

                        if down_rev == "None":
                            # This is a base revision
                            logger.debug(f"Found base revision: {rev_id} in {filename}")
                            if latest_id is None:
                                latest_id = rev_id
                        elif latest_id is None or rev_id > latest_id:
                            latest_id = rev_id

        # Log the revision graph for debugging
        if revision_ids:
            logger.debug(f"Revision graph: {revision_ids}")

        # Find the head revision(s)
        all_revs = set(revision_ids.keys())
        child_revs = set(r for r in revision_ids.values() if r is not None)
        head_revs = all_revs - child_revs

        if head_revs:
            logger.info(f"Found head revisions through parsing: {head_revs}")
            latest_id = max(head_revs) if head_revs else latest_id

        if latest_id:
            logger.info(f"Using migration ID: {latest_id}")
            return latest_id

        logger.warning("No migrations found, using default ID: 0001")
        return "0001"
    except Exception as e:
        logger.error(
            f"Could not determine latest migration using file parsing: {str(e)}",
            exc_info=True,
        )
        return "0001"  # Default to initial migration


if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(level=logging.DEBUG)
    latest_id = get_latest_migration_id()
    logging.info(f"Latest migration ID: {latest_id}")
