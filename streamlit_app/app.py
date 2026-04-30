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
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .main-header {
        text-align: center;
        padding: 3rem 0;
        color: white;
    }
    .main-header h1 {
        font-size: 3rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .main-header p {
        font-size: 1.2rem;
        opacity: 0.9;
    }
    .restaurant-card {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        margin-bottom: 1.5rem;
        transition: transform 0.2s;
    }
    .restaurant-card:hover {
        transform: translateY(-5px);
    }
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        padding-top: 2rem;
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

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem 0;'>
    <p>Built with ❤️ using Streamlit & FastAPI</p>
    <p>Powered by Groq LLM for intelligent recommendations</p>
</div>
""", unsafe_allow_html=True)
