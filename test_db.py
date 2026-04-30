import asyncio
import os
import sys

# Setup environment
os.environ["DB_TYPE"] = "sqlite"
os.environ["SQLITE_PATH"] = "data/restaurants.db"

# Import backend modules
sys.path.insert(0, ".")
from src.zomoto_ai.backend.data import get_database_backend

async def main():
    print("Testing database connection...")
    db = get_database_backend()
    await db.connect()
    
    # Check table count
    stats = await db.get_statistics()
    print("Stats:", stats)
    
    # Query a specific restaurant id
    # First, let's get an ID from the database
    cursor = db._connection.cursor()
    cursor.execute("SELECT id FROM restaurants LIMIT 1")
    row = cursor.fetchone()
    if row:
        restaurant_id = row[0]
        print(f"Found test ID in DB: {restaurant_id}")
        
        # Test get_restaurant_by_id
        data = await db.get_restaurant_by_id(restaurant_id)
        if data:
            print("Successfully retrieved data!")
            print(data)
        else:
            print("get_restaurant_by_id RETURNED NONE!")
            
    # Try searching
    results = await db.search_by_preferences(location="Bangalore", limit=5)
    print(f"Search returned {len(results)} results")
    if results:
        print("First result ID:", results[0]['id'])
        
        # Test get_restaurant_by_id with this ID
        data2 = await db.get_restaurant_by_id(results[0]['id'])
        print(f"get_restaurant_by_id with search result ID: {'Success' if data2 else 'FAILED'}")

if __name__ == "__main__":
    asyncio.run(main())
