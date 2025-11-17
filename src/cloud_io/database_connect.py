import certifi
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError
from pymongo.server_api import ServerApi
from src.config import MONGO_DB_URL
import pandas as pd
from urllib.parse import quote
import socket


def _extract_hostname(uri: str) -> str:
    """Extract hostname from MongoDB URI for DNS validation."""
    try:
        if "://" not in uri:
            return None
        scheme, rest = uri.split("://", 1)
        if "@" not in rest:
            return None
        # Extract hostname part (everything after @, before / or ?)
        host_part = rest.split("@", 1)[1].split("/")[0].split("?")[0]
        # Remove port if present (for non-SRV connections)
        hostname = host_part.split(":")[0]
        return hostname
    except:
        return None


def _validate_dns(hostname: str) -> bool:
    """Attempt DNS resolution of hostname."""
    if not hostname:
        return False
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.gaierror:
        return False


def _encode_mongo_uri(uri: str) -> str:
    """Encode special characters in MongoDB URI, especially in password and username."""
    try:
        # Handle mongodb+srv:// and mongodb:// URIs
        if "://" not in uri:
            return uri
        
        scheme, rest = uri.split("://", 1)
        if "@" not in rest:
            return uri
        
        # Split user:pass@host from rest
        auth_part, host_part = rest.split("@", 1)
        
        # Encode username and password separately
        if ":" in auth_part:
            username, password = auth_part.split(":", 1)
            # URL-encode both username and password (all special chars must be encoded)
            encoded_username = quote(username, safe='')
            encoded_password = quote(password, safe='')
            encoded_auth = f"{encoded_username}:{encoded_password}"
        else:
            # No password, but still encode username if present
            encoded_auth = quote(auth_part, safe='')
        
        # Reconstruct URI with encoded credentials
        encoded_uri = f"{scheme}://{encoded_auth}@{host_part}"
        return encoded_uri
    except Exception as e:
        # If encoding fails, raise - don't silently pass malformed URI
        raise ValueError(f"Failed to encode MongoDB URI: {str(e)}. Check for special characters in username/password.") from e


class MongoDatabaseWrapper:
    """Wrapper around PyMongo database object to provide DataFrame-friendly methods."""
    
    def __init__(self, db):
        self._db = db
    
    def bulk_insert(self, df: pd.DataFrame, collection_name: str):
        """Insert DataFrame records into MongoDB collection."""
        collection = self._db[collection_name]
        records = df.to_dict('records')
        if records:
            collection.insert_many(records)
    
    def find(self, collection_name: str, query=None):
        """Find documents in collection and return as DataFrame."""
        collection = self._db[collection_name]
        if query is None:
            query = {}
        cursor = collection.find(query)
        data = list(cursor)
        if not data:
            return None
        df = pd.DataFrame(data)
        # Remove MongoDB _id field if present
        if '_id' in df.columns:
            df = df.drop('_id', axis=1)
        return df
    
    def __getattr__(self, name):
        """Delegate other attributes to underlying database object."""
        return getattr(self._db, name)


def mongo_operation(client_url=None, database_name=None):
    """
    Create MongoDB connection and return wrapped database object.
    
    Args:
        client_url: MongoDB connection URL (defaults to MONGO_DB_URL from config)
        database_name: Database name (defaults to "myntra_reviews")
    
    Returns:
        MongoDatabaseWrapper around MongoDB database object
    
    Raises:
        ConfigurationError: If connection string is invalid or DNS resolution fails
    """
    if client_url is None:
        client_url = MONGO_DB_URL
    if database_name is None:
        database_name = "myntra_reviews"
    
    # Encode special characters in URI, especially password
    encoded_uri = _encode_mongo_uri(client_url)
    
    try:
        # Validate URI format before attempting connection
        if not encoded_uri or "://" not in encoded_uri:
            raise ValueError("Invalid MongoDB connection URI format")
        
        # Extract and validate hostname DNS resolution before attempting connection
        # Note: For mongodb+srv://, PyMongo handles SRV record resolution internally,
        # so we skip A record validation for SRV connections
        is_srv = encoded_uri.startswith("mongodb+srv://")
        hostname = _extract_hostname(client_url)
        if hostname and not is_srv:  # Only validate DNS for non-SRV connections
            if not _validate_dns(hostname):
                raise ConfigurationError(
                    f"MongoDB cluster hostname '{hostname}' cannot be resolved via DNS.\n\n"
                    f"This indicates one of the following:\n"
                    f"1. The cluster does not exist or was deleted\n"
                    f"2. The cluster hostname in your connection string is incorrect\n"
                    f"3. Network/DNS issues preventing resolution\n\n"
                    f"To fix:\n"
                    f"- Log into MongoDB Atlas dashboard\n"
                    f"- Verify cluster name matches: {hostname}\n"
                    f"- Copy the correct connection string from Atlas (Connect → Drivers)\n"
                    f"- Update your connection string in: src/cloud_io/__init__.py (line 17)"
                )
        
        # Add serverSelectionTimeoutMS to fail faster if DNS/connection issues
        if "serverSelectionTimeoutMS" not in encoded_uri:
            separator = "&" if "?" in encoded_uri else "?"
            encoded_uri += f"{separator}serverSelectionTimeoutMS=5000"
        
        client = MongoClient(
            encoded_uri,
            server_api=ServerApi("1"),
            tls=True,
            tlsCAFile=certifi.where(),  # ✅ This bypasses Windows cert issues entirely
            serverSelectionTimeoutMS=5000
        )
        # Test connection with a simple operation
        client.admin.command('ping')
        db = client[database_name]
        return MongoDatabaseWrapper(db)
    except (ValueError, ConfigurationError) as e:
        # Catch URI encoding errors and configuration errors
        error_msg = str(e).lower()
        if "dns" in error_msg or "host" in error_msg or "name" in error_msg:
            diagnostic = (
                f"MongoDB connection failed - DNS/Network issue detected. "
                f"Original error: {str(e)}\n\n"
                f"Troubleshooting steps:\n"
                f"1. Verify the MongoDB cluster exists and is accessible\n"
                f"2. Check the cluster hostname in your connection string\n"
                f"3. Verify your network can reach MongoDB Atlas\n"
                f"4. Check if the cluster was deleted or renamed\n"
                f"5. Ensure your IP is whitelisted in MongoDB Atlas (if applicable)"
            )
        else:
            diagnostic = (
                f"MongoDB connection configuration error: {str(e)}. "
                f"Check if the connection string is valid and credentials are correct."
            )
        raise ConfigurationError(diagnostic) from e
    except ServerSelectionTimeoutError as e:
        raise ServerSelectionTimeoutError(
            f"MongoDB server selection timeout: {str(e)}. "
            f"Check network connectivity and MongoDB cluster availability. "
            f"Verify the cluster is running and accessible."
        ) from e
    except Exception as e:
        error_type = type(e).__name__
        raise Exception(
            f"Failed to connect to MongoDB ({error_type}): {str(e)}. "
            f"Check connection string format, credentials, and network access."
        ) from e

