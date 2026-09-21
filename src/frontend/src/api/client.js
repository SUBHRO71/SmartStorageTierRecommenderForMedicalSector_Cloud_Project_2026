import axios from 'axios';
import { Auth } from '@aws-amplify/auth';
import mockData from './mockData';

// Mock responses are used only when explicitly requested. Live failures remain failures.
const FORCE_MOCK = import.meta.env.VITE_USE_MOCK_API === 'true';
export const isMockMode = FORCE_MOCK;

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',
  timeout: 4000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to inject JWT token if user logged in via Cognito
apiClient.interceptors.request.use(async (config) => {
  try {
    if (Auth && typeof Auth.currentSession === 'function') {
      const session = await Auth.currentSession();
      const token = session.getIdToken().getJwtToken();
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch (error) {
    // If no active Cognito session, continue (local dev or mock auth)
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

// Mock resolver helper
const getMockResponse = (url) => {
  if (url.includes('/dashboard/summary')) return { data: mockData.dashboardSummary };
  if (url.includes('/costs')) return { data: mockData.costComparison };
  if (url.match(/\/scans\/[^/?]+$/)) return { data: mockData.scanDetail };
  if (url.includes('/scans')) return { data: mockData.scansList };
  return { data: {} };
};

const client = {
  get: async (url, config) => {
    if (FORCE_MOCK) {
      return new Promise((resolve) => {
        setTimeout(() => resolve(getMockResponse(url)), 300);
      });
    }

    return apiClient.get(url, config);
  },

  post: async (url, data, config) => {
    if (FORCE_MOCK) {
      return new Promise((resolve) => {
        setTimeout(() => {
          if (url.includes('/predict')) resolve({ data: mockData.predictionResult });
          else if (url.includes('/tier')) resolve({ data: { success: true, requested_tier: data?.tier, current_tier: data?.tier, decision_status: 'APPLIED_MOCK' } });
          else if (url.includes('/restore')) resolve({ data: { restore_status: 'COMPLETE_MOCK' } });
          else resolve({ data: {} });
        }, 400);
      });
    }

    return apiClient.post(url, data, config);
  }
};

export default client;
