export interface Contact {
    id: string;
    first_name: string;
    last_name: string;
    email: string;
    phone: string;
    billing_address: string;
    billing_city: string;
    billing_state: string;
    billing_postcode: string;
    created_at: string;
    updated_at: string;
    orders?: Order[];
}

export interface Order {
    id: string;
    contact: string | Contact;
    woo_order_id: string;
    order_date: string;
    total_amount: string;
    status: string;
    created_at: string;
    updated_at: string;
}
