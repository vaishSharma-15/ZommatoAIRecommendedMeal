#!/usr/bin/env python
import sys
sys.path.insert(0, 'src')

import pandas as pd
import sqlite3
import json

# Read parquet file
df = pd.read_parquet('data/restaurants_processed.parquet')

# Connect to SQLite database
conn = sqlite3.connect('data/restaurants.db')
cursor = conn.cursor()

# Insert data
print(f'Loading {len(df)} restaurants into database...')
for index, row in df.iterrows():
    # Convert numpy arrays to lists for JSON serialization
    cuisines = row.get('cuisines', [])
    if hasattr(cuisines, 'tolist'):
        cuisines = cuisines.tolist()
    elif isinstance(cuisines, list):
        cuisines = [str(c) for c in cuisines]
    
    # Handle NaN values
    cost_for_two = row.get('cost_for_two', 0)
    if pd.isna(cost_for_two):
        cost_for_two = 0
    
    rating = row.get('rating', 0)
    if pd.isna(rating):
        rating = 0.0
    
    votes = row.get('votes', 0)
    if pd.isna(votes):
        votes = 0
    
    cursor.execute('''
        INSERT OR REPLACE INTO restaurants (id, name, location, city, area, cuisines, cost_for_two, rating, votes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        str(row.get('id', '')),
        str(row.get('name', '')),
        str(row.get('location', '')),
        str(row.get('city', '')),
        str(row.get('area', '')),
        json.dumps(cuisines),
        int(cost_for_two),
        float(rating),
        int(votes)
    ))

conn.commit()
conn.close()
print('Restaurant data loaded successfully')
