import pandas as pd
from .database_connect import mongo_operation as mongo
import os, sys
import logging
from src.constants import *
from src.config import DATABASE_URL
from src.exception import CustomException

logger = logging.getLogger(__name__)



class MongoIO:
    _mongo_ins = None
    _connection_url = None
    _database_name = None

    def __init__(self):
        # Store connection details but don't connect yet (lazy loading).
        # Kept class name for backward compatibility, backend is SQLite.
        if MongoIO._connection_url is None:
            db_url = DATABASE_URL
            if not db_url:
                raise Exception("DATABASE_URL is not set.")
            MongoIO._connection_url = db_url
            MongoIO._database_name = MONGO_DATABASE_NAME
    
    def _ensure_connection(self):
        """Lazy connection - only connect when actually needed."""
        if MongoIO._mongo_ins is None:
            MongoIO._mongo_ins = mongo(
                client_url=MongoIO._connection_url,
                database_name=MongoIO._database_name
            )
        return MongoIO._mongo_ins
    
    @property
    def mongo_ins(self):
        """Property to access MongoDB instance (lazy connection)."""
        return self._ensure_connection()

    def store_reviews(self,
                      product_name: str, 
                      reviews: pd.DataFrame,
                      platform: str = "myntra"):
        """
        Store reviews in MongoDB collection.
        
        Args:
            product_name: Name of the product
            reviews: DataFrame containing reviews
            platform: Platform name (myntra, flipkart, amazon)
        """
        try:
            # Collection naming: {platform}_{product_name}
            sanitized_product = product_name.replace(" ", "_")
            collection_name = f"{platform}_{sanitized_product}"
            self.mongo_ins.bulk_insert(reviews, collection_name)

        except Exception as e:
            raise CustomException(e, sys)

    def get_reviews(self,
                    product_name: str,
                    platform: str = None):
        """
        Get reviews from MongoDB collection.
        
        Args:
            product_name: Name of the product
            platform: Platform name (optional, if None returns from any platform)
            
        Returns:
            DataFrame with reviews
        """
        try:
            sanitized_product = product_name.replace(" ", "_")
            
            if platform:
                # Get from specific platform
                collection_name = f"{platform}_{sanitized_product}"
                data = self.mongo_ins.find(collection_name=collection_name)
            else:
                # Get from all platforms for this product
                platforms = ["myntra", "flipkart", "amazon"]
                all_data = []
                
                for plat in platforms:
                    collection_name = f"{plat}_{sanitized_product}"
                    try:
                        platform_data = self.mongo_ins.find(collection_name=collection_name)
                        if platform_data is not None and not platform_data.empty:
                            all_data.append(platform_data)
                    except:
                        continue
                
                if all_data:
                    import pandas as pd
                    data = pd.concat(all_data, axis=0, ignore_index=True)
                else:
                    data = None

            return data

        except Exception as e:
            raise CustomException(e, sys)
    
    def get_all_platform_reviews(self, product_name: str):
        """
        Get reviews from all platforms for a product.
        
        Args:
            product_name: Name of the product
            
        Returns:
            DataFrame with reviews from all platforms
        """
        return self.get_reviews(product_name=product_name, platform=None)
    
    def store_summary(self,
                     product_name: str,
                     summary: str,
                     platform: str = None):
        """
        Store review summary in SQLite summary table.
        
        Args:
            product_name: Name of the product
            summary: Summary text
            platform: Platform name (optional, None for all-platform summary)
        """
        try:
            self.mongo_ins.upsert_summary(
                product_name=product_name,
                platform=platform,
                summary=summary,
            )
            logger.info(f"Stored summary for {product_name} (platform: {platform or 'all'})")
            
        except Exception as e:
            logger.error(f"Error storing summary: {e}")
            raise CustomException(f"Failed to store summary: {e}", sys)
    
    def get_summary(self,
                   product_name: str,
                   platform: str = None) -> str:
        """
        Get review summary from SQLite.
        
        Args:
            product_name: Name of the product
            platform: Platform name (optional, None for all-platform summary)
            
        Returns:
            Summary string or None if not found
        """
        try:
            return self.mongo_ins.get_summary(
                product_name=product_name,
                platform=platform,
            )
            
        except Exception as e:
            logger.error(f"Error retrieving summary: {e}")
            return None

