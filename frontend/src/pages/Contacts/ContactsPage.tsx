import React, { useState, useEffect } from 'react';
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
    CircularProgress,
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

interface ContactsResponse {
    count: number;
    next: string | null;
    previous: string | null;
    results: Contact[];
}

type Order = 'asc' | 'desc';
type OrderBy = 'first_name' | 'last_name' | 'email' | 'phone';

export const ContactsPage: React.FC = () => {
    const queryClient = useQueryClient();
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);
    const [searchTerm, setSearchTerm] = useState('');
    const [debouncedSearchTerm, setDebouncedSearchTerm] = useState(searchTerm);
    const [order, setOrder] = useState<Order>('asc');
    const [orderBy, setOrderBy] = useState<OrderBy>('last_name');
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
    const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

    // Debounce search term
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearchTerm(searchTerm);
        }, 300); // 300ms delay

        return () => clearTimeout(timer);
    }, [searchTerm]);

    const { data: contactsData, isLoading, error } = useQuery<ContactsResponse>({
        queryKey: ['contacts', page, pageSize, debouncedSearchTerm, order, orderBy],
        queryFn: async () => {
            const response = await contactsApi.getAll(page, pageSize, debouncedSearchTerm, {
                ordering: `${order === 'desc' ? '-' : ''}${orderBy}`,
            });
            return response.data;
        },
    });

    const contacts = contactsData?.results || [];
    const totalContacts = contactsData?.count || 0;

    const mutation = useMutation({
        mutationFn: () => syncApi.syncWooCommerce('customers'),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['contacts', page, pageSize, debouncedSearchTerm, order, orderBy] });
        },
    });

    const handleSort = (property: OrderBy) => {
        const isAsc = orderBy === property && order === 'asc';
        setOrder(isAsc ? 'desc' : 'asc');
        setOrderBy(property);
    };

    const handleChangePage = (event: unknown, newPage: number) => {
        setPage(newPage + 1); // Convert 0-based to 1-based
    };

    const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
        setPageSize(parseInt(event.target.value, 10));
        setPage(1);
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

    const handleSearch = (event: React.ChangeEvent<HTMLInputElement>) => {
        setSearchTerm(event.target.value);
        setPage(1); // Reset to first page when searching
    };

    if (isLoading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
                <CircularProgress />
            </Box>
        );
    }

    if (error) {
        return <Alert severity="error">Error loading contacts</Alert>;
    }

    return (
        <Box>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Typography variant="h4">Contacts</Typography>
                <Stack direction="row" spacing={2}>
                    <Button
                        variant="contained"
                        color="primary"
                        onClick={() => mutation.mutate()}
                        startIcon={<Sync />}
                        disabled={mutation.isPending}
                    >
                        {mutation.isPending ? 'Syncing...' : 'Sync Contacts'}
                    </Button>
                    <Button
                        variant="outlined"
                        startIcon={<FileDownload />}
                        onClick={handleExportCSV}
                    >
                        Export CSV
                    </Button>
                </Stack>
            </Box>

            {mutation.isSuccess && (
                <Alert severity="success" sx={{ mb: 2 }}>
                    Contacts synchronized successfully!
                </Alert>
            )}

            {mutation.isError && (
                <Alert severity="error" sx={{ mb: 2 }}>
                    Error synchronizing contacts
                </Alert>
            )}

            <Paper sx={{ mb: 2, p: 2 }}>
                <TextField
                    fullWidth
                    variant="outlined"
                    placeholder="Search contacts..."
                    value={searchTerm}
                    onChange={handleSearch}
                    InputProps={{
                        startAdornment: <Search sx={{ color: 'text.secondary', mr: 1 }} />,
                    }}
                    sx={{ mb: 2 }}
                />

                <TableContainer>
                    <Table>
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
                                <TableCell>
                                    <TableSortLabel
                                        active={orderBy === 'email'}
                                        direction={orderBy === 'email' ? order : 'asc'}
                                        onClick={() => handleSort('email')}
                                    >
                                        Email
                                    </TableSortLabel>
                                </TableCell>
                                <TableCell>
                                    <TableSortLabel
                                        active={orderBy === 'phone'}
                                        direction={orderBy === 'phone' ? order : 'asc'}
                                        onClick={() => handleSort('phone')}
                                    >
                                        Phone
                                    </TableSortLabel>
                                </TableCell>
                                <TableCell>Address</TableCell>
                                <TableCell>City</TableCell>
                                <TableCell>State</TableCell>
                                <TableCell>Postal Code</TableCell>
                                <TableCell>Actions</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {(contacts || []).map((contact) => (
                                <TableRow key={contact.id}>
                                    <TableCell>{contact.first_name}</TableCell>
                                    <TableCell>{contact.last_name}</TableCell>
                                    <TableCell>
                                        <Stack direction="row" spacing={1} alignItems="center">
                                            <Typography>{contact.email}</Typography>
                                            <IconButton
                                                size="small"
                                                onClick={() => window.location.href = `mailto:${contact.email}`}
                                            >
                                                <Mail fontSize="small" />
                                            </IconButton>
                                        </Stack>
                                    </TableCell>
                                    <TableCell>
                                        {contact.phone && (
                                            <Stack direction="row" spacing={1} alignItems="center">
                                                <Typography>{contact.phone}</Typography>
                                                <IconButton
                                                    size="small"
                                                    onClick={() => window.location.href = `tel:${contact.phone}`}
                                                >
                                                    <Phone fontSize="small" />
                                                </IconButton>
                                            </Stack>
                                        )}
                                    </TableCell>
                                    <TableCell>{contact.billing_address || '-'}</TableCell>
                                    <TableCell>{contact.billing_city || '-'}</TableCell>
                                    <TableCell>{contact.billing_state || '-'}</TableCell>
                                    <TableCell>{contact.billing_postcode || '-'}</TableCell>
                                    <TableCell>
                                        <IconButton
                                            size="small"
                                            onClick={(event) => handleMenuOpen(event, contact)}
                                        >
                                            <MoreVert />
                                        </IconButton>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>

                <TablePagination
                    component="div"
                    count={totalContacts}
                    page={page - 1} // Convert 1-based to 0-based for Material-UI
                    onPageChange={handleChangePage}
                    rowsPerPage={pageSize}
                    onRowsPerPageChange={handleChangeRowsPerPage}
                    rowsPerPageOptions={[10, 25, 50]}
                />
            </Paper>

            <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={handleMenuClose}
            >
                <MenuItem onClick={handleMenuClose}>
                    <Edit sx={{ mr: 1 }} /> Edit
                </MenuItem>
                <MenuItem onClick={handleMenuClose}>
                    <Delete sx={{ mr: 1 }} /> Delete
                </MenuItem>
            </Menu>
        </Box>
    );
};

export default ContactsPage;
