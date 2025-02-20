import React from 'react';
import {
    Box,
    Typography,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { ordersApi } from '../../services/api';
import { Order } from '../../types';

export const OrdersPage: React.FC = () => {
    const { data: orders, isLoading } = useQuery<Order[]>({
        queryKey: ['orders'],
        queryFn: () => ordersApi.getAll().then((res) => res.data),
    });

    if (isLoading) {
        return <Typography>Loading...</Typography>;
    }

    return (
        <Box>
            <Typography variant="h4" sx={{ mb: 2 }}>Orders</Typography>
            <TableContainer component={Paper}>
                <Table>
                    <TableHead>
                        <TableRow>
                            <TableCell>Order ID</TableCell>
                            <TableCell>Customer</TableCell>
                            <TableCell>Date</TableCell>
                            <TableCell>Total Amount</TableCell>
                            <TableCell>Status</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {orders?.map((order) => (
                            <TableRow key={order.id}>
                                <TableCell>{order.woo_order_id}</TableCell>
                                <TableCell>
                                    {typeof order.contact === 'object' 
                                        ? `${order.contact.first_name} ${order.contact.last_name}`
                                        : order.contact}
                                </TableCell>
                                <TableCell>
                                    {new Date(order.order_date).toLocaleDateString()}
                                </TableCell>
                                <TableCell>${order.total_amount}</TableCell>
                                <TableCell>{order.status}</TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    );
};
