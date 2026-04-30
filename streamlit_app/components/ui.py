import streamlit as st
from typing import Dict, Any, List
from .utils import get_unique_locations, get_unique_cuisines, format_currency


def render_preference_form() -> Dict[str, Any]:
    """
    Render the preference input form in the sidebar.
    
    Returns:
        Dictionary of user preferences
    """
    preferences = {}
    
    st.header("Your Preferences")
    
    # Location
    locations = get_unique_locations()
    location = st.selectbox(
        "Location",
        options=locations,
        index=0,
        help="Select your preferred location"
    )
    preferences["location"] = location
    
    # Cuisine
    cuisines = get_unique_cuisines()
    cuisine = st.selectbox(
        "Cuisine",
        options=["Any Cuisine"] + cuisines,
        index=0,
        help="Select your preferred cuisine"
    )
    preferences["cuisine"] = cuisine if cuisine != "Any Cuisine" else ""
    
    # Rating
    min_rating = st.slider(
        "Minimum Rating",
        min_value=0.0,
        max_value=5.0,
        value=4.0,
        step=0.5,
        help="Minimum restaurant rating"
    )
    preferences["min_rating"] = min_rating
    
    # Budget
    budget_option = st.radio(
        "Budget",
        options=["Any Budget", "Under ₹500", "₹500-₹1000", "₹1000-₹2000", "Above ₹2000"],
        index=0,
        help="Select your budget range"
    )
    
    if budget_option == "Under ₹500":
        preferences["budget"] = {"kind": "range", "max_cost_for_two": 500}
    elif budget_option == "₹500-₹1000":
        preferences["budget"] = {"kind": "range", "max_cost_for_two": 1000}
    elif budget_option == "₹1000-₹2000":
        preferences["budget"] = {"kind": "range", "max_cost_for_two": 2000}
    elif budget_option == "Above ₹2000":
        preferences["budget"] = {"kind": "range", "max_cost_for_two": 5000}
    else:
        preferences["budget"] = None
    
    # Optional constraints
    st.subheader("Optional Preferences")
    optional_constraints = []
    
    if st.checkbox("Quick Service"):
        optional_constraints.append("Quick Service")
    if st.checkbox("Family Friendly"):
        optional_constraints.append("Family Friendly")
    if st.checkbox("Outdoor Seating"):
        optional_constraints.append("Outdoor Seating")
    if st.checkbox("Pet Friendly"):
        optional_constraints.append("Pet Friendly")
    if st.checkbox("Live Music"):
        optional_constraints.append("Live Music")
    
    preferences["optional_constraints"] = optional_constraints
    
    return preferences


def render_restaurant_card(restaurant: Dict[str, Any], rank: int) -> None:
    """
    Render a single restaurant card.
    
    Args:
        restaurant: Restaurant data dictionary
        rank: Rank of the restaurant
    """
    with st.container():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"### #{rank} {restaurant['name']}")
            st.markdown(f"**Location:** {restaurant['location']}")
            
            # Cuisines
            cuisines = restaurant.get('cuisines', [])
            if cuisines:
                cuisine_tags = " ".join([f"`{c}`" for c in cuisines[:5]])
                st.markdown(f"**Cuisines:** {cuisine_tags}")
            
            # Rating and cost
            rating = restaurant.get('rating', 'N/A')
            cost = restaurant.get('cost_for_two', 'N/A')
            st.markdown(f"**Rating:** ⭐ {rating} | **Cost for Two:** {format_currency(cost) if cost != 'N/A' else cost}")
        
        with col2:
            st.metric("Rank", rank)
        
        # Explanation
        explanation = restaurant.get('explanation')
        if explanation:
            st.info(f"💡 {explanation}")
        
        st.markdown("---")


def render_results(results: Dict[str, Any]) -> None:
    """
    Render the recommendation results.
    
    Args:
        results: API response dictionary
    """
    st.success(f"Found {len(results.get('recommendations', []))} restaurants matching your preferences!")
    
    # Summary
    summary = results.get('summary', '')
    if summary:
        st.markdown(f"**Summary:** {summary}")
    
    # Processing time
    processing_time = results.get('processing_time_ms', 0)
    if processing_time:
        st.caption(f"Generated in {processing_time/1000:.2f} seconds")
    
    # Restaurant cards
    recommendations = results.get('recommendations', [])
    
    for idx, item in enumerate(recommendations, 1):
        restaurant = item.get('restaurant', {})
        render_restaurant_card(restaurant, idx)
    
    # Export option
    if recommendations:
        from .utils import export_to_csv
        st.subheader("Export Results")
        export_to_csv(recommendations)


def render_health_status(healthy: bool) -> None:
    """
    Render backend health status indicator.
    
    Args:
        healthy: Whether backend is healthy
    """
    if healthy:
        st.success("✅ Backend API is healthy")
    else:
        st.error("❌ Backend API is not responding")
