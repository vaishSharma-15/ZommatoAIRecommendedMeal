'use client';

import { useState } from 'react';
import { Search, MapPin, Star, DollarSign, Filter, X, ChevronDown, Bookmark, Cpu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export default function HomePage() {
  const [filters, setFilters] = useState({
    location: 'Bangalore, India',
    cuisine: '',
    minRating: 4.0,
    maxCostForTwo: null as number | null,
  });
  const [loading, setLoading] = useState(false);
  const [recommendations, setRecommendations] = useState<any>(null);

  const preferencesList = ['Family-friendly', 'Quick service', 'Outdoor Seating', 'Pet-friendly', 'Live Music'];
  const [activePreferences, setActivePreferences] = useState<string[]>([]);

  const locations = [
    'Bangalore, India',
    'Indiranagar, Bangalore',
    'Koramangala, Bangalore',
    'Jayanagar, Bangalore',
    'Whitefield, Bangalore',
    'HSR Layout, Bangalore',
    'MG Road, Bangalore',
    'JP Nagar, Bangalore',
    'Marathahalli, Bangalore',
    'Malleshwaram, Bangalore',
    'Bellandur, Bangalore'
  ];

  const cuisines = [
    'Any Cuisine',
    'Italian',
    'Chinese',
    'North Indian',
    'South Indian',
    'Continental',
    'Japanese',
    'Thai',
    'Mexican',
    'Mediterranean'
  ];

  const togglePreference = (pref: string) => {
    if (activePreferences.includes(pref)) {
      setActivePreferences(activePreferences.filter(p => p !== pref));
    } else {
      setActivePreferences([...activePreferences, pref]);
    }
  };

  const handleGenerateRecommendations = async () => {
    setLoading(true);
    setRecommendations(null);
    try {
      const requestBody = {
        preferences: { 
          location: filters.location.includes(',') ? filters.location.split(',')[0].trim() : filters.location, // Extract area if comma-separated
          cuisine: filters.cuisine === 'Any Cuisine' ? '' : filters.cuisine,
          min_rating: filters.minRating,
          budget: filters.maxCostForTwo ? { kind: 'range', max_cost_for_two: filters.maxCostForTwo } : undefined,
          optional_constraints: activePreferences // Send selected preferences
        },
        top_n: 5, 
        include_explanations: true, 
        use_cache: false,
      };
      console.log('Sending request with body:', JSON.stringify(requestBody, null, 2));
      
      const response = await fetch('http://localhost:8000/api/v1/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });
      console.log('Response status:', response.status);
      if (response.ok) {
        const data = await response.json();
        console.log('API response data:', data);
        
        // Remove duplicate restaurants based on restaurant_id
        const uniqueRecommendations = data.recommendations.filter((item: any, index: number, self: any[]) => 
          index === self.findIndex((t: any) => t.restaurant.restaurant_id === item.restaurant.restaurant_id)
        );
        
        setRecommendations({
          ...data,
          recommendations: uniqueRecommendations
        });
      } else {
        const errorData = await response.json();
        console.error("API returned error:", response.status, errorData);
        alert(`Error: ${errorData.detail || 'Failed to generate recommendations'}`);
      }
    } catch (err) {
      console.error("Fetch error:", err);
      alert(`Network error: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white font-sans text-gray-900">
      {/* Header */}
      <header className="absolute top-0 w-full z-50 bg-white/95 backdrop-blur-sm border-b border-gray-100 py-4">
        <div className="max-w-7xl mx-auto px-6 flex justify-between items-center">
          <div className="text-2xl font-black text-red-600 tracking-tight">Zomato AI</div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative pt-24 pb-32 flex items-center min-h-[600px] overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src="/images/hero_bg.png" alt="Dining Background" className="w-full h-full object-cover filter brightness-[0.4]" />
        </div>
        <div className="max-w-7xl mx-auto px-6 relative z-10 w-full pt-16">
          <div className="max-w-4xl mx-auto bg-white/10 backdrop-blur-md border border-white/20 p-12 rounded-2xl shadow-2xl flex items-center justify-center min-h-[160px]">
            <h1 className="text-2xl md:text-3xl lg:text-4xl font-semibold text-white leading-tight text-center">Find AI Recommended meal on zomato</h1>
          </div>
        </div>
      </section>

      {/* Floating Filter Bar */}
      <section className="max-w-7xl mx-auto px-6 relative z-20 -mt-16">
        <div className="bg-white rounded-xl shadow-[0_8px_30px_rgb(0,0,0,0.12)] p-6 border border-gray-100">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
            <div className="col-span-1 border-b border-gray-200 pb-2 relative">
              <label className="flex items-center gap-2 text-xs font-bold text-gray-500 uppercase tracking-wider mb-2"><MapPin size={14}/> Location</label>
              <select 
                className="w-full text-sm font-medium focus:outline-none text-gray-900 bg-transparent appearance-none cursor-pointer"
                value={filters.location}
                onChange={(e) => setFilters({...filters, location: e.target.value})}
              >
                {locations.map(loc => <option key={loc} value={loc}>{loc}</option>)}
              </select>
              <ChevronDown size={16} className="text-gray-400 absolute right-0 bottom-2 pointer-events-none" />
            </div>
            
            <div className="col-span-1 border-b border-gray-200 pb-2 relative">
              <label className="flex items-center gap-2 text-xs font-bold text-gray-500 uppercase tracking-wider mb-2"><Star size={14}/> Min Rating</label>
              <select 
                className="w-full text-sm font-medium focus:outline-none text-gray-900 bg-transparent appearance-none cursor-pointer"
                value={filters.minRating}
                onChange={(e) => setFilters({...filters, minRating: parseFloat(e.target.value)})}
              >
                <option value={0}>Any Rating</option>
                <option value={3.0}>3.0+ Stars</option>
                <option value={4.0}>4.0+ Stars</option>
                <option value={4.5}>4.5+ Stars</option>
              </select>
              <ChevronDown size={16} className="text-gray-400 absolute right-0 bottom-2 pointer-events-none" />
            </div>
            
            <div className="col-span-1 border-b border-gray-200 pb-2 relative">
              <label className="flex items-center gap-2 text-xs font-bold text-gray-500 uppercase tracking-wider mb-2"><Filter size={14}/> Cuisine</label>
              <select 
                className="w-full text-sm font-medium focus:outline-none text-gray-900 bg-transparent appearance-none cursor-pointer"
                value={filters.cuisine}
                onChange={(e) => setFilters({...filters, cuisine: e.target.value})}
              >
                {cuisines.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              <ChevronDown size={16} className="text-gray-400 absolute right-0 bottom-2 pointer-events-none" />
            </div>

            <div className="col-span-1 border-b border-gray-200 pb-2">
              <label className="flex items-center gap-2 text-xs font-bold text-gray-500 uppercase tracking-wider mb-2"><DollarSign size={14}/> Budget (Max)</label>
              <input 
                type="number" 
                placeholder="e.g. 1000" 
                className="w-full text-sm font-medium focus:outline-none text-gray-900 placeholder-gray-400 bg-transparent" 
                value={filters.maxCostForTwo || ''}
                onChange={(e) => setFilters({...filters, maxCostForTwo: e.target.value ? parseInt(e.target.value) : null})}
              />
            </div>

            <div className="col-span-1 h-full">
              <Button 
                onClick={handleGenerateRecommendations} 
                disabled={loading}
                className="w-full h-full min-h-[50px] bg-red-700 hover:bg-red-800 text-white font-bold tracking-wide rounded-md shadow-md flex items-center justify-center gap-2"
              >
                {loading ? (
                  <span className="flex items-center gap-2"><div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div> Loading...</span>
                ) : (
                  <span>FIND MEALS</span>
                )}
              </Button>
            </div>
          </div>
          <div className="mt-6 flex items-center gap-4 flex-wrap">
            <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">Preferences:</span>
            {preferencesList.map(pref => (
              <Badge 
                key={pref} 
                variant="outline" 
                onClick={() => togglePreference(pref)}
                className={`px-4 py-1.5 rounded-full text-xs font-medium cursor-pointer transition-colors ${
                  activePreferences.includes(pref) 
                    ? 'bg-orange-50 text-orange-700 border-orange-200' 
                    : 'border-gray-200 hover:border-red-200 hover:bg-red-50 text-gray-600'
                }`}
              >
                {pref}
              </Badge>
            ))}
          </div>
        </div>
      </section>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-16">
        
        {/* Dynamic Recommendations */}
        {recommendations && (
          <div className="mb-16">
            <div className="flex justify-between items-end mb-6">
              <div>
                <h2 className="text-2xl font-bold mb-1">Your Recommendations</h2>
                <p className="text-gray-500 text-sm">{recommendations.summary}</p>
              </div>
              <Button variant="ghost" onClick={() => setRecommendations(null)} className="text-red-600 hover:text-red-700 hover:bg-red-50">Clear Results</Button>
            </div>

            <div className="grid grid-cols-1 gap-4">
              {recommendations.recommendations.map((item: any, idx: number) => (
                <div key={idx} className="bg-white rounded-xl shadow-sm hover:shadow-md border border-gray-100 p-6 transition-shadow">
                  <div className="flex justify-between items-start mb-3">
                    <h3 className="text-lg font-bold">{item.restaurant.name}</h3>
                    <span className="text-xs font-bold text-orange-600 bg-orange-50 px-2 py-1 rounded whitespace-nowrap">Rank #{item.rank}</span>
                  </div>
                  <div className="flex flex-wrap gap-3 text-sm text-gray-600 mb-3">
                    <span className="flex items-center gap-1">
                      <Star size={14} className="text-yellow-400" fill="currentColor"/> {item.restaurant.rating}
                    </span>
                    <span>•</span>
                    <span>₹{item.restaurant.cost_for_two} for two</span>
                    <span>•</span>
                    <span>{item.restaurant.location}</span>
                  </div>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {item.restaurant.cuisines?.map((cuisine: string, cIdx: number) => (
                      <span key={cIdx} className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">
                        {cuisine}
                      </span>
                    ))}
                  </div>
                  {item.explanation && (
                    <p className="text-sm text-gray-700 italic">"{item.explanation}"</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="bg-gray-50 border-t border-gray-200 pt-16 pb-8 mt-auto">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-12">
            <div className="col-span-1 md:col-span-2">
              <div className="text-2xl font-black text-gray-900 tracking-tight mb-4">Zomato AI</div>
              <p className="text-sm text-gray-500 max-w-xs mb-6">Revolutionizing the way you discover food through culinary intelligence and personalized machine learning.</p>
              <div className="flex gap-4 text-gray-400">
                <a href="#" className="hover:text-gray-900"><svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path fillRule="evenodd" d="M22 12c0-5.523-4.477-10-10-10S2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.878v-6.987h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.988C18.343 21.128 22 16.991 22 12z" clipRule="evenodd" /></svg></a>
                <a href="#" className="hover:text-gray-900"><svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M8.29 20.251c7.547 0 11.675-6.253 11.675-11.675 0-.178 0-.355-.012-.53A8.348 8.348 0 0022 5.92a8.19 8.19 0 01-2.357.646 4.118 4.118 0 001.804-2.27 8.224 8.224 0 01-2.605.996 4.107 4.107 0 00-6.993 3.743 11.65 11.65 0 01-8.457-4.287 4.106 4.106 0 001.27 5.477A4.072 4.072 0 012.8 9.713v.052a4.105 4.105 0 003.292 4.022 4.095 4.095 0 01-1.853.07 4.108 4.108 0 003.834 2.85A8.233 8.233 0 012 18.407a11.616 11.616 0 006.29 1.84" /></svg></a>
                <a href="#" className="hover:text-gray-900"><svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path fillRule="evenodd" d="M12.315 2c2.43 0 2.784.013 3.808.06 1.064.049 1.791.218 2.427.465a4.902 4.902 0 011.772 1.153 4.902 4.902 0 011.153 1.772c.247.636.416 1.363.465 2.427.048 1.067.06 1.407.06 4.123v.08c0 2.643-.012 2.987-.06 4.043-.049 1.064-.218 1.791-.465 2.427a4.902 4.902 0 01-1.153 1.772 4.902 4.902 0 01-1.772 1.153c-.636.247-1.363.416-2.427.465-1.067.048-1.407.06-4.123.06h-.08c-2.643 0-2.987-.012-4.043-.06-1.064-.049-1.791-.218-2.427-.465a4.902 4.902 0 01-1.772-1.153 4.902 4.902 0 01-1.153-1.772c-.247-.636-.416-1.363-.465-2.427-.047-1.024-.06-1.379-.06-3.808v-.63c0-2.43.013-2.784.06-3.808.049-1.064.218-1.791.465-2.427a4.902 4.902 0 011.153-1.772A4.902 4.902 0 015.45 2.525c.636-.247 1.363-.416 2.427-.465C8.901 2.013 9.256 2 11.685 2h.63zm-.081 1.802h-.468c-2.456 0-2.784.011-3.807.058-.975.045-1.504.207-1.857.344-.467.182-.8.398-1.15.748-.35.35-.566.683-.748 1.15-.137.353-.3.882-.344 1.857-.047 1.023-.058 1.351-.058 3.807v.468c0 2.456.011 2.784.058 3.807.045.975.207 1.504.344 1.857.182.466.399.8.748 1.15.35.35.683.566 1.15.748.353.137.882.3 1.857.344 1.054.048 1.37.058 4.041.058h.08c2.597 0 2.917-.01 3.96-.058.976-.045 1.505-.207 1.858-.344.466-.182.8-.398 1.15-.748.35-.35.566-.683.748-1.15.137-.353.3-.882.344-1.857.048-1.055.058-1.37.058-4.041v-.08c0-2.597-.01-2.917-.058-3.96-.045-.976-.207-1.505-.344-1.858a3.097 3.097 0 00-.748-1.15 3.098 3.098 0 00-1.15-.748c-.353-.137-.882-.3-1.857-.344-1.023-.047-1.351-.058-3.807-.058zM12 6.865a5.135 5.135 0 110 10.27 5.135 5.135 0 010-10.27zm0 1.802a3.333 3.333 0 100 6.666 3.333 3.333 0 000-6.666zm5.338-3.205a1.2 1.2 0 110 2.4 1.2 1.2 0 010-2.4z" clipRule="evenodd" /></svg></a>
              </div>
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-4 text-sm">Company</h4>
              <ul className="space-y-3 text-sm text-gray-500">
                <li><a href="#" className="hover:text-gray-900 transition-colors">Privacy Policy</a></li>
                <li><a href="#" className="hover:text-gray-900 transition-colors">Terms of Service</a></li>
                <li><a href="#" className="hover:text-gray-900 transition-colors">AI Ethics</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-4 text-sm">Support</h4>
              <ul className="space-y-3 text-sm text-gray-500">
                <li><a href="#" className="hover:text-gray-900 transition-colors">Contact Support</a></li>
                <li><a href="#" className="hover:text-gray-900 transition-colors">Cookie Policy</a></li>
                <li><a href="#" className="hover:text-gray-900 transition-colors">Dining Guide</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-200 pt-8 flex flex-col md:flex-row justify-between items-center gap-4 text-xs text-gray-500">
            <p>© 2024 Zomato AI. Powered by Culinary Intelligence.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
