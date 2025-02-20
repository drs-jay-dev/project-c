import React, { useState } from 'react';
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
    Button,
    IconButton,
    TextField,
    TablePagination,
    Tooltip,
    Menu,
    MenuItem,
    Alert,
    TableSortLabel,
    Chip,
    Stack,
} from '@mui/material';
import { 
    Edit, 
    Delete, 
    Sync, 
    MoreVert, 
    FileDownload, 
    FilterList,
    Search,
    Mail,
    Phone,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { contactsApi, syncApi } from '../../services/api';
import { Contact } from '../../types';

type Order = 'asc' | 'desc';
type OrderBy = 'first_name' | 'last_name' | 'email' | 'phone';

export const ContactsPage: React.FC = () => {
    const queryClient = useQueryClient();
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(10);
    const [searchTerm, setSearchTerm] = useState('');
    const [order, setOrder] = useState<Order>('asc');
    const [orderBy, setOrderBy] = useState<OrderBy>('last_name');
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const [selectedContact, setSelectedContact] = useState<Contact | null>(null);

    const { data: contacts, isLoading, error } = useQuery<Contact[]>({
        queryKey: ['contacts'],
        queryFn: () => contactsApi.getAll().then((res) => res.data),
    });

    const mutation = useMutation({
        mutationFn: syncApi.syncWooCommerce,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['contacts'] });
        },
    });

    const handleSort = (property: OrderBy) => {
        const isAsc = orderBy === property && order === 'asc';
        setOrder(isAsc ? 'desc' : 'asc');
        setOrderBy(property);
    };

    const handleChangePage = (event: unknown, newPage: number) => {
        setPage(newPage);
    };

    const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
        setRowsPerPage(parseInt(event.target.value, 10));
        setPage(0);
    };

    const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, contact: Contact) => {
        setAnchorEl(event.currentTarget);
        setSelectedContact(contact);
    };

    const handleMenuClose = () => {
        setAnchorEl(null);
        setSelectedContact(null);
    };

    const handleExportCSV = () => {
        // TODO: Implement CSV export
        console.log('Exporting to CSV...');
    };

    const filteredContacts = contacts?.filter((contact) => {
        const searchStr = searchTerm.toLowerCase();
        return (
            contact.first_name.toLowerCase().includes(searchStr) ||
            contact.last_name.toLowerCase().includes(searchStr) ||
            contact.email.toLowerCase().includes(searchStr) ||
            contact.phone.toLowerCase().includes(searchStr)
        );
    }) || [];

    const sortedContacts = [...filteredContacts].sort((a, b) => {
        const isAsc = order === 'asc';
        if (orderBy === 'first_name') {
            return isAsc ? a.first_name.localeCompare(b.first_name) : b.first_name.localeCompare(a.first_name);
        }
        if (orderBy === 'last_name') {
            return isAsc ? a.last_name.localeCompare(b.last_name) : b.last_name.localeCompare(a.last_name);
        }
        return 0;
    });

    const paginatedContacts = sortedContacts.slice(
        page * rowsPerPage,
        page * rowsPerPage + rowsPerPage
    );

    if (error) {
        return <Alert severity="error">Error loading contacts. Please try again later.</Alert>;
    }

    return (
        <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="h4">Contacts</Typography>
                <Stack direction="row" spacing={2}>
                    <Button
                        variant="contained"
                        startIcon={<FileDownload />}
                        onClick={handleExportCSV}
                    >
                        Export CSV
                    </Button>
                    <Button
                        variant="contained"
                        startIcon={<Sync />}
                        onClick={() => mutation.mutate()}
                        disabled={mutation.status === 'pending'}
                    >
                        Sync WooCommerce
                    </Button>
                </Stack>
            </Box>

            <Paper sx={{ mb: 2, p: 2 }}>
                <Stack direction="row" spacing={2} alignItems="center">
                    <TextField
                        size="small"
                        placeholder="Search contacts..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        InputProps={{
                            startAdornment: <Search sx={{ color: 'text.secondary', mr: 1 }} />,
                        }}
                        sx={{ width: 300 }}
                    />
                    <Button
                        startIcon={<FilterList />}
                        size="small"
                    >
                        Filter
                    </Button>
                    {searchTerm && (
                        <Chip 
                            label={`Search: ${searchTerm}`}
                            onDelete={() => setSearchTerm('')}
                            size="small"
                        />
                    )}
                </Stack>
            </Paper>

            <TableContainer component={Paper}>
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell>
                                <TableSortLabel
                                    active={orderBy === 'first_name'}
                                    direction={orderBy === 'first_name' ? order : 'asc'}
                                    onClick={() => handleSort('first_name')}
                                >
                                    First Name
                                </TableSortLabel>
                            </TableCell>
                            <TableCell>
                                <TableSortLabel
                                    active={orderBy === 'last_name'}
                                    direction={orderBy === 'last_name' ? order : 'asc'}
                                    onClick={() => handleSort('last_name')}
                                >
                                    Last Name
                                </TableSortLabel>
                            </TableCell>
                            <TableCell>Email</TableCell>
                            <TableCell>Phone</TableCell>
                            <TableCell>Billing Address</TableCell>
                            <TableCell>Billing City</TableCell>
                            <TableCell>Billing State</TableCell>
                            <TableCell>Billing Zip</TableCell>
                            <TableCell>Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {isLoading ? (
                            <TableRow>
                                <TableCell colSpan={9} align="center">Loading...</TableCell>
                            </TableRow>
                        ) : paginatedContacts.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={9} align="center">No contacts found</TableCell>
                            </TableRow>
                        ) : (
                            paginatedContacts.map((contact) => (
                                <TableRow key={contact.id} hover>
                                    <TableCell>{contact.first_name}</TableCell>
                                    <TableCell>{contact.last_name}</TableCell>
                                    <TableCell>{contact.email}</TableCell>
                                    <TableCell>{contact.phone}</TableCell>
                                    <TableCell>{contact.billing_address}</TableCell>
                                    <TableCell>{contact.billing_city}</TableCell>
                                    <TableCell>{contact.billing_state}</TableCell>
                                    <TableCell>{contact.billing_postcode}</TableCell>
                                    <TableCell>
                                        <Tooltip title="Edit">
                                            <IconButton size="small">
                                                <Edit fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title="More actions">
                                            <IconButton 
                                                size="small"
                                                onClick={(e) => handleMenuOpen(e, contact)}
                                            >
                                                <MoreVert fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
                <TablePagination
                    rowsPerPageOptions={[5, 10, 25, 50]}
                    component="div"
                    count={filteredContacts.length}
                    rowsPerPage={rowsPerPage}
                    page={page}
                    onPageChange={handleChangePage}
                    onRowsPerPageChange={handleChangeRowsPerPage}
                />
            </TableContainer>

            <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={handleMenuClose}
            >
                <MenuItem onClick={handleMenuClose}>
                    <Mail sx={{ mr: 1 }} fontSize="small" />
                    Send Email
                </MenuItem>
                <MenuItem onClick={handleMenuClose}>
                    <Phone sx={{ mr: 1 }} fontSize="small" />
                    Call Contact
                </MenuItem>
                <MenuItem onClick={handleMenuClose} sx={{ color: 'error.main' }}>
                    <Delete sx={{ mr: 1 }} fontSize="small" />
                    Delete Contact
                </MenuItem>
            </Menu>
        </Box>
    );
};
