# Phase-wise Architecture — ZomotoAIRecommendation

This document breaks the system into implementation phases. Each phase adds a small set of components with clear contracts so you can ship incrementally (starting from a working CLI) and later evolve into an API/UI.

---

## Phase 0 — Foundations (repo + contracts)

### Goal
Establish stable schemas/interfaces so ingestion, retrieval, and LLM ranking can evolve independently.

### Components
- **Domain models**
  - `Restaurant`: `id`, `name`, `location/city/area`, `cuisines[]`, `cost_for_two`, `rating`, `votes` (if available), plus any optional attributes.
  - `UserPreference`: `location`, `budget` (bucket or numeric), `cuisine`, `min_rating`, `optional_constraints[]`.
  - `CandidateSet`: a compact list of candidate `Restaurant` entries used for ranking.
  - `RecommendationResult`: ranked list of restaurants with grounded explanations.
- **LLM provider abstraction**
  - `LLMClient` interface so you can swap providers (hosted/local) without changing core logic.
- **Basic Web UI (input source)**
  - A minimal preference form (location, budget, cuisine, min rating, optional constraints) that produces a valid `UserPreference`.
  - Can be standalone (mocked submit) or backed by a thin endpoint later; the key is establishing the UI contract early.

### Deliverables
- A minimal runnable entrypoint (even if it just prints “wiring OK”).
- A single place to configure: dataset path, model/provider settings, limits like `TOP_N`.
- A basic Web UI screen that is the primary source of user input (replacing CLI-first for preference collection).

---

## Phase 1 — Data ingestion & preprocessing (offline build step)

### Goal
Produce a clean, normalized restaurant index from the Hugging Face dataset:
`ManikaSaini/zomato-restaurant-recommendation`.

### Components
- **Dataset loader**: loads the dataset (local cache allowed).
- **Cleaner/Normalizer**
  - Handle missing values.
  - Canonicalize location strings (e.g., whitespace, casing, common aliases).
  - Canonicalize cuisines (split multi-cuisine fields, trim, consistent casing).
  - Parse numeric fields: rating, votes, cost.
- **Extractor**: retains minimum fields required for recommendation.

### Storage
- **Processed dataset artifact**: `parquet` or `csv` (fast to iterate).
- Optional: `sqlite` for querying if you want structured filters without loading everything into memory.

### Deliverables
- `build_index` script/command that creates the processed artifact deterministically.
- Summary stats in logs: row count, missing rates, distinct locations/cuisines.

---

## Phase 2 — User preference collection (Web UI first)

### Goal
Collect preferences reliably and normalize them into `UserPreference`.

### Components
- **Input layer**
  - Web UI form for location, budget, cuisine, min rating, optional constraints.
- **Validation + normalization**
  - Map free text into canonical forms (e.g., known location/cuisine vocab).
  - Enforce numeric constraints (e.g., rating range 0–5).

### Deliverables
- A Web UI flow that outputs a validated `UserPreference` object.
- Clear error messages and defaults (e.g., missing min rating → 0).

---

## Phase 3 — Retrieval & filtering (structured, explainable)

### Goal
Filter the restaurant index using structured criteria and keep the candidate list small enough for the LLM.

### Components
- **Candidate Generator (structured filtering)**
  - Filters by location, cuisine, budget/cost, min rating.
- **Edge-case handler (no matches)**
  - Controlled relax strategy (recorded):
    - Expand/normalize location (city vs area).
    - Relax cuisine match (exact → partial → “similar”/any).
    - Lower min rating.
    - Expand budget range.
  - If still no matches: return a clear explanation.
- **Reducer (LLM budget control)**
  - If too many candidates: pick `top-N` by rating/votes and apply diversity sampling (area/cuisine/price buckets).

### Deliverables
- Deterministic candidate selection with a clear rationale.
- `CandidateSet` JSON that is compact and stable for prompting.

---

## Phase 4 — LLM ranking & grounded explanations (no hallucinations)

### Goal
Use an LLM to rank candidates and generate short, human-readable explanations grounded in the provided attributes.

### Components
- **Prompt Builder**
  - Includes: user preferences + compact candidate list.
  - Instructs the model to only use provided fields.
- **LLM Ranker**
  - Returns ranked restaurants (top 3–10) and 1–3 sentence explanations each.
- **Output validator (grounding guardrail)**
  - Ensures every returned restaurant exists in the candidate set.
  - Ensures explanations don’t reference attributes not present in the candidate data.
  - If invalid: re-ask with a correction prompt or drop invalid items.

### Deliverables
- Ranked list + explanations that pass grounding validation.
- Optional comparison summary across top results.

---

## Phase 5 — Presentation (CLI → API/UI)

### Goal
Present results in a user-friendly format.

