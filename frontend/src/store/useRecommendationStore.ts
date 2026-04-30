import { create } from 'zustand';
import { RecommendationItem, RecommendationResponse } from '@/types/api';

interface RecommendationState {
  recommendations: RecommendationItem[];
  loading: boolean;
  error: string | null;
  currentRecommendations: RecommendationResponse | null;
  setRecommendations: (recs: RecommendationItem[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setCurrentRecommendations: (response: RecommendationResponse) => void;
  clearRecommendations: () => void;
}

export const useRecommendationStore = create<RecommendationState>((set, get) => ({
  recommendations: [],
  loading: false,
  error: null,
  currentRecommendations: null,
  
  setRecommendations: (recs) => set({ recommendations: recs }),
  
  setLoading: (loading) => set({ loading }),
  
  setError: (error) => set({ error }),
  
  setCurrentRecommendations: (response) => set({ 
    currentRecommendations: response,
    recommendations: response.recommendations,
    loading: false,
    error: null 
  }),
  
  clearRecommendations: () => set({ 
    recommendations: [],
    currentRecommendations: null,
    loading: false,
    error: null 
  }),
}));
