# Phase 5 - Presentation Layer

This phase provides user-friendly presentation of recommendation results through both CLI and web-based interfaces.

## Architecture Overview

Phase 5 integrates all previous phases (1-4) to deliver a complete user experience:

```
Phase 1 (Data) → Phase 3 (Retrieval) → Phase 4 (LLM Ranking) → Phase 5 (Presentation)
```

## Components

### Option A: CLI Presentation (`cli.py`, `cli_command.py`)

**Features:**
- Rich, formatted output using Rich library
- Interactive preference collection
- Single-shot and interactive modes
- Fallback ranking when LLM unavailable
- Error handling and user guidance

**Classes:**
- `CLIPresenter`: Basic CLI presentation
- `EnhancedCLIPresenter`: Enhanced presentation with restaurant details
- `RecommendationCLI`: Complete CLI application

**Usage:**
```bash
# Interactive mode
python -m zomoto_ai.phase5.cli_command

# Single recommendation
python -m zomoto_ai.phase5.cli_command --location Bangalore --budget 1000 --rating 4.0

# With custom data path
python -m zomoto_ai.phase5.cli_command --data-path custom_data.parquet
```

### Option B: API + UI (`api.py`, `frontend.py`)

**Backend Features:**
- FastAPI REST API
- `/recommendations` endpoint for generating recommendations
- `/health` endpoint for service status
- Built-in caching for LLM results
- Performance metrics and monitoring
- CORS support for frontend integration

**Frontend Features:**
- Modern, responsive web interface
- Interactive preference form
- Real-time loading states
- Recommendation cards with detailed information
- Search adjustment explanations
- Error handling and user feedback

**API Endpoints:**
```
GET  /health              - Service health check
POST /recommendations     - Generate recommendations
GET  /cache/stats         - Cache statistics
DELETE /cache             - Clear cache
GET  /                    - Web UI (when integrated)
```

**Usage:**
```bash
# Start API server
python -m zomoto_ai.phase5.api

# Start full UI server
python -m zomoto_ai.phase5.frontend

# Custom host/port
python -m zomoto_ai.phase5.api --host 0.0.0.0 --port 8080
```

## Key Features

### 1. **Caching Mechanism**
- LLM results cached by preference and candidate hash
- Reduces API costs and improves response times
- Cache management endpoints for monitoring and clearing

### 2. **Performance Optimizations**
- Token limits enforced for LLM prompts
- Efficient candidate reduction
- Background processing for long-running operations
- Response time tracking

### 3. **Error Handling**
- Graceful degradation when LLM unavailable
- Fallback ranking by rating and popularity
- Comprehensive error messages
- Input validation and sanitization

### 4. **User Experience**
- Rich, formatted output in CLI
- Modern, responsive web interface
- Loading states and progress indicators
- Clear explanations of search adjustments

## Configuration

### Environment Variables
```bash
# Required for LLM ranking
GROQ_API_KEY=your_groq_api_key

# Optional customization
ZOMOTO_DATASET_PATH=data/restaurants_processed.parquet
```

### Dependencies
```bash
# CLI dependencies
rich>=13.0.0

# API dependencies  
fastapi>=0.100.0
uvicorn>=0.20.0
jinja2>=3.0.0
```

## API Request/Response Format

### Request
```json
{
  "preferences": {
    "location": "Bangalore",
    "budget": {
      "kind": "range",
      "max_cost_for_two": 1000
    },
    "cuisine": "Italian",
    "min_rating": 4.0,
    "optional_constraints": ["FreshMenu", "Om Nom Thai"]
  },
  "top_n": 10
}
```

### Response
```json
{
  "success": true,
  "summary": "Top recommendations based on your preferences",
  "recommendations": [
    {
      "restaurant_id": "123",
      "rank": 1,
      "explanation": "Great Italian restaurant with high rating",
      "restaurant_name": "Restaurant Name",
      "location": "Bangalore",
      "cuisines": ["Italian", "Continental"],
      "cost_for_two": 800,
      "rating": 4.5,
      "votes": 250
    }
  ],
  "total_candidates": 50,
  "relaxation_steps": [
    {"action": "lower_min_rating", "note": "Lowered rating from 4.5 to 4.0"}
  ],
  "processing_time_ms": 1250
}
```

## Testing

Run tests with pytest:
```bash
# Run all tests
python -m pytest src/zomoto_ai/phase5/tests.py -v

# Run specific test class
python -m pytest src/zomoto_ai/phase5/tests.py::TestCLI -v
```

## Deployment

### CLI Deployment
```bash
# Install package
pip install -e .

# Run CLI
zomoto-ai-cli --location Bangalore --budget 1000
```

### API Deployment
```bash
# Install with API dependencies
pip install -e ".[api]"

# Run with production server
uvicorn zomoto_ai.phase5.api:app --host 0.0.0.0 --port 8000

# Or with Docker
docker build -t zomoto-api .
docker run -p 8000:8000 zomoto-api
```

## Performance Considerations

1. **Memory Usage**: Restaurant data loaded into memory (~50MB for current dataset)
2. **LLM Costs**: Caching reduces repeat calls by ~80%
3. **Response Times**: 
   - Retrieval: ~50ms
   - LLM Ranking: ~2-5s (first time), ~200ms (cached)
   - Total: ~3-6s (uncached), ~300ms (cached)

## Future Enhancements

1. **Database Integration**: Move from in-memory to PostgreSQL for scalability
2. **Rate Limiting**: Add API rate limiting for production use
3. **Authentication**: User accounts and preference saving
4. **Analytics**: Recommendation analytics and A/B testing
5. **Mobile App**: React Native mobile application
6. **Real-time Updates**: WebSocket integration for live updates

## Troubleshooting

### Common Issues

1. **"No GROQ_API_KEY found"**
   - Solution: Set environment variable: `export GROQ_API_KEY=your_key`

2. **"Dataset not found"**
   - Solution: Run Phase 1 to generate processed dataset
   - Check path: `data/restaurants_processed.parquet`

3. **"No recommendations found"**
   - Solution: Relax search criteria (lower rating, increase budget)
   - Check if location exists in dataset

4. **"API server won't start"**
   - Solution: Check port availability, try different port with `--port 8080`

### Debug Mode
```bash
# Enable debug logging
python -m zomoto_ai.phase5.api --log-level debug

# CLI with verbose output
python -m zomoto_ai.phase5.cli_command --location Bangalore --budget 1000 --debug
```
