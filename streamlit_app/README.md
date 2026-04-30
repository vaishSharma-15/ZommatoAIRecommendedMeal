# Zomato AI Recommendations - Streamlit App

A Streamlit-based user interface for the Zomato AI Restaurant Recommendation System.

## Features

- **Simple Python-based UI**: No JavaScript/React knowledge required
- **Real-time Recommendations**: Get AI-powered restaurant suggestions
- **Interactive Filters**: Location, cuisine, budget, rating preferences
- **Health Monitoring**: Check backend API status
- **Export Results**: Download recommendations as CSV

## Installation

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set environment variables:**
```bash
export API_URL="http://localhost:8000"
```

Or create a `.streamlit/secrets.toml` file:
```toml
API_URL = "http://localhost:8000"
```

## Running Locally

```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`

## Project Structure

```
streamlit_app/
├── app.py                  # Main Streamlit application
├── components/
│   ├── __init__.py         # Package initialization
│   ├── api.py              # API client functions
│   ├── ui.py               # UI components
│   └── utils.py            # Helper functions
├── requirements.txt        # Python dependencies
├── .streamlit/
│   └── config.toml        # Streamlit configuration
├── Procfile              # Deployment configuration
└── README.md             # This file
```

## Deployment Options

### 1. Streamlit Cloud (Recommended)

1. Push code to GitHub
2. Go to [Streamlit Cloud](https://streamlit.io/cloud)
3. Connect your repository
4. Set environment variables:
   - `API_URL`: Your backend API URL
5. Deploy automatically

### 2. Render

1. Create new Web Service on Render
2. Connect GitHub repository
3. Build command: `pip install -r requirements.txt`
4. Start command: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`
5. Set environment variables

### 3. Hugging Face Spaces

1. Create new Space on Hugging Face
2. Choose Streamlit SDK
3. Upload files or connect GitHub
4. Set secrets:
   - `API_URL`: Your backend API URL
5. Deploy

### 4. Railway

1. New project from GitHub
2. Add Streamlit service
3. Configure environment variables
4. Deploy

## Environment Variables

- `API_URL`: The URL of the FastAPI backend (default: `http://localhost:8000`)

## Usage

1. **Select Location**: Choose your preferred area from the dropdown
2. **Choose Cuisine**: Pick your favorite cuisine type
3. **Set Budget**: Specify your budget range
4. **Set Rating**: Minimum restaurant rating threshold
5. **Add Preferences**: Select optional preferences (Quick Service, Family Friendly, etc.)
6. **Click "Find Restaurants"**: Get AI-powered recommendations

## Backend Integration

The Streamlit app integrates with the existing FastAPI backend:
- Calls `POST /api/v1/recommendations` endpoint
- Calls `GET /health` for health checks
- Handles errors gracefully with user-friendly messages

## Development

### Adding New Features

1. **New UI Components**: Add to `components/ui.py`
2. **New API Functions**: Add to `components/api.py`
3. **Helper Functions**: Add to `components/utils.py`

### Customization

Edit `.streamlit/config.toml` to customize:
- Theme colors
- Font settings
- Client behavior
- Logger settings

## Troubleshooting

**Backend not responding:**
- Check if the FastAPI backend is running
- Verify the `API_URL` environment variable
- Check network connectivity

**Import errors:**
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version (requires Python 3.8+)

**Port already in use:**
- Change port in `.streamlit/config.toml`
- Or run with: `streamlit run app.py --server.port 8502`

## License

This is part of the Zomato AI Recommendation System project.