### Option A: CLI (fastest path)
- Prints top recommendations with required fields and explanations.

### Option B: API + UI
- **Backend**
  - `POST /recommendations`: accepts `UserPreference`, returns `RecommendationResult`.
- **Frontend**
  - Preference form + results cards.

### Performance & cost basics
- Cache LLM results by `(preference_hash, candidate_ids_hash)` to reduce repeat calls.
- Enforce token/size limits by truncating candidate fields.

### Deliverables
- A user-friendly output format meeting acceptance criteria:
  - Name, location, cuisines, rating, cost, explanation.

---

## Phase 6 — Reliability, evaluation, and production hardening

### Goal
Make the system robust, testable, and scalable for production deployment.

### Components
- **Testing Framework**
  - Unit tests: normalization, filtering, relax strategy (50+ tests covering all phases).
  - Golden tests: prompt + output validation (prevents hallucination regressions).
  - Integration tests: end-to-end pipeline testing with 94% coverage.
  - Performance benchmarks and load testing suite.
- **Observability & Monitoring**
  - Structured JSON logs with correlation IDs and trace context.
  - Real-time metrics collection: response times, error rates, LLM latency.
  - Health checks: database, LLM service, cache system monitoring.
  - Alerting: email/webhook notifications for threshold breaches.
- **Scalability Upgrades**
  - Database backends: SQLite (development) and PostgreSQL (production) with unified interface.
  - Connection pooling and performance indexing for large datasets.
  - Redis-based distributed caching and session management.
  - Async job queue for LLM calls with priority processing and retry logic.
- **Production Hardening**
  - Rate limiting: token bucket algorithm with multiple time windows.
  - Reliability patterns: circuit breakers, exponential backoff retries, timeout enforcement.
  - Fallback behavior: simplified ranking algorithms when LLM fails.
  - Production deployment: Docker, Docker Compose, Kubernetes manifests.

### Deliverables
- Comprehensive test suite with automated reporting.
- Production-ready monitoring and alerting system.
- Scalable database architecture with caching layer.
- Complete production deployment configuration.
- Clear operational limits and failure modes (timeouts, retries, fallback behavior).

---

## Phase 7 — Streamlit Deployment (Alternative UI Option)

### Goal
Create a Streamlit-based user interface as an alternative to the Next.js frontend, providing a simpler, Python-based deployment option that can be easily hosted on free platforms.

### Components
- **Streamlit Application**
  - Simple, Python-based UI for preference collection
  - Real-time recommendation display
  - Interactive filters and visualizations
- **API Integration**
  - Direct calls to existing FastAPI backend
  - Session state management for user preferences
  - Error handling and loading states
- **Deployment Configuration**
  - `requirements.txt` with Streamlit dependencies
  - `.streamlit/config.toml` for app configuration
  - `Procfile` for cloud deployment

### Streamlit UI Components
- **Preference Input Form**
  - Location selector (dropdown with autocomplete)
  - Cuisine multi-select
  - Budget slider/range input
  - Rating threshold slider
  - Optional constraints checkboxes
- **Results Display**
  - Restaurant cards with key information
  - Expandable explanations
  - Rating visualization
  - Cuisine tags
- **Additional Features**
  - Session history sidebar
  - Export results to CSV
  - Basic analytics dashboard
  - Comparison view for multiple restaurants

### File Structure
```
streamlit_app/
├── app.py                  # Main Streamlit application
├── pages/
│   ├── 1_🏠_Home.py        # Home page with quick search
│   ├── 2_🔍_Recommend.py    # Full recommendation form
│   └── 3_📊_Analytics.py   # Analytics dashboard
├── components/
│   ├── ui.py              # Reusable UI components
│   ├── api.py             # API client functions
│   └── utils.py           # Helper functions
├── assets/
│   ├── images/            # Static images
│   └── styles/            # Custom CSS
├── requirements.txt       # Python dependencies
├── .streamlit/
│   └── config.toml        # Streamlit configuration
└── Procfile              # Deployment configuration
```

### Streamlit Configuration (.streamlit/config.toml)
```toml
[theme]
primaryColor = "#E23744"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F5"
textColor = "#262730"
font = "sans serif"

[client]
showErrorDetails = false
maxUploadSize = 200

[logger]
level = "info"

[browser]
gatherUsageStats = false
```

### Requirements.txt
```
streamlit==1.28.0
requests==2.31.0
pandas==2.1.0
plotly==5.17.0
altair==5.0.0
```

