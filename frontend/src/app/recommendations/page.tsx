'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { recommendationRequestSchema } from '@/lib/validations';
import { recommendationApi } from '@/lib/apiService';
import { useRecommendationStore } from '@/store/useRecommendationStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Star, Clock, TrendingUp } from 'lucide-react';

export default function RecommendationsPage() {
  const { setLoading, setError, setCurrentRecommendations } = useRecommendationStore();
  const [step, setStep] = useState(1);
  const [jobId, setJobId] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(recommendationRequestSchema),
    defaultValues: {
      preferences: {
        location: '',
        cuisine: '',
        min_rating: 0,
        optional_constraints: [],
        budget: {
          kind: 'range',
          max_cost_for_two: undefined,
          min_cost_for_two: undefined,
        },
      },
      top_n: 10,
      include_explanations: true,
      use_cache: true,
    },
  });

  const onSubmit = async (data: any) => {
    try {
      setLoading(true);
      setError(null);

      // Check if user wants async processing
      if (data.top_n > 20) {
        const jobResponse = await recommendationApi.generateRecommendationsAsync(data);
        setJobId(jobResponse.job.job_id);
        setStep(3); // Job submitted step
      } else {
        const response = await recommendationApi.generateRecommendations(data);
        setCurrentRecommendations(response);
        setStep(4); // Results step
      }
    } catch (error) {
      setError((error as Error).message || 'Failed to generate recommendations');
      setLoading(false);
    }
  };

  const checkJobStatus = async () => {
    if (!jobId) return;

    try {
      const jobResponse = await recommendationApi.getJobStatus(jobId);
      
      if (jobResponse.job.status === 'completed') {
        const result = jobResponse.job.result;
        setCurrentRecommendations(result);
        setStep(4);
      } else if (jobResponse.job.status === 'failed') {
          setError(jobResponse.job.error || 'Job failed');
          setStep(2);
        } else {
          // Still processing
          setTimeout(checkJobStatus, 2000);
        }
    } catch (error) {
      setError('Failed to check job status');
    }
  };

  // Auto-check job status if we have a job ID
  useState(() => {
    if (jobId && step === 3) {
      checkJobStatus();
    }
  });

  const renderStep1 = () => (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Tell Us Your Preferences</h2>
      <p className="text-gray-600">Help us find the perfect restaurants for you.</p>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Location *
          </label>
          <Input
            {...register('preferences.location')}
            placeholder="e.g., Bangalore, Mumbai, Delhi"
            className="w-full"
          />
          {errors.preferences?.location && (
            <p className="text-red-500 text-sm mt-1">{errors.preferences.location.message}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Cuisine (Optional)
          </label>
          <Input
            {...register('preferences.cuisine')}
            placeholder="e.g., Italian, Chinese, North Indian"
            className="w-full"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Minimum Rating
          </label>
          <Input
            {...register('preferences.min_rating', { valueAsNumber: true })}
            type="number"
            min="0"
            max="5"
            step="0.1"
            placeholder="e.g., 3.5"
            className="w-full"
          />
          {errors.preferences?.min_rating && (
            <p className="text-red-500 text-sm mt-1">{errors.preferences.min_rating.message}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Number of Recommendations
          </label>
          <Input
            {...register('top_n', { valueAsNumber: true })}
            type="number"
            min="1"
            max="50"
            className="w-full"
          />
          {errors.top_n && (
            <p className="text-red-500 text-sm mt-1">{errors.top_n.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            <input
              {...register('include_explanations')}
              type="checkbox"
              id="include_explanations"
              className="rounded border-gray-300 text-orange-600 focus:ring-orange-500"
            />
            <label htmlFor="include_explanations" className="text-sm text-gray-700">
              Include explanations
            </label>
          </div>
          
          <div className="flex items-center space-x-2">
            <input
              {...register('use_cache')}
              type="checkbox"
              id="use_cache"
              className="rounded border-gray-300 text-orange-600 focus:ring-orange-500"
              defaultChecked
            />
            <label htmlFor="use_cache" className="text-sm text-gray-700">
              Use cache for faster results
            </label>
          </div>
        </div>
      </div>

      <div className="flex justify-between pt-6">
        <Button
          type="button"
          onClick={() => setStep(2)}
          variant="outline"
          disabled={isSubmitting}
        >
          Back
        </Button>
        
        <Button
          type="submit"
          disabled={isSubmitting}
          className="btn-scale"
        >
          {isSubmitting ? 'Generating...' : 'Get Recommendations'}
        </Button>
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Budget Preferences</h2>
      <p className="text-gray-600">Set your budget range to filter restaurants.</p>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Budget Type
          </label>
          <select
            {...register('preferences.budget.kind')}
            className="w-full rounded-md border-gray-300 text-gray-900 focus:ring-orange-500"
          >
            <option value="range">Price Range</option>
            <option value="exact">Exact Price</option>
          </select>
          {errors.preferences?.budget?.kind && (
            <p className="text-red-500 text-sm mt-1">{errors.preferences.budget.kind.message}</p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Maximum Cost for Two
            </label>
            <Input
              {...register('preferences.budget.max_cost_for_two', { valueAsNumber: true })}
              type="number"
              min="0"
              placeholder="e.g., 1000"
              className="w-full"
            />
            {errors.preferences?.budget?.max_cost_for_two && (
              <p className="text-red-500 text-sm mt-1">{errors.preferences.budget.max_cost_for_two.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Minimum Cost for Two (Optional)
            </label>
            <Input
              {...register('preferences.budget.min_cost_for_two', { valueAsNumber: true })}
              type="number"
              min="0"
              placeholder="e.g., 500"
              className="w-full"
            />
            {errors.preferences?.budget?.min_cost_for_two && (
              <p className="text-red-500 text-sm mt-1">{errors.preferences.budget.min_cost_for_two.message}</p>
            )}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Optional Constraints
          </label>
          <Input
            {...register('preferences.optional_constraints')}
            placeholder="e.g., outdoor seating, valet parking"
            className="w-full"
          />
          {errors.preferences?.optional_constraints && (
            <p className="text-red-500 text-sm mt-1">{errors.preferences.optional_constraints.message}</p>
          )}
        </div>
      </div>

      <div className="flex justify-between pt-6">
        <Button
          type="button"
          onClick={() => setStep(1)}
          variant="outline"
        >
          Back
        </Button>
        
        <Button
          type="submit"
          disabled={isSubmitting}
          className="btn-scale"
        >
          {isSubmitting ? 'Generating...' : 'Get Recommendations'}
        </Button>
      </div>
    </div>
  );

  const renderStep3 = () => (
    <div className="space-y-6">
      <div className="text-center">
        <div className="inline-flex items-center px-4 py-6 border border-orange-200 rounded-lg">
          <Clock className="h-8 w-8 text-orange-600 animate-spin" />
        </div>
        <h2 className="mt-4 text-2xl font-bold text-gray-900">
          Processing Your Request
        </h2>
        <p className="mt-2 text-gray-600">
          {jobId ? 'We are generating personalized recommendations for you.' : 'Please wait...'}
        </p>
        {jobId && (
          <p className="mt-2 text-sm text-gray-500">
            Job ID: {jobId}
          </p>
        )}
      </div>
    </div>
  );

  const renderStep4 = (recommendations: any) => (
    <div className="space-y-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900">
          Your Personalized Recommendations
        </h2>
        <Button
          onClick={() => {
            setCurrentRecommendations(null as any);
            setStep(1);
          }}
          variant="outline"
        >
          Start Over
        </Button>
      </div>

      {recommendations ? (
        <>
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
            <h3 className="text-lg font-semibold text-green-800">
              {recommendations.summary}
            </h3>
            <div className="mt-2 text-sm text-green-600">
              Found {recommendations.recommendations.length} restaurants from {recommendations.total_candidates} candidates
              • Generated in {(recommendations.processing_time_ms / 1000).toFixed(1)}s
              • {recommendations.cache_hit ? 'Served from cache' : 'Fresh recommendations'}
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {recommendations.recommendations.map((item: any, index: number) => (
              <Card key={index} className="card-hover">
                <CardHeader>
                  <div className="flex justify-between items-start">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">
                        #{item.rank}
                      </Badge>
                      <div className="flex items-center gap-1">
                        <Star className="h-4 w-4 text-yellow-500 fill-current" />
                        <span className="text-sm font-medium">{item.restaurant.rating?.toFixed(1)}</span>
                      </div>
                    </div>
                    <div className="text-sm text-gray-500">
                      {item.restaurant.cost_for_two && `₹${item.restaurant.cost_for_two}`}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <CardTitle className="text-lg">{item.restaurant.name}</CardTitle>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant="outline">
                      {item.restaurant.cuisines.join(', ')}
                    </Badge>
                  </div>
                  <CardDescription className="mt-2">
                    📍 {item.restaurant.location}
                  </CardDescription>
                  {item.explanation && (
                    <div className="mt-3 p-3 bg-blue-50 rounded-lg">
                      <p className="text-sm text-blue-800">
                        <strong>Why we recommend this:</strong> {item.explanation}
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      ) : (
        <div className="grid gap-4">
          {[...Array(6)].map((_, index) => (
            <Card key={index}>
              <CardContent className="p-4">
                <Skeleton className="h-4 w-3/4 mb-2" />
                <Skeleton className="h-4 w-full mb-2" />
                <Skeleton className="h-4 w-2/3 mb-2" />
                <Skeleton className="h-4 w-1/2 mb-4" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-4xl px-4 py-8">
        {/* Progress Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              {[1, 2, 3, 4].map((stepNumber) => (
                <div
                  key={stepNumber}
                  className={`h-8 w-8 rounded-full flex items-center justify-center ${
                    step === stepNumber
                      ? 'bg-orange-600 text-white'
                      : 'bg-gray-200 text-gray-600'
                  }`}
                >
                  {stepNumber}
                </div>
              ))}
              <div className="h-1 flex-1 bg-gray-200 rounded" />
              <div className="h-8 w-8 rounded-full flex items-center justify-center bg-green-600 text-white">
                <TrendingUp className="h-4 w-4" />
              </div>
            </div>
            <div className="text-sm text-gray-600">
              {step === 1 && 'Tell us your preferences'}
              {step === 2 && 'Set your budget'}
              {step === 3 && 'Processing request'}
              {step === 4 && 'View recommendations'}
            </div>
          </div>
        </div>

        {/* Form Steps */}
        <form onSubmit={handleSubmit(onSubmit)}>
          {step === 1 && renderStep1()}
          {step === 2 && renderStep2()}
          {step === 3 && renderStep3()}
          {step === 4 && renderStep4(useRecommendationStore().currentRecommendations)}
        </form>
      </div>
    </div>
  );
}
