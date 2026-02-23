-- AgentX PostgreSQL Initialization Script
-- This script sets up the sample schema for evaluation

-- Create customers table
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    city VARCHAR(100),
    phone VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    order_date DATE,
    total DECIMAL(10, 2),
    status VARCHAR(50) DEFAULT 'pending'
);

-- Create products table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2),
    category VARCHAR(100),
    stock INTEGER DEFAULT 0
);

-- Create order_items table
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER,
    unit_price DECIMAL(10, 2)
);

-- Insert sample customers
INSERT INTO customers (id, name, email, city, phone) VALUES
    (1, 'Alice Johnson', 'alice@example.com', 'New York', '555-0101'),
    (2, 'Bob Smith', 'bob@example.com', 'Los Angeles', '555-0102'),
    (3, 'Charlie Brown', 'charlie@example.com', 'Chicago', '555-0103'),
    (4, 'Diana Ross', 'diana@example.com', 'New York', '555-0104'),
    (5, 'Edward Kim', 'edward@example.com', 'San Francisco', NULL),
    (6, 'Fiona Green', 'fiona@example.com', 'Boston', '555-0106'),
    (7, 'George White', 'george@example.com', 'Seattle', '555-0107'),
    (8, 'Hannah Lee', 'hannah@example.com', 'Austin', '555-0108'),
    (9, 'Ivan Chen', 'ivan@example.com', 'Denver', '555-0109'),
    (10, 'Julia Martinez', 'julia@example.com', 'Miami', '555-0110')
ON CONFLICT (id) DO NOTHING;

-- Insert sample orders
INSERT INTO orders (id, customer_id, order_date, total, status) VALUES
    (1, 1, '2024-01-15', 150.00, 'completed'),
    (2, 1, '2024-02-20', 75.50, 'completed'),
    (3, 2, '2024-01-25', 200.00, 'completed'),
    (4, 3, '2024-03-01', 50.00, 'pending'),
    (5, 4, '2024-03-10', 1200.00, 'completed'),
    (6, 5, '2024-03-15', 89.99, 'completed'),
    (7, 6, '2024-03-20', 350.00, 'shipped'),
    (8, 7, '2024-03-25', 175.25, 'pending'),
    (9, 8, '2024-04-01', 500.00, 'completed'),
    (10, 9, '2024-04-05', 99.99, 'cancelled')
ON CONFLICT (id) DO NOTHING;

-- Insert sample products
INSERT INTO products (id, name, price, category, stock) VALUES
    (1, 'Laptop', 999.99, 'Electronics', 50),
    (2, 'Smartphone', 699.99, 'Electronics', 100),
    (3, 'Headphones', 149.99, 'Electronics', 200),
    (4, 'Desk Chair', 299.99, 'Furniture', 30),
    (5, 'Monitor', 349.99, 'Electronics', 75),
    (6, 'Keyboard', 79.99, 'Electronics', 150),
    (7, 'Mouse', 29.99, 'Electronics', 200),
    (8, 'Desk Lamp', 49.99, 'Home', 100),
    (9, 'Notebook', 9.99, 'Office', 500),
    (10, 'Pen Set', 14.99, 'Office', 300)
ON CONFLICT (id) DO NOTHING;

-- Insert sample order items
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
    (1, 3, 1, 149.99),
    (2, 7, 2, 29.99),
    (2, 9, 2, 9.99),
    (3, 2, 1, 199.99),
    (4, 9, 5, 9.99),
    (5, 1, 1, 999.99),
    (5, 3, 1, 149.99),
    (6, 8, 2, 44.99),
    (7, 4, 1, 299.99),
    (7, 8, 1, 49.99);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_customers_city ON customers(city);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

-- Reset sequences
SELECT setval('customers_id_seq', (SELECT MAX(id) FROM customers));
SELECT setval('orders_id_seq', (SELECT MAX(id) FROM orders));
SELECT setval('products_id_seq', (SELECT MAX(id) FROM products));

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO agentx;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO agentx;