### Procfile (for deployment)
```
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

### Deployment Options

#### 1. Streamlit Cloud (Free - Recommended)
- **URL**: https://streamlit.io/cloud
- **Features**: Free tier, easy GitHub integration, automatic deployments
- **Steps**:
  1. Push code to GitHub
  2. Connect Streamlit Cloud to repo
  3. Set environment variables (API_URL, GROQ_API_KEY)
  4. Deploy automatically

#### 2. Render (Free)
- **URL**: https://render.com
- **Features**: Free web service, supports Python
- **Steps**:
  1. Create new Web Service
  2. Connect GitHub repo
  3. Build command: `pip install -r requirements.txt`
  4. Start command from Procfile
  5. Set environment variables

#### 3. Railway (Free tier with credits)
- **URL**: https://railway.app
- **Features**: Easy deployment, free credits
- **Steps**:
  1. New project from GitHub
  2. Add Streamlit service
  3. Configure environment variables
  4. Deploy

#### 4. Hugging Face Spaces (Free)
- **URL**: https://huggingface.co/spaces
- **Features**: Free hosting, community visibility
- **Steps**:
  1. Create new Space
  2. Choose Streamlit SDK
  3. Upload files or connect GitHub
  4. Set secrets (environment variables)
  5. Deploy

### Integration with Existing Backend
```python
# components/api.py
import requests
import streamlit as st

API_URL = st.secrets.get("API_URL", "http://localhost:8000")

def get_recommendations(preferences):
    """Call the FastAPI backend for recommendations"""
    try:
        response = requests.post(
            f"{API_URL}/api/v1/recommendations",
            json={
                "preferences": preferences,
                "top_n": 5,
                "include_explanations": True,
                "use_cache": True
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching recommendations: {str(e)}")
        return None
```

### Example Streamlit App Structure
```python
# app.py
import streamlit as st
from components.api import get_recommendations
from components.ui import render_preference_form, render_results

st.set_page_config(
    page_title="Zomato AI Recommendations",
    page_icon="🍽️",
    layout="wide"
)

st.title("🍽️ Zomato AI Restaurant Recommendations")
st.markdown("Find the perfect restaurant based on your preferences")

# Session state for preferences
if 'preferences' not in st.session_state:
    st.session_state.preferences = None

# Preference form
with st.sidebar:
    st.header("Your Preferences")
    preferences = render_preference_form()

# Get recommendations
if st.button("Find Restaurants", type="primary"):
    with st.spinner("Finding the best restaurants for you..."):
        results = get_recommendations(preferences)
        st.session_state.preferences = preferences
        st.session_state.results = results

# Display results
if 'results' in st.session_state and st.session_state.results:
    render_results(st.session_state.results)
```

### Advantages of Streamlit Deployment
- **Simplicity**: Pure Python, no JavaScript/React knowledge needed
- **Rapid Development**: Build UI in hours, not days
- **Free Hosting**: Multiple free tier options available
- **Easy Maintenance**: Single Python file can be the entire app
- **Built-in Components**: Sliders, dropdowns, charts out of the box
- **Hot Reload**: Automatic updates during development

### Limitations
- **Less Customization**: Limited styling compared to custom React apps
- **Performance**: Not as performant as compiled frontend frameworks
- **State Management**: Session state is basic compared to React state
- **Mobile Experience**: Not as polished as responsive web apps

### Deliverables
- Fully functional Streamlit application
- Deployment configuration files
- Documentation for deployment to chosen platform
- Integration with existing FastAPI backend
- Environment variable setup guide

---

## Complete System Architecture (Post-Phase 7)

### Backend Architecture

#### **API Layer (FastAPI)**
```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                     │
├─────────────────────────────────────────────────────────────┤
│  • POST /recommendations     - Main recommendation endpoint │
│  • GET  /health             - Service health check         │
│  • GET  /metrics            - Prometheus metrics endpoint   │
│  • GET  /cache/statFrontend Architecture - Next.js Application
This document provides comprehensive specifications for the Next.js frontend that integrates with the Zomoto AI Recommendation System backend.

🎯 Project Overview
Build a modern, responsive web application that integrates with a FastAPI backend for restaurant recommendations. The app should provide an intuitive user experience for discovering restaurants based on user preferences.

🏗️ Technical Requirements
Framework & Stack
Framework: Next.js 14+ with App Router
Styling: Tailwind CSS with modern design system
State Management: Zustand or React Context API
HTTP Client: Axios with interceptors for error handling
UI Components: Headless UI or shadcn/ui components
Icons: Lucide React or Heroicons
Form Handling: React Hook Form with Zod validation
Animations: Framer Motion for smooth transitions
Charts: Recharts for analytics dashboard
API Integration
The frontend must integrate with these backend endpoints:

POST /api/v1/recommendations - Generate recommendations
POST /api/v1/recommendations/async - Async recommendations
GET /api/v1/jobs/{job_id} - Job status
GET /api/v1/health - System health
GET /api/v1/metrics - Performance metrics
GET /api/v1/cache/stats - Cache statistics
🎨 Design Requirements
Design System
Primary Colors: Orange/Red theme (food-related)
Secondary Colors: Neutral grays and whites
Typography: Inter or Poppins font family
Spacing: Consistent 8px grid system
Border Radius: 8px for cards, 4px for buttons
Shadows: Subtle elevation with consistent blur
Component Library
Create reusable components:

Button (primary, secondary, outline, ghost)
Input (text, email, number, search)
Select (single, multi-select)
Card (restaurant, recommendation, stats)
Modal (confirmation, details, forms)
Badge (cuisine tags, ratings, status)
Skeleton (loading states)
Toast (notifications, errors)
Responsive Design
Mobile: 320px - 768px
Tablet: 768px - 1024px
Desktop: 1024px+
Large Desktop: 1440px+
Accessibility
WCAG 2.1 AA compliance
Semantic HTML5 elements
ARIA labels and roles
Keyboard navigation support
Screen reader compatibility
Focus management
Color contrast ratios
🔧 Technical Implementation
Project Structure
src/
├── app/                    # App Router
│   ├── (auth)/            # Auth routes
│   ├── dashboard/         # Dashboard
│   ├── recommendations/   # Recommendation pages
│   ├── restaurants/       # Restaurant pages
│   ├── globals.css        # Global styles
│   ├── layout.tsx         # Root layout
│   └── page.tsx           # Home page
├── components/             # Reusable components
│   ├── ui/               # Base UI components
│   ├── forms/            # Form components
│   ├── cards/            # Card components
│   └── layout/           # Layout components
├── lib/                   # Utilities
│   ├── api.ts            # API client
│   ├── utils.ts          # Helper functions
│   └── validations.ts    # Zod schemas
├── hooks/                 # Custom hooks
├── store/                 # State management
├── types/                 # TypeScript types
└── styles/                # CSS modules
API Client Setup
// lib/api.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 30000,
});

