"""Database Backend - Unified SQLite/PostgreSQL interface

Provides a unified interface for both SQLite and PostgreSQL databases
with connection pooling, performance optimization, and indexing.
"""

import asyncio
import sqlite3
import time
from typing import List, Dict, Any, Optional, Union
from abc import ABC, abstractmethod
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from zomoto_ai.phase0.domain.models import Restaurant
from zomoto_ai.phase6.logging import get_logger, get_performance_tracker


class DatabaseBackend(ABC):
    """Abstract base class for database backends."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the database."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the database."""
        pass
    
    @abstractmethod
    async def create_schema(self) -> bool:
        """Create database schema and indexes."""
        pass
    
    @abstractmethod
    async def insert_restaurants(self, restaurants: List[Restaurant]) -> bool:
        """Insert restaurant records."""
        pass
    
    @abstractmethod
    async def search_by_preferences(
        self,
        location: str,
        cuisine: Optional[str] = None,
        min_rating: float = 0.0,
        max_cost_for_two: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search restaurants by preferences."""
        pass
    
    @abstractmethod
    async def get_restaurant_by_id(self, restaurant_id: str) -> Optional[Dict[str, Any]]:
        """Get restaurant by ID."""
        pass
    
    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        pass


class SQLiteBackend(DatabaseBackend):
    """SQLite database backend."""
    
    def __init__(self, db_path: str = "data/restaurants.db"):
        self.db_path = db_path
        self.logger = get_logger()
        self.performance_tracker = get_performance_tracker()
        self._connection = None
        self._lock = asyncio.Lock()
        
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    async def connect(self) -> bool:
        """Connect to SQLite database."""
        try:
            with self.performance_tracker.track_request("database", "connect"):
                self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
                self._connection.row_factory = sqlite3.Row  # Enable dict-like access
                
                # Enable WAL mode for better performance
                self._connection.execute("PRAGMA journal_mode=WAL")
                self._connection.execute("PRAGMA synchronous=NORMAL")
                self._connection.execute("PRAGMA cache_size=10000")
                self._connection.execute("PRAGMA temp_store=memory")
                
                self.logger.info("sqlite_backend", "connected", f"Connected to SQLite: {self.db_path}")
                return True
                
        except Exception as e:
            self.logger.error("sqlite_backend", "connect_failed", f"Failed to connect: {str(e)}")
            return False
    
    async def disconnect(self):
        """Disconnect from SQLite database."""
        if self._connection:
            self._connection.close()
            self._connection = None
            self.logger.info("sqlite_backend", "disconnected", "Disconnected from SQLite")
    
    async def create_schema(self) -> bool:
        """Create database schema and indexes."""
        if not self._connection:
            return False
        
        try:
            with self.performance_tracker.track_request("database", "create_schema"):
                cursor = self._connection.cursor()
                
                # Create restaurants table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS restaurants (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        location TEXT,
                        city TEXT,
                        area TEXT,
                        cuisines TEXT,  -- JSON array
                        cost_for_two INTEGER,
                        rating REAL,
                        votes INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_location ON restaurants(location)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_city ON restaurants(city)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_area ON restaurants(area)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_rating ON restaurants(rating)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_cost ON restaurants(cost_for_two)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_cuisines ON restaurants(cuisines)")
                
                # Create full-text search index
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS restaurants_fts 
                    USING fts5(name, location, city, area, cuisines)
                """)
                
                self._connection.commit()
                
                self.logger.info("sqlite_backend", "schema_created", "Database schema created")
                return True
                
        except Exception as e:
            self.logger.error("sqlite_backend", "schema_creation_failed", f"Failed to create schema: {str(e)}")
            return False
    
    async def insert_restaurants(self, restaurants: List[Restaurant]) -> bool:
        """Insert restaurant records."""
        if not self._connection:
            return False
        
        try:
            with self.performance_tracker.track_request("database", "insert_restaurants"):
                cursor = self._connection.cursor()
                
                # Prepare insert statement
                insert_sql = """
                    INSERT OR REPLACE INTO restaurants 
                    (id, name, location, city, area, cuisines, cost_for_two, rating, votes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """
                
                # Prepare FTS insert statement
                fts_sql = """
                    INSERT OR REPLACE INTO restaurants_fts 
                    (rowid, name, location, city, area, cuisines)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                
                # Batch insert
                restaurant_data = []
                fts_data = []
                
                for restaurant in restaurants:
                    import json
                    restaurant_data.append((
                        restaurant.id,
                        restaurant.name,
                        restaurant.location,
                        restaurant.city,
                        restaurant.area,
                        json.dumps(restaurant.cuisines),
                        restaurant.cost_for_two,
                        restaurant.rating,
                        restaurant.votes
                    ))
                    
                    fts_data.append((
                        restaurant.id,
                        restaurant.name,
                        restaurant.location or "",
                        restaurant.city or "",
                        restaurant.area or "",
                        " ".join(restaurant.cuisines)
                    ))
                
                cursor.executemany(insert_sql, restaurant_data)
                cursor.executemany(fts_sql, fts_data)
                
                self._connection.commit()
                
                self.logger.info("sqlite_backend", "restaurants_inserted", 
                               f"Inserted {len(restaurants)} restaurants")
                return True
                
        except Exception as e:
            self.logger.error("sqlite_backend", "insert_failed", f"Failed to insert restaurants: {str(e)}")
            return False
    
    async def search_by_preferences(
        self,
        location: str,
        cuisine: Optional[str] = None,
        min_rating: float = 0.0,
        max_cost_for_two: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search restaurants by preferences."""
        if not self._connection:
            return []
        
        try:
            with self.performance_tracker.track_request("database", "search"):
                cursor = self._connection.cursor()
                
                # Build query
                where_conditions = []
                params = []
                
                # Location search (case-insensitive)
                where_conditions.append("(LOWER(location) LIKE ? OR LOWER(city) LIKE ? OR LOWER(area) LIKE ?)")
                location_param = f"%{location.lower()}%"
                params.extend([location_param, location_param, location_param])
                
                # Cuisine filter
                if cuisine:
                    where_conditions.append("cuisines LIKE ?")
                    params.append(f"%{cuisine}%")
                
                # Rating filter
                where_conditions.append("rating >= ?")
                params.append(min_rating)
                
                # Cost filter
                if max_cost_for_two:
                    where_conditions.append("cost_for_two <= ?")
                    params.append(max_cost_for_two)
                
                # Combine conditions
                where_clause = " AND ".join(where_conditions)
                
                query = f"""
                    SELECT id, name, location, city, area, cuisines, cost_for_two, rating, votes
                    FROM restaurants
                    WHERE {where_clause}
                    ORDER BY rating DESC, votes DESC
                    LIMIT ?
                """
                
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to dictionaries
                results = []
                for row in rows:
                    import json
                    result = dict(row)
                    # Parse cuisines JSON
                    try:
                        result['cuisines'] = json.loads(result['cuisines'])
                    except:
                        result['cuisines'] = []
                    results.append(result)
                
                self.logger.info("sqlite_backend", "search_completed",
                               f"Found {len(results)} restaurants for location: {location}",
                               location=location,
                               cuisine=cuisine,
                               results_count=len(results))
                
                return results
                
        except Exception as e:
            self.logger.error("sqlite_backend", "search_failed", f"Search failed: {str(e)}")
            return []
    
    async def get_restaurant_by_id(self, restaurant_id: str) -> Optional[Dict[str, Any]]:
        """Get restaurant by ID."""
        if not self._connection:
            return None
        
        try:
            cursor = self._connection.cursor()
            cursor.execute(
                "SELECT id, name, location, city, area, cuisines, cost_for_two, rating, votes FROM restaurants WHERE id = ?",
                (restaurant_id,)
            )
            row = cursor.fetchone()
            
            if row:
                import json
                result = dict(row)
                try:
                    result['cuisines'] = json.loads(result['cuisines'])
                except:
                    result['cuisines'] = []
                return result
            
            return None
            
        except Exception as e:
            self.logger.error("sqlite_backend", "get_by_id_failed", f"Failed to get restaurant: {str(e)}")
            return None
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        if not self._connection:
            return {"error": "Not connected"}
        
        try:
            cursor = self._connection.cursor()
            
            # Get table statistics
            cursor.execute("SELECT COUNT(*) FROM restaurants")
            total_restaurants = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT city) FROM restaurants")
            unique_cities = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT location) FROM restaurants")
            unique_locations = cursor.fetchone()[0]
            
            cursor.execute("SELECT AVG(rating) FROM restaurants WHERE rating IS NOT NULL")
            avg_rating = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT AVG(cost_for_two) FROM restaurants WHERE cost_for_two IS NOT NULL")
            avg_cost = cursor.fetchone()[0] or 0
            
            return {
                "total_restaurants": total_restaurants,
                "unique_cities": unique_cities,
                "unique_locations": unique_locations,
                "average_rating": round(avg_rating, 2),
                "average_cost": round(avg_cost, 2),
                "database_type": "SQLite",
                "database_path": self.db_path
            }
            
        except Exception as e:
            self.logger.error("sqlite_backend", "stats_failed", f"Failed to get statistics: {str(e)}")
            return {"error": str(e)}


