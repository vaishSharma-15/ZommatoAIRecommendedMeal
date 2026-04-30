import streamlit as st
from components.api import get_recommendations, check_backend_health
from components.ui import render_preference_form, render_results, render_health_status
from components.utils import validate_preferences

# Page configuration
st.set_page_config(
    page_title="Zomato AI Recommendations",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background-color: #f8f9fa;
    }
    .main-header {
        text-align: center;
        padding: 2rem 0;
    }
    .restaurant-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'preferences' not in st.session_state:
    st.session_state.preferences = None
if 'results' not in st.session_state:
    st.session_state.results = None
if 'backend_healthy' not in st.session_state:
    st.session_state.backend_healthy = None

# Main header
st.markdown("""
<div class="main-header">
    <h1>🍽️ Zomato AI Restaurant Recommendations</h1>
    <p>Find the perfect restaurant based on your preferences using AI-powered recommendations</p>
</div>
""", unsafe_allow_html=True)

# Check backend health
with st.spinner("Checking backend status..."):
    st.session_state.backend_healthy = check_backend_health()

# Display health status
st.subheader("System Status")
render_health_status(st.session_state.backend_healthy)

if not st.session_state.backend_healthy:
    st.warning("Backend API is not responding. Some features may not work properly.")

# Main content area
col1, col2 = st.columns([1, 3])

with col1:
    st.markdown("---")
    st.subheader("Preferences")
    
    # Preference form
    preferences = render_preference_form()
    
    # Generate recommendations button
    st.markdown("---")
    if st.button("🔍 Find Restaurants", type="primary", use_container_width=True):
        if validate_preferences(preferences):
            st.session_state.preferences = preferences
            
            with st.spinner("Finding the best restaurants for you..."):
                results = get_recommendations(preferences, top_n=5)
                
                if results:
                    st.session_state.results = results
                    st.success("Recommendations generated successfully!")
                else:
                    st.error("Failed to generate recommendations. Please try again.")

with col2:
    st.markdown("---")
    
    # Display results
    if st.session_state.results:
        st.subheader("Your Recommendations")
        render_results(st.session_state.results)
    else:
        st.info("👈 Select your preferences and click 'Find Restaurants' to get recommendations")
        
        # Show example
        st.markdown("---")
        st.subheader("How it works")
        st.markdown("""
        1. **Select Location**: Choose your preferred area
        2. **Choose Cuisine**: Pick your favorite cuisine type
        3. **Set Budget**: Specify your budget range
        4. **Add Preferences**: Select optional preferences like quick service, family-friendly, etc.
        5. **Get Recommendations**: Our AI will find the best restaurants for you
        """)
        
        # Features
        st.subheader("Features")
        st.markdown("""
        - 🤖 **AI-Powered**: Uses advanced LLM for intelligent ranking
        - 🎯 **Personalized**: Recommendations based on your specific preferences
        - ⚡ **Fast**: Quick response times with caching
        - 📊 **Explainable**: Get explanations for why each restaurant was recommended
        - 🔄 **Flexible**: Relaxation strategies when exact matches aren't found
        """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem 0;'>
    <p>Built with ❤️ using Streamlit & FastAPI</p>
    <p>Powered by Groq LLM for intelligent recommendations</p>
</div>
""", unsafe_allow_html=True)
