# Zomoto AI Frontend - Next.js Application

## 🎯 Project Overview

Complete Next.js frontend for the Zomoto AI Recommendation System with modern UI/UX, TypeScript, and production-ready features.

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

## 📁 Project Structure

```
src/
├── app/                    # App Router
│   ├── globals.css        # Global styles
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Home page
│   └── recommendations/   # Recommendation pages
├── components/             # Reusable components
│   └── ui/               # Base UI components
├── lib/                   # Utilities
│   ├── api.ts            # API client
│   ├── apiService.ts     # API service functions
│   ├── utils.ts          # Helper functions
│   └── validations.ts    # Zod schemas
├── store/                 # State management
└── types/                 # TypeScript types
```

## 🎨 Features Implemented

### ✅ Core Features
- **Home Page**: Hero section, featured restaurants, popular cuisines
- **Recommendations**: Multi-step form wizard with real-time validation
- **Dashboard**: User statistics and recommendation history
- **Responsive Design**: Mobile-first with Tailwind CSS

### ✅ Technical Features
- **TypeScript**: Full type safety throughout
- **API Integration**: Axios with error handling and interceptors
- **State Management**: Zustand for global state
- **Form Validation**: React Hook Form with Zod schemas
- **UI Components**: Reusable component library with shadcn/ui

### ✅ Production Features
- **SEO Optimized**: Next.js metadata and OpenGraph tags
- **Performance**: Code splitting, image optimization, caching
- **Accessibility**: WCAG 2.1 AA compliance
- **Error Handling**: Comprehensive error boundaries and user feedback

## 🔧 Configuration

### Environment Variables
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=Zomoto AI Recommendations
```

### API Integration
The frontend integrates with these backend endpoints:
- `POST /api/v1/recommendations` - Generate recommendations
- `POST /api/v1/recommendations/async` - Async recommendations
- `GET /api/v1/jobs/{job_id}` - Job status
- `GET /api/v1/health` - System health

## 🎨 Design System

### Colors
- **Primary**: Orange theme (food-related)
- **Secondary**: Neutral grays and whites
- **Typography**: Inter font family
- **Spacing**: 8px grid system

### Components
- Button (primary, secondary, outline, ghost)
- Input, Card, Badge, Skeleton
- Loading states and animations
- Responsive grid layouts

## 📱 Pages

### Home Page (`/`)
- Hero section with call-to-action
- Featured restaurants carousel
- Popular cuisines grid
- How it works section

### Recommendations (`/recommendations`)
- Multi-step preference form
- Real-time validation
- Loading states during API calls
- Results display with explanations

### Dashboard (`/dashboard`)
- User statistics
- Recommendation history
- Saved favorites
- Settings panel

## 🚀 Deployment

### Build Configuration
```bash
npm run build
npm start
```

### Environment Setup
1. Install dependencies: `npm install`
2. Set environment variables
3. Start backend server
4. Run frontend: `npm run dev`

## 📋 Development Commands

```bash
# Development
npm run dev          # Start dev server
npm run build        # Build for production
npm run start        # Start production server

# Code Quality
npm run lint         # Run ESLint
npm run type-check   # TypeScript check
npm test             # Run tests
```

## 🔗 Integration

The frontend seamlessly integrates with the backend API:
- Automatic correlation ID tracking
- Error handling with user-friendly messages
- Loading states and progress indicators
- Caching and performance optimization

## 🎯 Next Steps

1. Install dependencies: `npm install`
2. Configure environment variables
3. Start backend server
4. Run `npm run dev` to start frontend
5. Visit `http://localhost:3000`

The frontend is production-ready with modern React patterns, TypeScript safety, and comprehensive error handling. 🚀
