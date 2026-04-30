#!/usr/bin/env python3
"""
Investigate the restaurant data to understand why no Delhi restaurants were found
"""

import os
import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from zomoto_ai.phase3.retrieval import load_restaurants_from_parquet


def main():
    print("=== Data Investigation ===\n")
    
    # Load restaurants
    data_path = "data/restaurants_processed.parquet"
    print(f"Loading restaurants from {data_path}...")
    restaurants = load_restaurants_from_parquet(data_path)
    print(f"Loaded {len(restaurants)} restaurants\n")
    
    # Check cities in the dataset
    cities = {}
    areas = {}
    locations = {}
    
    for restaurant in restaurants:
        if restaurant.city:
            cities[restaurant.city] = cities.get(restaurant.city, 0) + 1
        if restaurant.area:
            areas[restaurant.area] = areas.get(restaurant.area, 0) + 1
        if restaurant.location:
            locations[restaurant.location] = locations.get(restaurant.location, 0) + 1
    
    print("=== Top Cities ===")
    for city, count in sorted(cities.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"{city}: {count}")
    
    print("\n=== Cities containing 'delhi' (case insensitive) ===")
    delhi_cities = {city: count for city, count in cities.items() if 'delhi' in city.lower()}
    for city, count in sorted(delhi_cities.items(), key=lambda x: x[1], reverse=True):
        print(f"{city}: {count}")
    
    print("\n=== Areas containing 'delhi' ===")
    delhi_areas = {area: count for area, count in areas.items() if 'delhi' in area.lower()}
    for area, count in sorted(delhi_areas.items(), key=lambda x: x[1], reverse=True):
        print(f"{area}: {count}")
    
    print("\n=== Locations containing 'delhi' ===")
    delhi_locations = {loc: count for loc, count in locations.items() if 'delhi' in loc.lower()}
    for loc, count in sorted(delhi_locations.items(), key=lambda x: x[1], reverse=True):
        print(f"{loc}: {count}")
    
    # Check restaurants with budget <= 1000 and rating >= 4.5
    print("\n=== Restaurants with budget <= 1000 and rating >= 4.5 ===")
    good_restaurants = []
    for restaurant in restaurants:
        if (restaurant.cost_for_two and restaurant.cost_for_two <= 1000 and 
            restaurant.rating and restaurant.rating >= 4.5):
            good_restaurants.append(restaurant)
    
    print(f"Found {len(good_restaurants)} restaurants meeting budget and rating criteria")
    
    if good_restaurants:
        print("\nSample of restaurants meeting criteria:")
        for i, restaurant in enumerate(good_restaurants[:5], 1):
            print(f"{i}. {restaurant.name}")
            print(f"   City: {restaurant.city}")
            print(f"   Area: {restaurant.area}")
            print(f"   Location: {restaurant.location}")
            print(f"   Cost: {restaurant.cost_for_two}, Rating: {restaurant.rating}")
            print()
    
    # Test location matching function manually
    print("=== Manual location matching test ===")
    from zomoto_ai.phase3.retrieval import _location_match
    
    test_location = "Delhi"
    matches = 0
    sample_matches = []
    
    for restaurant in restaurants:
        if _location_match(restaurant, test_location):
            matches += 1
            if len(sample_matches) < 5:
                sample_matches.append(restaurant)
    
    print(f"Restaurants matching 'Delhi': {matches}")
    
    if sample_matches:
        print("\nSample matches:")
        for i, restaurant in enumerate(sample_matches, 1):
            print(f"{i}. {restaurant.name}")
            print(f"   City: {restaurant.city}")
            print(f"   Area: {restaurant.area}")
            print(f"   Location: {restaurant.location}")
            print()


if __name__ == "__main__":
    main()
