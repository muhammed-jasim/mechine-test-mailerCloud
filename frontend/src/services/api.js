import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getOverview = async () => {
  const response = await api.get('/api/analytics/overview/');
  return response.data;
};

export const getForms = async () => {
  const response = await api.get('/api/forms/');
  return response.data;
};

export const getFormSubmissions = async (formId, page = 1) => {
  const response = await api.get(`/api/forms/${encodeURIComponent(formId)}/submissions/?page=${page}`);
  return response.data;
};

export const getAllSubmissions = async (page = 1, formId = '') => {
  const url = formId 
    ? `/api/submissions/?page=${page}&form_id=${encodeURIComponent(formId)}`
    : `/api/submissions/?page=${page}`;
  const response = await api.get(url);
  return response.data;
};

export const getHourlyAnalytics = async (formId = '') => {
  const url = formId 
    ? `/api/analytics/hourly/?form_id=${encodeURIComponent(formId)}`
    : '/api/analytics/hourly/';
  const response = await api.get(url);
  return response.data;
};

export const submitForm = async (payload) => {
  const response = await api.post('/api/submissions/', payload);
  return response.data;
};

export default api;
