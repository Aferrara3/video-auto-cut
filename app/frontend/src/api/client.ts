import axios from 'axios';

const api = axios.create({
  baseURL: '/api', // Vite proxy handles redirection
  headers: {
    'Content-Type': 'application/json',
  },
});

export const broll = {
  ingest: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await api.post('/broll/ingest', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
  search: async (query: string) => {
    const { data } = await api.get('/broll/search', { params: { query } });
    return data;
  },
  getAll: async () => {
    const { data } = await api.get('/broll/library');
    return data;
  }
};

export const jobs = {
  upload: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await api.post('/jobs/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
  transcribe: async (jobId: string) => {
    const { data } = await api.post(`/jobs/${jobId}/transcribe`);
    return data;
  },
  plan: async (jobId: string, srtContent: string) => {
    const { data } = await api.post(`/jobs/${jobId}/plan`, { srt_content: srtContent });
    return data;
  },
  render: async (jobId: string, clips: any[]) => {
    const { data } = await api.post(`/jobs/${jobId}/render`, { clips });
    return data;
  },
  getStatus: async (jobId: string) => {
    const { data } = await api.get(`/jobs/${jobId}`);
    return data;
  }
};

export const action = {
  ingest: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await api.post('/action/ingest', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
  plan: async (jobId: string) => {
    const { data } = await api.post(`/action/${jobId}/plan`);
    return data;
  },
  render: async (jobId: string, plan?: any[]) => {
    const { data } = await api.post(`/action/${jobId}/render`, { plan });
    return data;
  },
  getStatus: async (jobId: string) => {
    // Reusing the general jobs status endpoint since action jobs are stored there too
    const { data } = await api.get(`/jobs/${jobId}`);
    return data;
  }
};

export default api;