import axios from 'axios';

const RAW_BASE = import.meta.env.VITE_API_URL || 'https://franchise-iq-backend.onrender.com';
let BASE = RAW_BASE.replace(/\/+$/, '');
if (BASE && !BASE.startsWith('http')) {
  BASE = `https://${BASE}`;
}

const authApi = axios.create({ baseURL: `${BASE}/api`, timeout: 30_000 });

const TOKEN_KEY = 'franchiseiq_token';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export const login = async ({ email, password }) => {
  // Backend expects OAuth2PasswordRequestForm — form-encoded, field name "username".
  const form = new URLSearchParams();
  form.append('username', email);
  form.append('password', password);
  const { data } = await authApi.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  setToken(data.access_token);
  return data;
};

export const logout = () => clearToken();

export const fetchMe = async () => {
  const token = getToken();
  if (!token) return null;
  try {
    const { data } = await authApi.get('/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return data;
  } catch {
    clearToken();
    return null;
  }
};

export default authApi;
