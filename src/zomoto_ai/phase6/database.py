"""Database Backend for Phase 6 - Scalability Upgrades

Provides SQLite and PostgreSQL backends for fast filtering at larger dataset sizes.
"""

import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import os
from pathlib import Path
import json
from datetime import datetime

# Import domain models
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from zomoto_ai.phase0.domain.models import Restaurant, UserPreference, Budget


@dataclass
class DatabaseConfig:
    """Database configuration."""
    db_type: str  # "sqlite" or "postgresql"
    connection_string: str
    pool_size: int = 5
    max_overflow: int = 10


class DatabaseBackend:
    """Unified database backend supporting SQLite and PostgreSQL."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.db_type = config.db_type.lower()
        
        if self.db_type not in ["sqlite", "postgresql"]:
            raise ValueError(f"Unsupported database type: {self.db_type}")
        
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
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
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_city ON restaurants(city)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_area ON restaurants(area)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_rating ON restaurants(rating)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_cost ON restaurants(cost_for_two)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_location ON restaurants(location)")
            
            # Create full-text search index for location/cuisine
            if self.db_type == "postgresql":
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_restaurants_search 
                    ON restaurants USING gin(to_tsvector('english', name || ' ' || COALESCE(location, '') || ' ' || COALESCE(cuisines, '')))
                """)
            
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        """Get database connection."""
        if self.db_type == "sqlite":
            conn = sqlite3.connect(self.config.connection_string)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            try:
                yield conn
            finally:
                conn.close()
        
        elif self.db_type == "postgresql":
            conn = psycopg2.connect(self.config.connection_string)
            conn.cursor_factory = RealDictCursor
            try:
                yield conn
            finally:
                conn.close()
    
    def _serialize_cuisines(self, cuisines: List[str]) -> str:
        """Serialize cuisines list to JSON string."""
        return json.dumps(cuisines)
    
    def _deserialize_cuisines(self, cuisines_json: str) -> List[str]:
        """Deserialize JSON string to cuisines list."""
        if not cuisines_json:
            return []
        try:
            return json.loads(cuisines_json)
        except json.JSONDecodeError:
            return []
    
    def insert_restaurant(self, restaurant: Restaurant) -> bool:
        """Insert a restaurant into the database."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if self.db_type == "sqlite":
                    cursor.execute("""
                        INSERT OR REPLACE INTO restaurants 
                        (id, name, location, city, area, cuisines, cost_for_two, rating, votes, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        restaurant.id,
                        restaurant.name,
                        restaurant.location,
                        restaurant.city,
                        restaurant.area,
                        self._serialize_cuisines(restaurant.cuisines),
                        restaurant.cost_for_two,
                        restaurant.rating,
                        restaurant.votes
                    ))
                else:  # PostgreSQL
                    cursor.execute("""
                        INSERT INTO restaurants 
                        (id, name, location, city, area, cuisines, cost_for_two, rating, votes, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
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
                    """, (
                        restaurant.id,
                        restaurant.name,
                        restaurant.location,
                        restaurant.city,
                        restaurant.area,
                        self._serialize_cuisines(restaurant.cuisines),
                        restaurant.cost_for_two,
                        restaurant.rating,
                        restaurant.votes
                    ))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"Error inserting restaurant {restaurant.id}: {e}")
            return False
    
    def bulk_insert_restaurants(self, restaurants: List[Restaurant]) -> int:
        """Bulk insert multiple restaurants."""
        success_count = 0
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for restaurant in restaurants:
                try:
                    if self.db_type == "sqlite":
                        cursor.execute("""
                            INSERT OR REPLACE INTO restaurants 
                            (id, name, location, city, area, cuisines, cost_for_two, rating, votes, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (
                            restaurant.id,
                            restaurant.name,
                            restaurant.location,
                            restaurant.city,
                            restaurant.area,
                            self._serialize_cuisines(restaurant.cuisines),
                            restaurant.cost_for_two,
                            restaurant.rating,
                            restaurant.votes
                        ))
                    else:  # PostgreSQL
                        cursor.execute("""
                            INSERT INTO restaurants 
                            (id, name, location, city, area, cuisines, cost_for_two, rating, votes, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
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
                        """, (
                            restaurant.id,
                            restaurant.name,
                            restaurant.location,
                            restaurant.city,
                            restaurant.area,
                            self._serialize_cuisines(restaurant.cuisines),
                            restaurant.cost_for_two,
                            restaurant.rating,
                            restaurant.votes
                        ))
                    
                    success_count += 1
                    
                except Exception as e:
                    print(f"Error inserting restaurant {restaurant.id}: {e}")
            
            conn.commit()
        
        return success_count
    
    def get_restaurant_by_id(self, restaurant_id: str) -> Optional[Restaurant]:
        """Get a restaurant by ID."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM restaurants WHERE id = ?", (restaurant_id,))
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_restaurant(row)
                return None
                
        except Exception as e:
            print(f"Error getting restaurant {restaurant_id}: {e}")
            return None
    
    def _row_to_restaurant(self, row) -> Restaurant:
        """Convert database row to Restaurant object."""
        if self.db_type == "sqlite":
            return Restaurant(
                id=row["id"],
                name=row["name"],
                location=row["location"],
                city=row["city"],
                area=row["area"],
                cuisines=self._deserialize_cuisines(row["cuisines"]),
                cost_for_two=row["cost_for_two"],
                rating=row["rating"],
                votes=row["votes"]
            )
        else:  # PostgreSQL
            return Restaurant(
                id=row["id"],
                name=row["name"],
                location=row["location"],
                city=row["city"],
                area=row["area"],
                cuisines=self._deserialize_cuisines(row["cuisines"]),
                cost_for_two=row["cost_for_two"],
                rating=row["rating"],
                votes=row["votes"]
            )
    
    def search_restaurants(self, preference: UserPreference, limit: int = 50) -> List[Restaurant]:
        """Search restaurants based on user preferences."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Build query dynamically based on preferences
                query_parts = ["SELECT * FROM restaurants WHERE 1=1"]
                params = []
                
                # Location filtering
                if preference.location:
                    if self.db_type == "sqlite":
                        query_parts.append("""
                            (city LIKE ? OR area LIKE ? OR location LIKE ?)
                        """)
                        location_param = f"%{preference.location}%"
                        params.extend([location_param, location_param, location_param])
                    else:  # PostgreSQL
                        query_parts.append("""
                            (to_tsvector('english', COALESCE(city, '') || ' ' || COALESCE(area, '') || ' ' || COALESCE(location, '')) 
                            @@ plainto_tsquery('english', %s))
                        """)
                        params.append(preference.location)
                
                # Cuisine filtering
                if preference.cuisine:
                    if self.db_type == "sqlite":
                        query_parts.append("cuisines LIKE ?")
                        params.append(f"%{preference.cuisine}%")
                    else:  # PostgreSQL
                        query_parts.append("cuisines::jsonb ? %s")
                        params.append(preference.cuisine)
                
                # Rating filtering
                if preference.min_rating > 0:
                    query_parts.append("rating >= ?")
                    params.append(preference.min_rating)
                
                # Budget filtering
                if preference.budget:
                    if preference.budget.kind == "range" and preference.budget.max_cost_for_two:
                        query_parts.append("cost_for_two <= ?")
                        params.append(preference.budget.max_cost_for_two)
                
                # Add ordering and limit
                query_parts.append("ORDER BY rating DESC, votes DESC LIMIT ?")
                params.append(limit)
                
                query = " ".join(query_parts)
                
                if self.db_type == "sqlite":
                    cursor.execute(query, params)
                else:  # PostgreSQL
                    cursor.execute(query, params)
                
                rows = cursor.fetchall()
                return [self._row_to_restaurant(row) for row in rows]
                
        except Exception as e:
            print(f"Error searching restaurants: {e}")
            return []
    
    def get_restaurant_count(self) -> int:
        """Get total restaurant count."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM restaurants")
                row = cursor.fetchone()
                return row["count"] if row else 0
        except Exception as e:
            print(f"Error getting restaurant count: {e}")
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Basic counts
                cursor.execute("SELECT COUNT(*) as total FROM restaurants")
                total = cursor.fetchone()["total"]
                
                # Rating distribution
                cursor.execute("""
                    SELECT 
                        CASE 
                            WHEN rating >= 4.5 THEN '4.5+'
                            WHEN rating >= 4.0 THEN '4.0-4.4'
                            WHEN rating >= 3.5 THEN '3.5-3.9'
                            WHEN rating >= 3.0 THEN '3.0-3.4'
                            ELSE 'Below 3.0'
                        END as rating_range,
                        COUNT(*) as count
                    FROM restaurants 
                    WHERE rating IS NOT NULL
                    GROUP BY rating_range
                    ORDER BY rating_range
                """)
                rating_dist = {row["rating_range"]: row["count"] for row in cursor.fetchall()}
                
                # Top cities
                cursor.execute("""
                    SELECT city, COUNT(*) as count 
                    FROM restaurants 
                    WHERE city IS NOT NULL 
                    GROUP BY city 
                    ORDER BY count DESC 
                    LIMIT 10
                """)
                top_cities = {row["city"]: row["count"] for row in cursor.fetchall()}
                
                # Average cost
                cursor.execute("SELECT AVG(cost_for_two) as avg_cost FROM restaurants WHERE cost_for_two IS NOT NULL")
                avg_cost_row = cursor.fetchone()
                avg_cost = avg_cost_row["avg_cost"] if avg_cost_row else 0
                
                return {
                    "total_restaurants": total,
                    "rating_distribution": rating_dist,
                    "top_cities": top_cities,
                    "average_cost_for_two": round(avg_cost, 2) if avg_cost else 0,
                    "database_type": self.db_type
                }
                
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {"error": str(e)}
    
    def create_indexes(self):
        """Create additional performance indexes."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Composite indexes for common query patterns
            if self.db_type == "sqlite":
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_city_rating ON restaurants(city, rating DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cost_rating ON restaurants(cost_for_two, rating DESC)")
            else:  # PostgreSQL
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_city_rating ON restaurants(city, rating DESC)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cost_rating ON restaurants(cost_for_two, rating DESC)")
            
            conn.commit()
    
    def optimize_database(self):
        """Optimize database performance."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if self.db_type == "sqlite":
                cursor.execute("VACUUM")
                cursor.execute("ANALYZE")
            else:  # PostgreSQL
                cursor.execute("VACUUM ANALYZE")
                cursor.execute("REINDEX DATABASE")
            
            conn.commit()