// Request interceptor for auth
apiClient.interceptors.request.use((config) => {
  // Add auth headers if needed
  return config;
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle common errors
    return Promise.reject(error);
  }
);
State Management
// store/useRecommendations.ts
import { create } from 'zustand';

interface RecommendationState {
  recommendations: Recommendation[];
  loading: boolean;
  error: string | null;
  setRecommendations: (recs: Recommendation[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useRecommendationStore = create<RecommendationState>((set) => ({
  recommendations: [],
  loading: false,
  error: null,
  setRecommendations: (recs) => set({ recommendations: recs }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}));
Form Validation
// lib/validations.ts
import { z } from 'zod';

export const preferenceSchema = z.object({
  location: z.string().min(2, 'Location must be at least 2 characters'),
  cuisine: z.string().optional(),
  budget: z.object({
    kind: z.enum(['range', 'exact']),
    maxCostForTwo: z.number().positive().optional(),
    minCostForTwo: z.number().positive().optional(),
  }).optional(),
  minRating: z.number().min(0).max(5),
  optionalConstraints: z.array(z.string()).optional(),
});
📱 Page Specifications
Home Page (/)
Hero section with animated background
Quick search bar
Featured restaurants carousel
Popular cuisines grid with hover effects
How it works section
User testimonials carousel
Call-to-action to get started
Recommendations Page (/recommendations)
Multi-step form wizard
Progress indicator
Real-time validation
Loading states during API calls
Results display with filtering
Save/share functionality
Restaurant Details (/restaurants/[id])
Restaurant header with image
Detailed information sections
Reviews and ratings
Similar recommendations
Contact and directions
Dashboard (/dashboard)
User statistics
Recommendation history
Saved favorites
Preference management
Settings panel
Admin Panel (if applicable)
System health monitoring
Performance metrics dashboard
User management
Content management
🎯 User Experience
Loading States
Skeleton screens for all major components
Progress indicators for async operations
Optimistic UI updates where appropriate
Error boundaries for graceful error handling
Performance
Image optimization with next/image
Code splitting by route
Lazy loading for heavy components
Service worker for offline support
Caching strategies for API responses
Micro-interactions
Hover states on all interactive elements
Smooth transitions between pages
Loading animations
Success/error notifications
Form validation feedback
🔐 Authentication (Optional)
Features
Email/password authentication
Social login options (Google, Facebook)
JWT token management
Protected routes
User profile management
Implementation
NextAuth.js for authentication
Middleware for route protection
Session management
Token refresh logic
📊 Analytics & Monitoring
User Analytics
Recommendation tracking
User behavior analysis
Conversion funnels
Performance metrics
Error Tracking
Sentry integration
Error boundaries
Performance monitoring
User feedback collection
🚀 Deployment
Build Configuration
Environment variables setup
Build optimization
Asset optimization
Bundle analysis
Hosting Options
Vercel (recommended for Next.js)
Netlify
AWS Amplify
Self-hosted with Docker
📋 Acceptance Criteria
Functional Requirements
[ ] All API endpoints properly integrated
[ ] Responsive design works on all devices
[ ] Form validation prevents invalid submissions
[ ] Loading states provide good UX
[ ] Error handling is user-friendly
[ ] Accessibility standards are met
Performance Requirements
[ ] Page load time < 3 seconds
[ ] First Contentful Paint < 1.5 seconds
[ ] Largest Contentful Paint < 2.5 seconds
[ ] Cumulative Layout Shift < 0.1
[ ] First Input Delay < 100ms
Code Quality
[ ] TypeScript for type safety
[ ] ESLint and Prettier configured
[ ] Unit tests for critical components
[ ] Integration tests for API calls
[ ] E2E tests for user flows
🎨 Design References
Visual Style
Modern, clean interface
Food-related color palette
High-quality food photography
Consistent spacing and typography
Subtle animations and transitions
Inspiration
Food delivery apps (Uber Eats, DoorDash)
Restaurant discovery platforms (Yelp, Zomato)
Modern SaaS applications
Material Design principles
🔄 Integration with Backend
API Response Types
// types/api.ts
export interface RecommendationRequest {
  preferences: {
    location: string;
    budget?: {
      kind: 'range' | 'exact';
      max_cost_for_two?: number;
      min_cost_for_two?: number;
    };
    cuisine?: string;
    min_rating: number;
    optional_constraints: string[];
  };
  top_n: number;
  include_explanations: boolean;
  use_cache: boolean;
}

export interface RecommendationResponse {
  recommendations: Array<{
    restaurant: {
      restaurant_id: string;
      name: string;
      location: string;
      cuisines: string[];
      cost_for_two?: number;
      rating?: number;
      votes?: number;
    };
    rank: number;
    explanation?: string;
  }>;
  user_preferences: RecommendationRequest['preferences'];
  summary: string;
  total_candidates: number;
  processing_time_ms: number;
  cache_hit: boolean;
  timestamp: string;
}
Error Handling
// lib/errorHandling.ts
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export const handleApiError = (error: any) => {
  if (error.response) {
    throw new ApiError(
      error.response.data.message || 'An error occurred',
      error.response.status,
      error.response.data.error
    );
  } else if (error.request) {
    throw new ApiError('Network error. Please check your connection.', 0);
  } else {
    throw new ApiError('An unexpected error occurred.', 0);
  }
};
🛠️ Development Workflow
Setup Commands
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Run tests
npm test

# Lint code
npm run lint

# Type check
npm run type-check
Environment Variables
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=Zomoto AI Recommendations
NEXT_PUBLIC_GOOGLE_ANALYTICS_ID=your_ga_id
This frontend architecture provides a comprehensive foundation for building a modern, scalable, and user-friendly restaurant recommendation application that seamlessly integrates with the existing backend system.s        - Cache statistics             │
│  • POST /cache/clear        - Clear cache                  │
│  • GET  /jobs/{id}          - Async job status            │
└─────────────────────────────────────────────────────────────┘
```

#### **Service Layer**
```
┌─────────────────────────────────────────────────────────────┐
│                    Service Components                      │
├─────────────────────────────────────────────────────────────┤
│  • RecommendationService - Orchestrates full pipeline       │
│  • RetrievalService       - Phase 3 filtering logic       │
│  • RankingService        - Phase 4 LLM integration        │
│  • CacheService          - Redis-based caching           │
│  • JobQueueService       - Async LLM processing          │
│  • MonitoringService     - Health checks & metrics        │
└─────────────────────────────────────────────────────────────┘
```

#### **Data Layer**
```
┌─────────────────────────────────────────────────────────────┐
│                      Data Storage                          │
├─────────────────────────────────────────────────────────────┤
│  • PostgreSQL (Production)                                  │
│    - Restaurants table with indexes                        │
│    - Connection pooling (20 connections)                   │
│    - Full-text search capabilities                         │
│                                                             │
│  • SQLite (Development)                                     │
│    - Single file database                                 │
│    - Same interface as PostgreSQL                          │
│                                                             │
│  • Redis (Cache & Job Queue)                               │
│    - LLM result caching (TTL: 1 hour)                     │
│    - Session management                                   │
│    - Async job queue with priorities                       │
└─────────────────────────────────────────────────────────────┘
```

#### **Reliability Layer**
```
┌─────────────────────────────────────────────────────────────┐
│                 Reliability Components                      │
├─────────────────────────────────────────────────────────────┤
│  • Circuit Breaker        - Prevents cascade failures      │
│  • Rate Limiter           - Token bucket algorithm         │
│  • Retry Handler          - Exponential backoff           │
│  • Timeout Manager        - Configurable timeouts        │
│  • Fallback Handler       - Simplified ranking algorithms │
│  • Health Checker         - Component health monitoring   │
└─────────────────────────────────────────────────────────────┘
```

### Frontend Architecture

#### **Web Application (React + TailwindCSS)**
```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Components                     │
├─────────────────────────────────────────────────────────────┤
│  • PreferenceForm          - User input collection         │
│  • RecommendationCards    - Results display               │
│  • LoadingSpinner         - Async operation feedback      │
│  • ErrorBoundary          - Error handling UI             │
│  • HealthStatus           - System status indicator       │
└─────────────────────────────────────────────────────────────┘
```

#### **State Management**
```
┌─────────────────────────────────────────────────────────────┐
│                    State Management                         │
├─────────────────────────────────────────────────────────────┤
│  • useState (React Hooks) - Local component state          │
│  • useEffect                - API calls and side effects  │
│  • Context API             - Global application state     │
│  • Local Storage           - User preference persistence │
└─────────────────────────────────────────────────────────────┘
```

#### **API Integration**
```
┌─────────────────────────────────────────────────────────────┐
│                    API Client Layer                         │
├─────────────────────────────────────────────────────────────┤
│  • Axios/Fetch             - HTTP requests                 │
│  • Request Interceptors    - Error handling & logging     │
│  • Response Transformers  - Data normalization           │
│  • Retry Logic            - Automatic retry on failures    │
│  • Loading States         - UI feedback during requests   │
└─────────────────────────────────────────────────────────────┘
```

### Deployment Architecture

#### **Container-based Deployment**
```
┌─────────────────────────────────────────────────────────────┐
│                 Docker Compose Stack                        │
├─────────────────────────────────────────────────────────────┤
│  • API Service (4 workers)                                 │
│  • PostgreSQL Database                                      │
│  • Redis Cache & Job Queue                                 │
│  • Prometheus Monitoring                                    │
│  • Nginx Reverse Proxy (optional)                          │
└─────────────────────────────────────────────────────────────┘
```

#### **Kubernetes Deployment**
```
┌─────────────────────────────────────────────────────────────┐
│                Kubernetes Resources                          │
├─────────────────────────────────────────────────────────────┤
│  • Deployment (4 replicas)                                 │
│  • Service (LoadBalancer)                                 │
│  • ConfigMap (Environment variables)                       │
│  • PersistentVolume (PostgreSQL)                           │
│  • HorizontalPodAutoscaler                                 │
│  • NetworkPolicy (Security)                                │
└─────────────────────────────────────────────────────────────┘
```

### Monitoring & Observability Stack

#### **Logging & Metrics**
```
┌─────────────────────────────────────────────────────────────┐
│                Observability Components                     │
├─────────────────────────────────────────────────────────────┤
│  • Structured JSON Logs      - Request tracing             │
│  • Prometheus Metrics       - Performance monitoring      │
│  • Health Check Endpoints   - Component health            │
│  • AlertManager             - Threshold-based alerts      │
│  • Grafana Dashboard        - Visualization              │
└─────────────────────────────────────────────────────────────┘
```

#### **Key Metrics Tracked**
- **API Performance**: Response times, error rates, throughput
- **LLM Performance**: API calls, latency, costs, success rates
- **Database Performance**: Query times, connection pool usage
- **Cache Performance**: Hit rates, eviction rates, memory usage
- **System Resources**: CPU, memory, disk usage

### Security Architecture

#### **API Security**
```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                          │
├─────────────────────────────────────────────────────────────┤
│  • Rate Limiting           - Prevent abuse/DoS            │
│  • Input Validation       - Sanitize all user input       │
│  • CORS Configuration    - Cross-origin request security │
│  • Environment Variables  - Secure secret management      │
│  • API Keys (Optional)    - Authentication for premium   │
└─────────────────────────────────────────────────────────────┘
```

#### **Data Protection**
- **Encryption**: Database connections (SSL/TLS)
- **Access Control**: Least privilege principle
- **Audit Logging**: All sensitive operations logged
- **Data Sanitization**: PII protection in logs

---

## End-to-end data flow (conceptual)

1. **Offline**: Hugging Face dataset → clean/normalize → processed index (parquet).
2. **User Input**: Web UI form → validation → UserPreference object.
3. **API Request**: POST /recommendations with UserPreference → RecommendationService.
4. **Retrieval**: UserPreference → database query → CandidateSet (Phase 3).
5. **LLM Ranking**: CandidateSet → async job queue → LLM API → ranked results (Phase 4).
6. **Caching**: Results cached by preference hash → faster subsequent requests.
7. **Response**: RecommendationResult → JSON response → frontend rendering.
8. **Monitoring**: All steps logged, metrics collected, health checks performed.

---

## 🎨 Frontend Development Prompt for Google Stitch

### **Complete Next.js Frontend Generation Prompt**

Copy and paste the following prompt into Google Stitch to generate a complete Next.js frontend for the Zomoto AI Recommendation System:

---

```
Create a complete Next.js frontend for a restaurant recommendation system with the following specifications:

## 🎯 Project Overview
Build a modern, responsive web application that integrates with a FastAPI backend for restaurant recommendations. The app should provide an intuitive user experience for discovering restaurants based on user preferences.

## 🏗️ Technical Requirements

### Framework & Stack
- **Framework**: Next.js 14+ with App Router
- **Styling**: Tailwind CSS with modern design system
- **State Management**: Zustand or React Context API
- **HTTP Client**: Axios with interceptors for error handling
- **UI Components**: Headless UI or shadcn/ui components
- **Icons**: Lucide React or Heroicons
- **Form Handling**: React Hook Form with Zod validation
- **Animations**: Framer Motion for smooth transitions
- **Charts**: Recharts for analytics dashboard

### API Integration
The frontend must integrate with these backend endpoints:
- `POST /api/v1/recommendations` - Generate recommendations
- `POST /api/v1/recommendations/async` - Async recommendations
- `GET /api/v1/jobs/{job_id}` - Job status
- `GET /api/v1/health` - System health
- `GET /api/v1/metrics` - Performance metrics
- `GET /api/v1/cache/stats` - Cache statistics

### Core Features

#### 1. Home Page
- Hero section with app introduction
- Quick preference form (location, cuisine, budget, rating)
- Featured restaurants carousel
- Popular cuisines grid
- User testimonials

#### 2. Recommendation Form
- Multi-step preference collection wizard
- Location input with autocomplete
- Budget slider with visual indicators
- Cuisine multi-select with search
- Rating preference toggle
- Optional constraints (restaurant names, dietary restrictions)
- Form validation with real-time feedback

#### 3. Results Page
- Restaurant cards with rich information
- Filtering and sorting options
- Map view integration (optional)
- Save to favorites functionality
- Share recommendations
- Load more pagination

#### 4. Restaurant Details
- Full restaurant information
- Photo gallery
- Menu preview
- Reviews section
- Similar recommendations
- Directions integration

#### 5. User Dashboard
- Recommendation history
- Saved favorites
- Preference management
- Analytics and insights
- Settings and profile

#### 6. Admin Panel (if applicable)
- System health monitoring
- Performance metrics dashboard
- User management
- Content management

## 🎨 Design Requirements

### Design System
- **Primary Colors**: Orange/Red theme (food-related)
- **Secondary Colors**: Neutral grays and whites
- **Typography**: Inter or Poppins font family
- **Spacing**: Consistent 8px grid system
- **Border Radius**: 8px for cards, 4px for buttons
- **Shadows**: Subtle elevation with consistent blur

### Component Library
Create reusable components:
- Button (primary, secondary, outline, ghost)
- Input (text, email, number, search)
- Select (single, multi-select)
- Card (restaurant, recommendation, stats)
- Modal (confirmation, details, forms)
- Badge (cuisine tags, ratings, status)
- Skeleton (loading states)
- Toast (notifications, errors)

### Responsive Design
- **Mobile**: 320px - 768px
- **Tablet**: 768px - 1024px
- **Desktop**: 1024px+
- **Large Desktop**: 1440px+

### Accessibility
- WCAG 2.1 AA compliance
- Semantic HTML5 elements
- ARIA labels and roles
- Keyboard navigation support
- Screen reader compatibility
- Focus management
- Color contrast ratios

## 🔧 Technical Implementation

### Project Structure
```
src/
├── app/                    # App Router
│   ├── (auth)/            # Auth routes
│   ├── dashboard/         # Dashboard
│   ├── recommendations/   # Recommendation pages
│   ├── restaurants/       # Restaurant pages
│   ├── globals.css        # Global styles
│   ├── layout.tsx         # Root layout
│   └── page.tsx           # Home page
├── components/             # Reusable components
│   ├── ui/               # Base UI components
│   ├── forms/            # Form components
│   ├── cards/            # Card components
│   └── layout/           # Layout components
├── lib/                   # Utilities
│   ├── api.ts            # API client
│   ├── utils.ts          # Helper functions
│   └── validations.ts    # Zod schemas
├── hooks/                 # Custom hooks
├── store/                 # State management
├── types/                 # TypeScript types
└── styles/                # CSS modules
```

### API Client Setup
```typescript
// lib/api.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 30000,
});

// Request interceptor for auth
apiClient.interceptors.request.use((config) => {
  // Add auth headers if needed
  return config;
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle common errors
    return Promise.reject(error);
  }
);
```

### State Management
```typescript
// store/useRecommendations.ts
import { create } from 'zustand';

interface RecommendationState {
  recommendations: Recommendation[];
  loading: boolean;
  error: string | null;
  setRecommendations: (recs: Recommendation[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useRecommendationStore = create<RecommendationState>((set) => ({
  recommendations: [],
  loading: false,
  error: null,
  setRecommendations: (recs) => set({ recommendations: recs }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}));
```

### Form Validation
```typescript
// lib/validations.ts
import { z } from 'zod';

export const preferenceSchema = z.object({
  location: z.string().min(2, 'Location must be at least 2 characters'),
  cuisine: z.string().optional(),
  budget: z.object({
    kind: z.enum(['range', 'exact']),
    maxCostForTwo: z.number().positive().optional(),
    minCostForTwo: z.number().positive().optional(),
  }).optional(),
  minRating: z.number().min(0).max(5),
  optionalConstraints: z.array(z.string()).optional(),
});
```

## 📱 Page Specifications

### Home Page (`/`)
- Hero section with animated background
- Quick search bar
- Featured restaurants carousel
- Popular cuisines grid with hover effects
- How it works section
- User testimonials carousel
- Call-to-action to get started

### Recommendations Page (`/recommendations`)
- Multi-step form wizard
- Progress indicator
- Real-time validation
- Loading states during API calls
- Results display with filtering
- Save/share functionality

### Restaurant Details (`/restaurants/[id]`)
- Restaurant header with image
- Detailed information sections
- Reviews and ratings
- Similar recommendations
- Contact and directions

### Dashboard (`/dashboard`)
- User statistics
- Recommendation history
- Saved favorites
- Preference management
- Settings panel

## 🎯 User Experience

### Loading States
- Skeleton screens for all major components
- Progress indicators for async operations
- Optimistic UI updates where appropriate
- Error boundaries for graceful error handling

### Performance
- Image optimization with next/image
- Code splitting by route
- Lazy loading for heavy components
- Service worker for offline support
- Caching strategies for API responses

### Micro-interactions
- Hover states on all interactive elements
- Smooth transitions between pages
- Loading animations
- Success/error notifications
- Form validation feedback

## 🔐 Authentication (Optional)

### Features
- Email/password authentication
- Social login options (Google, Facebook)
- JWT token management
- Protected routes
- User profile management

### Implementation
- NextAuth.js for authentication
- Middleware for route protection
- Session management
- Token refresh logic

## 📊 Analytics & Monitoring

### User Analytics
- Recommendation tracking
- User behavior analysis
- Conversion funnels
- Performance metrics

### Error Tracking
- Sentry integration
- Error boundaries
- Performance monitoring
- User feedback collection

## 🚀 Deployment

### Build Configuration
- Environment variables setup
- Build optimization
- Asset optimization
- Bundle analysis

### Hosting Options
- Vercel (recommended for Next.js)
- Netlify
- AWS Amplify
- Self-hosted with Docker

## 📋 Acceptance Criteria

### Functional Requirements
- [ ] All API endpoints properly integrated
- [ ] Responsive design works on all devices
- [ ] Form validation prevents invalid submissions
- [ ] Loading states provide good UX
- [ ] Error handling is user-friendly
- [ ] Accessibility standards are met

### Performance Requirements
- [ ] Page load time < 3 seconds
- [ ] First Contentful Paint < 1.5 seconds
- [ ] Largest Contentful Paint < 2.5 seconds
- [ ] Cumulative Layout Shift < 0.1
- [ ] First Input Delay < 100ms

### Code Quality
- [ ] TypeScript for type safety
- [ ] ESLint and Prettier configured
- [ ] Unit tests for critical components
- [ ] Integration tests for API calls
- [ ] E2E tests for user flows

## 🎨 Design References

### Visual Style
- Modern, clean interface
- Food-related color palette
- High-quality food photography
- Consistent spacing and typography
- Subtle animations and transitions

### Inspiration
- Food delivery apps (Uber Eats, DoorDash)
- Restaurant discovery platforms (Yelp, Zomato)
- Modern SaaS applications
- Material Design principles

Generate the complete Next.js application with all the specified features, components, and functionality. Ensure the code is production-ready, well-documented, and follows modern React/Next.js best practices.
```

---

**How to Use:**
1. Copy the entire prompt above
2. Paste it into Google Stitch
3. Generate the complete Next.js frontend
4. The generated frontend will integrate seamlessly with our backend API

The prompt includes comprehensive specifications for a production-ready frontend with modern UI/UX, proper error handling, accessibility, and performance optimization. 🚀