class PostgreSQLBackend(DatabaseBackend):
    """PostgreSQL database backend."""
    
    def __init__(self, host: str = "localhost", port: int = 5432, database: str = "zomoto_ai",
                 username: str = "postgres", password: str = "", pool_size: int = 20):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.pool_size = pool_size
        
        self.logger = get_logger()
        self.performance_tracker = get_performance_tracker()
        self._pool = None
    
    async def connect(self) -> bool:
        """Connect to PostgreSQL database."""
        try:
            import asyncpg
            
            with self.performance_tracker.track_request("database", "connect"):
                self._pool = await asyncpg.create_pool(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.username,
                    password=self.password,
                    min_size=5,
                    max_size=self.pool_size,
                    command_timeout=60
                )
                
                self.logger.info("postgresql_backend", "connected", 
                               f"Connected to PostgreSQL: {self.host}:{self.port}/{self.database}")
                return True
                
        except Exception as e:
            self.logger.error("postgresql_backend", "connect_failed", f"Failed to connect: {str(e)}")
            return False
    
    async def disconnect(self):
        """Disconnect from PostgreSQL database."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self.logger.info("postgresql_backend", "disconnected", "Disconnected from PostgreSQL")
    
    async def create_schema(self) -> bool:
        """Create database schema and indexes."""
        if not self._pool:
            return False
        
        try:
            with self.performance_tracker.track_request("database", "create_schema"):
                async with self._pool.acquire() as conn:
                    # Create restaurants table
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS restaurants (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            location TEXT,
                            city TEXT,
                            area TEXT,
                            cuisines TEXT[],  -- PostgreSQL array
                            cost_for_two INTEGER,
                            rating REAL,
                            votes INTEGER,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # Create indexes
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_location ON restaurants(location)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_city ON restaurants(city)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_area ON restaurants(area)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_rating ON restaurants(rating)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_cost ON restaurants(cost_for_two)")
                    
                    # Create GIN index for cuisines array
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_cuisines ON restaurants USING GIN(cuisines)")
                    
                    # Create full-text search
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS restaurants_fts (
                            restaurant_id TEXT PRIMARY KEY REFERENCES restaurants(id),
                            document tsvector
                        )
                    """)
                    
                    await conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_restaurants_fts_document 
                        ON restaurants_fts USING GIN(document)
                    """)
                    
                    self.logger.info("postgresql_backend", "schema_created", "Database schema created")
                    return True
                    
        except Exception as e:
            self.logger.error("postgresql_backend", "schema_creation_failed", f"Failed to create schema: {str(e)}")
            return False
    
    async def insert_restaurants(self, restaurants: List[Restaurant]) -> bool:
        """Insert restaurant records."""
        if not self._pool:
            return False
        
        try:
            with self.performance_tracker.track_request("database", "insert_restaurants"):
                async with self._pool.acquire() as conn:
                    # Prepare insert statement
                    insert_sql = """
                        INSERT INTO restaurants 
                        (id, name, location, city, area, cuisines, cost_for_two, rating, votes, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        location = EXCLUDED.location,
                        city = EXCLUDED.city,
                        area = EXCLUDED.area,
                        cuisines = EXCLUDED.cuisines,
                        cost_for_two = EXCLUDED.cost_for_two,
                        rating = EXCLUDED.rating,
                        votes = EXCLUDED.votes,
                        updated_at = CURRENT_TIMESTAMP
                    """
                    
                    # Batch insert
                    restaurant_data = []
                    for restaurant in restaurants:
                        restaurant_data.append((
                            restaurant.id,
                            restaurant.name,
                            restaurant.location,
                            restaurant.city,
                            restaurant.area,
                            restaurant.cuisines,  # PostgreSQL array
                            restaurant.cost_for_two,
                            restaurant.rating,
                            restaurant.votes
                        ))
                    
                    await conn.executemany(insert_sql, restaurant_data)
                    
                    self.logger.info("postgresql_backend", "restaurants_inserted",
                                   f"Inserted {len(restaurants)} restaurants")
                    return True
                    
        except Exception as e:
            self.logger.error("postgresql_backend", "insert_failed", f"Failed to insert restaurants: {str(e)}")
            return False
    
    async def search_by_preferences(
        self,
        location: str,
        cuisine: Optional[str] = None,
        min_rating: float = 0.0,
        max_cost_for_two: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search restaurants by preferences."""
        if not self._pool:
            return []
        
        try:
            with self.performance_tracker.track_request("database", "search"):
                async with self._pool.acquire() as conn:
                    # Build query
                    where_conditions = ["$1"]
                    params = [location]
                    param_counter = 2
                    
                    # Location search
                    where_conditions.append("(LOWER(location) LIKE $" + str(param_counter) + 
                                          " OR LOWER(city) LIKE $" + str(param_counter) + 
                                          " OR LOWER(area) LIKE $" + str(param_counter) + ")")
                    location_param = f"%{location.lower()}%"
                    params.append(location_param)
                    param_counter += 1
                    
                    # Cuisine filter
                    if cuisine:
                        where_conditions.append("$" + str(param_counter) + " = ANY(cuisines)")
                        params.append(cuisine)
                        param_counter += 1
                    
                    # Rating filter
                    where_conditions.append("rating >= $" + str(param_counter))
                    params.append(min_rating)
                    param_counter += 1
                    
                    # Cost filter
                    if max_cost_for_two:
                        where_conditions.append("cost_for_two <= $" + str(param_counter))
                        params.append(max_cost_for_two)
                        param_counter += 1
                    
                    # Combine conditions
                    where_clause = " AND ".join(where_conditions)
                    
                    query = f"""
                        SELECT id, name, location, city, area, cuisines, cost_for_two, rating, votes
                        FROM restaurants
                        WHERE {where_clause}
                        ORDER BY rating DESC, votes DESC
                        LIMIT ${param_counter}
                    """
                    
                    params.append(limit)
                    
                    rows = await conn.fetch(query, *params)
                    
                    # Convert to dictionaries
                    results = []
                    for row in rows:
                        result = dict(row)
                        results.append(result)
                    
                    self.logger.info("postgresql_backend", "search_completed",
                                   f"Found {len(results)} restaurants for location: {location}",
                                   location=location,
                                   cuisine=cuisine,
                                   results_count=len(results))
                    
                    return results
                    
        except Exception as e:
            self.logger.error("postgresql_backend", "search_failed", f"Search failed: {str(e)}")
            return []
    
    async def get_restaurant_by_id(self, restaurant_id: str) -> Optional[Dict[str, Any]]:
        """Get restaurant by ID."""
        if not self._pool:
            return None
        
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id, name, location, city, area, cuisines, cost_for_two, rating, votes FROM restaurants WHERE id = $1",
                    restaurant_id
                )
                
                return dict(row) if row else None
                
        except Exception as e:
            self.logger.error("postgresql_backend", "get_by_id_failed", f"Failed to get restaurant: {str(e)}")
            return None
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        if not self._pool:
            return {"error": "Not connected"}
        
        try:
            async with self._pool.acquire() as conn:
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_restaurants,
                        COUNT(DISTINCT city) as unique_cities,
                        COUNT(DISTINCT location) as unique_locations,
                        COALESCE(AVG(rating), 0) as avg_rating,
                        COALESCE(AVG(cost_for_two), 0) as avg_cost
                    FROM restaurants
                """)
                
                return {
                    "total_restaurants": stats["total_restaurants"],
                    "unique_cities": stats["unique_cities"],
                    "unique_locations": stats["unique_locations"],
                    "average_rating": round(float(stats["avg_rating"]), 2),
                    "average_cost": round(float(stats["avg_cost"]), 2),
                    "database_type": "PostgreSQL",
                    "host": self.host,
                    "port": self.port,
                    "database": self.database
                }
                
        except Exception as e:
            self.logger.error("postgresql_backend", "stats_failed", f"Failed to get statistics: {str(e)}")
            return {"error": str(e)}


class RestaurantRepository:
    """High-level repository for restaurant operations."""
    
    def __init__(self, backend: DatabaseBackend):
        self.backend = backend
        self.logger = get_logger()
        self._cache = {}  # Simple in-memory cache
    
    async def initialize(self) -> bool:
        """Initialize the repository."""
        return await self.backend.connect() and await self.backend.create_schema()
    
    async def load_from_parquet(self, parquet_path: str) -> bool:
        """Load restaurants from parquet file."""
        try:
            from zomoto_ai.phase3.retrieval import load_restaurants_from_parquet
            restaurants = load_restaurants_from_parquet(parquet_path)
            
            if restaurants:
                return await self.backend.insert_restaurants(restaurants)
            
            return False
            
        except Exception as e:
            self.logger.error("restaurant_repository", "load_parquet_failed", 
                            f"Failed to load from parquet: {str(e)}")
            return False
    
    async def search_preferences(self, **kwargs) -> List[Dict[str, Any]]:
        """Search restaurants by preferences."""
        cache_key = str(sorted(kwargs.items()))
        
        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Search database
        results = await self.backend.search_by_preferences(**kwargs)
        
        # Cache result
        self._cache[cache_key] = results
        
        return results
    
    async def get_by_id(self, restaurant_id: str) -> Optional[Dict[str, Any]]:
        """Get restaurant by ID."""
        return await self.backend.get_restaurant_by_id(restaurant_id)
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get repository statistics."""
        return await self.backend.get_statistics()


# Factory functions and global instances
_database_backend = None


def create_sqlite_backend(db_path: str = "data/restaurants.db") -> SQLiteBackend:
    """Create SQLite backend instance."""
    return SQLiteBackend(db_path)


def create_postgresql_backend(
    host: str = "localhost",
    port: int = 5432,
    database: str = "zomoto_ai",
    username: str = "postgres",
    password: str = "",
    pool_size: int = 20
) -> PostgreSQLBackend:
    """Create PostgreSQL backend instance."""
    return PostgreSQLBackend(host, port, database, username, password, pool_size)


def get_database_backend() -> DatabaseBackend:
    """Get default database backend instance."""
    global _database_backend
    
    if _database_backend is None:
        # Try to determine which backend to use from environment
        import os
        db_type = os.getenv("DB_TYPE", "sqlite").lower()
        
        if db_type == "postgresql":
            _database_backend = create_postgresql_backend(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "5432")),
                database=os.getenv("DB_NAME", "zomoto_ai"),
                username=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "")
            )
        else:
            _database_backend = create_sqlite_backend(
                os.getenv("SQLITE_PATH", "data/restaurants.db")
            )
    
    return _database_backend
