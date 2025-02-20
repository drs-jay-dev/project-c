import axios from 'axios';
import { Contact, Order } from '../types';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add token to requests if it exists
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export const contactsApi = {
    getAll: () => api.get<Contact[]>('/contacts/'),
    getOne: (id: string) => api.get<Contact>(`/contacts/${id}/`),
    create: (data: Partial<Contact>) => api.post<Contact>('/contacts/', data),
    update: (id: string, data: Partial<Contact>) => api.put<Contact>(`/contacts/${id}/`, data),
    delete: (id: string) => api.delete(`/contacts/${id}/`),
};

export const ordersApi = {
    getAll: () => api.get<Order[]>('/orders/'),
    getOne: (id: string) => api.get<Order>(`/orders/${id}/`),
};

export const syncApi = {
    syncWooCommerce: () => api.post('/sync-woocommerce/'),
};
