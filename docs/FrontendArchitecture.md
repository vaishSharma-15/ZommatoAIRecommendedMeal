# Frontend Architecture - Next.js Application

This document provides comprehensive specifications for the Next.js frontend that integrates with the Zomoto AI Recommendation System backend.

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

### Admin Panel (if applicable)
- System health monitoring
- Performance metrics dashboard
- User management
- Content management

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

## 🔄 Integration with Backend

### API Response Types
```typescript
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
```

### Error Handling
```typescript
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
```

## 🛠️ Development Workflow

### Setup Commands
```bash
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
```

### Environment Variables
```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=Zomoto AI Recommendations
NEXT_PUBLIC_GOOGLE_ANALYTICS_ID=your_ga_id
```

This frontend architecture provides a comprehensive foundation for building a modern, scalable, and user-friendly restaurant recommendation application that seamlessly integrates with the existing backend system.
