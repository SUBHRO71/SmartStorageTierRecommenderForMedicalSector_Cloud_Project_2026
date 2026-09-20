import axios from 'axios';
import { Auth } from '@aws-amplify/auth';
import mockData from './mockData';

// If explicitly true, force mock data; otherwise try real API first with mock fallback
const FORCE_MOCK = process.env.REACT_APP_USE_MOCK_API === 'true';

const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:5000/api',
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

    try {
      return await apiClient.get(url, config);
    } catch (err) {
      console.warn(`[API Client] Request to ${url} failed (${err.message}). Falling back to local mock data.`);
      return getMockResponse(url);
    }
  },

  post: async (url, data, config) => {
    if (FORCE_MOCK) {
      return new Promise((resolve) => {
        setTimeout(() => {
          if (url.includes('/predict')) resolve({ data: mockData.predictionResult });
          else if (url.includes('/tier')) resolve({ data: { success: true, new_tier: data?.tier } });
          else resolve({ data: {} });
        }, 400);
      });
    }

    try {
      return await apiClient.post(url, data, config);
    } catch (err) {
      console.warn(`[API Client] POST to ${url} failed (${err.message}). Falling back to mock response.`);
      if (url.includes('/predict')) return { data: mockData.predictionResult };
      if (url.includes('/tier')) return { data: { success: true, new_tier: data?.tier } };
      return { data: {} };
    }
  }
};

export default client;
