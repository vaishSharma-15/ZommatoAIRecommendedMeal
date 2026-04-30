export interface Budget {
  kind: 'range' | 'exact';
  max_cost_for_two?: number;
  min_cost_for_two?: number;
}

export interface UserPreference {
  location: string;
  budget?: Budget;
  cuisine?: string;
  min_rating: number;
  optional_constraints: string[];
}

export interface RecommendationRequest {
  preferences: UserPreference;
  top_n: number;
  include_explanations: boolean;
  use_cache: boolean;
}

export interface Restaurant {
  restaurant_id: string;
  name: string;
  location: string;
  cuisines: string[];
  cost_for_two?: number;
  rating?: number;
  votes?: number;
}

export interface RecommendationItem {
  restaurant: Restaurant;
  rank: number;
  explanation?: string;
}

export interface RecommendationResponse {
  recommendations: RecommendationItem[];
  user_preferences: UserPreference;
  summary: string;
  total_candidates: number;
  processing_time_ms: number;
  cache_hit: boolean;
  timestamp: string;
}

export interface HealthStatus {
  status: string;
  last_check: string;
  response_time_ms?: number;
  error?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  uptime_seconds: number;
  components: Record<string, HealthStatus>;
  timestamp: string;
}

export interface MetricValue {
  name: string;
  value: number;
  unit?: string;
  timestamp: string;
}

export interface MetricsResponse {
  metrics: MetricValue[];
  summary: Record<string, any>;
  timestamp: string;
}

export interface CacheStatsResponse {
  hit_rate: number;
  total_requests: number;
  hits: number;
  misses: number;
  size: number;
  timestamp: string;
}

export interface JobStatus {
  job_id: string;
  status: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  result?: any;
  error?: string;
  progress?: number;
}

export interface JobResponse {
  job: JobStatus;
  timestamp: string;
}

export interface ErrorResponse {
  error: string;
  message: string;
  details?: Record<string, any>;
  timestamp: string;
  request_id?: string;
}

export interface ValidationErrorResponse extends ErrorResponse {
  validation_errors: Array<{
    field: string;
    message: string;
  }>;
}