class RestaurantRepository:
    """High-level repository for restaurant operations."""
    
    def __init__(self, db_backend: DatabaseBackend):
        self.db = db_backend
        self._cache = {}  # Simple in-memory cache
    
    def load_from_parquet(self, parquet_path: str) -> int:
        """Load restaurants from parquet file into database."""
        try:
            import pandas as pd
            
            # Load parquet file
            df = pd.read_parquet(parquet_path)
            
            # Convert to Restaurant objects
            restaurants = []
            for _, row in df.iterrows():
                # Handle NaN values
                cost_for_two = row.get("cost_for_two") if not pd.isna(row.get("cost_for_two")) else None
                rating = row.get("rating") if not pd.isna(row.get("rating")) else None
                votes = row.get("votes") if not pd.isna(row.get("votes")) else None
                
                # Handle cuisines
                cuisines = row.get("cuisines", [])
                if isinstance(cuisines, str):
                    cuisines = [c.strip() for c in cuisines.split(",")]
                
                restaurant = Restaurant(
                    id=str(row.get("id")),
                    name=str(row.get("name")),
                    location=row.get("location"),
                    city=row.get("city"),
                    area=row.get("area"),
                    cuisines=cuisines,
                    cost_for_two=cost_for_two,
                    rating=rating,
                    votes=votes
                )
                restaurants.append(restaurant)
            
            # Bulk insert
            return self.db.bulk_insert_restaurants(restaurants)
            
        except Exception as e:
            print(f"Error loading from parquet: {e}")
            return 0
    
    def search_by_preferences(self, preference: UserPreference, limit: int = 50) -> List[Restaurant]:
        """Search restaurants by user preferences with caching."""
        # Create cache key
        cache_key = self._create_cache_key(preference, limit)
        
        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Search database
        results = self.db.search_restaurants(preference, limit)
        
        # Cache results (simple TTL - in production, use Redis)
        self._cache[cache_key] = results
        
        return results
    
    def _create_cache_key(self, preference: UserPreference, limit: int) -> str:
        """Create cache key for preference search."""
        key_data = {
            "location": preference.location,
            "budget": asdict(preference.budget) if preference.budget else None,
            "cuisine": preference.cuisine,
            "min_rating": preference.min_rating,
            "optional_constraints": preference.optional_constraints,
            "limit": limit
        }
        return str(hash(json.dumps(key_data, sort_keys=True)))
    
    def get_by_id(self, restaurant_id: str) -> Optional[Restaurant]:
        """Get restaurant by ID with caching."""
        if restaurant_id in self._cache:
            return self._cache[restaurant_id]
        
        restaurant = self.db.get_restaurant_by_id(restaurant_id)
        if restaurant:
            self._cache[restaurant_id] = restaurant
        
        return restaurant
    
    def clear_cache(self):
        """Clear repository cache."""
        self._cache.clear()
    
    def get_repository_stats(self) -> Dict[str, Any]:
        """Get repository statistics."""
        return {
            "cache_size": len(self._cache),
            "database_stats": self.db.get_statistics()
        }


