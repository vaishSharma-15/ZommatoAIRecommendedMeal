import requests
import streamlit as st
from typing import Dict, Any, Optional


def get_api_url() -> str:
    """Get the current API URL from session state or secrets."""
    if "api_url" not in st.session_state:
        st.session_state.api_url = st.secrets.get("API_URL", "http://localhost:8000")
    return st.session_state.api_url


def get_recommendations(preferences: Dict[str, Any], top_n: int = 5) -> Optional[Dict[str, Any]]:
    """
    Call the FastAPI backend for restaurant recommendations.
    
    Args:
        preferences: User preference dictionary
        top_n: Number of recommendations to return
        
    Returns:
        JSON response from API or None if error occurs
    """
    api_url = get_api_url()
    try:
        response = requests.post(
            f"{api_url}/api/v1/recommendations",
            json={
                "preferences": preferences,
                "top_n": top_n,
                "include_explanations": True,
                "use_cache": True
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error("Request timed out. Please try again.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the backend. Please check if the API is running.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"API error: {e.response.status_code} - {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching recommendations: {str(e)}")
        return None


def check_backend_health() -> bool:
    """
    Check if the backend API is healthy.
    
    Returns:
        True if backend is healthy, False otherwise
    """
    api_url = get_api_url()
    try:
        response = requests.get(f"{api_url}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False
