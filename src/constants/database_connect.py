from src.cloud_io.database_connect import mongo_operation as sqlite_operation


def mongo_operation():
    """Backward-compatible alias. Returns SQLite wrapper instance."""
    return sqlite_operation()
