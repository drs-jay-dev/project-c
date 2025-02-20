import React from 'react';
import { Box, Grid, Paper, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { contactsApi, ordersApi } from '../../services/api';
import { Contact, Order } from '../../types';

export const DashboardPage: React.FC = () => {
    const { data: contacts } = useQuery<Contact[]>({
        queryKey: ['contacts'],
        queryFn: () => contactsApi.getAll().then((res) => res.data),
    });

    const { data: orders } = useQuery<Order[]>({
        queryKey: ['orders'],
        queryFn: () => ordersApi.getAll().then((res) => res.data),
    });

    const totalContacts = contacts?.length || 0;
    const totalOrders = orders?.length || 0;
    const totalRevenue = orders?.reduce((sum, order) => sum + parseFloat(order.total_amount), 0) || 0;

    return (
        <Box>
            <Typography variant="h4" sx={{ mb: 4 }}>Dashboard</Typography>
            <Grid container spacing={3}>
                <Grid item xs={12} md={4}>
                    <Paper sx={{ p: 3, textAlign: 'center' }}>
                        <Typography variant="h6" color="primary">Total Contacts</Typography>
                        <Typography variant="h3">{totalContacts}</Typography>
                    </Paper>
                </Grid>
                <Grid item xs={12} md={4}>
                    <Paper sx={{ p: 3, textAlign: 'center' }}>
                        <Typography variant="h6" color="primary">Total Orders</Typography>
                        <Typography variant="h3">{totalOrders}</Typography>
                    </Paper>
                </Grid>
                <Grid item xs={12} md={4}>
                    <Paper sx={{ p: 3, textAlign: 'center' }}>
                        <Typography variant="h6" color="primary">Total Revenue</Typography>
                        <Typography variant="h3">${totalRevenue.toFixed(2)}</Typography>
                    </Paper>
                </Grid>
                <Grid item xs={12}>
                    <Paper sx={{ p: 3 }}>
                        <Typography variant="h6" sx={{ mb: 2 }}>Recent Orders</Typography>
                        {orders?.slice(0, 5).map((order) => (
                            <Box key={order.id} sx={{ mb: 2, p: 2, bgcolor: 'background.default' }}>
                                <Typography>
                                    Order #{order.woo_order_id} - ${order.total_amount}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    {new Date(order.order_date).toLocaleDateString()}
                                </Typography>
                            </Box>
                        ))}
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};
