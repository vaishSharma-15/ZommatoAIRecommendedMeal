import streamlit as st
from typing import List, Dict, Any


def format_currency(amount: int) -> str:
    """Format currency amount for display."""
    return f"₹{amount:,}"


def get_unique_locations() -> List[str]:
    """
    Get list of unique locations from the dataset.
    In production, this would fetch from the backend API.
    For now, return a sample list.
    """
    return [
        "Indiranagar",
        "Koramangala",
        "Whitefield",
        "HSR Layout",
        "Jayanagar",
        "BTM Layout",
        "Electronic City",
        "MG Road",
        "Brigade Road",
        "Church Street"
    ]


def get_unique_cuisines() -> List[str]:
    """
    Get list of unique cuisines from the dataset.
    In production, this would fetch from the backend API.
    For now, return a sample list.
    """
    return [
        "North Indian",
        "South Indian",
        "Chinese",
        "Italian",
        "Mexican",
        "Thai",
        "Japanese",
        "Continental",
        "Mediterranean",
        "American",
        "Biryani",
        "Cafe",
        "Desserts",
        "Beverages",
        "Healthy Food",
        "Salad",
        "Burger",
        "Pizza",
        "Seafood",
        "Kerala"
    ]


def validate_preferences(preferences: Dict[str, Any]) -> bool:
    """
    Validate user preferences before sending to API.
    
    Args:
        preferences: User preference dictionary
        
    Returns:
        True if valid, False otherwise
    """
    if not preferences.get("location"):
        st.error("Please select a location")
        return False
    
    if preferences.get("min_rating", 0) < 0 or preferences.get("min_rating", 5) > 5:
        st.error("Rating must be between 0 and 5")
        return False
    
    return True


def export_to_csv(data: List[Dict[str, Any]], filename: str = "recommendations.csv"):
    """
    Export recommendations to CSV format.
    
    Args:
        data: List of recommendation dictionaries
        filename: Name of the CSV file
    """
    import pandas as pd
    
    df = pd.DataFrame(data)
    csv = df.to_csv(index=False)
    st.download_button(
        label="Download as CSV",
        data=csv,
        file_name=filename,
        mime="text/csv"
    )