def create_sqlite_backend(db_path: str = "restaurants.db") -> DatabaseBackend:
    """Create SQLite database backend."""
    return DatabaseBackend(DatabaseConfig(
        db_type="sqlite",
        connection_string=db_path
    ))


def create_postgresql_backend(
    host: str = "localhost",
    port: int = 5432,
    database: str = "zomoto_ai",
    username: str = "postgres",
    password: str = None
) -> DatabaseBackend:
    """Create PostgreSQL database backend."""
    password = password or os.getenv("POSTGRES_PASSWORD")
    connection_string = f"postgresql://{username}:{password}@{host}:{port}/{database}"
    
    return DatabaseBackend(DatabaseConfig(
        db_type="postgresql",
        connection_string=connection_string
    ))


if __name__ == "__main__":
    # Example usage
    
    # SQLite backend
    sqlite_db = create_sqlite_backend("test_restaurants.db")
    repo = RestaurantRepository(sqlite_db)
    
    # Load from parquet
    loaded_count = repo.load_from_parquet("data/restaurants_processed.parquet")
    print(f"Loaded {loaded_count} restaurants into SQLite")
    
    # Search
    preference = UserPreference(
        location="Bangalore",
        min_rating=4.0,
        budget=Budget(kind="range", max_cost_for_two=1000)
    )
    
    results = repo.search_by_preferences(preference, limit=10)
    print(f"Found {len(results)} restaurants matching preferences")
    
    # Statistics
    stats = repo.get_repository_stats()
    print("Repository stats:", json.dumps(stats, indent=2, default=str))
