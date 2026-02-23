"""
Enterprise Schema Setup for AgentX Benchmark.

Creates a realistic enterprise data warehouse schema with:
- Fact tables (sales, orders, user events)
- Dimension tables (customer, product, store, date, promotion)
- SCD Type 2 dimension (customer history)
- Multi-tenant support
- Hierarchy tables (employees, BOM)
- Supporting tables (marketing, support, engagement)

Usage:
    from tasks.enterprise_schema import setup_enterprise_schema
    setup_enterprise_schema(executor)
"""

import random
from datetime import datetime, timedelta


def setup_enterprise_schema(executor):
    """
    Setup complete enterprise schema with sample data.

    Args:
        executor: SQLExecutor instance
    """
    adapter = executor.adapter

    # Drop existing tables (in reverse dependency order)
    tables_to_drop = [
        'marketing_touches', 'customer_engagement', 'support_tickets',
        'payments', 'shipping', 'inventory', 'bill_of_materials',
        'employees', 'staging_customer', 'user_events', 'orders_fact',
        'sales_fact', 'dim_promotion', 'dim_date', 'dim_store',
        'dim_product', 'dim_customer_scd', 'dim_customer', 'tenants'
    ]

    for table in tables_to_drop:
        try:
            adapter.execute(f"DROP TABLE IF EXISTS {table}")
        except:
            pass

    # =========================================================================
    # DIMENSION TABLES
    # =========================================================================

    # Tenants (for multi-tenant queries)
    adapter.execute("""
        CREATE TABLE tenants (
            tenant_id INTEGER PRIMARY KEY,
            tenant_name TEXT NOT NULL,
            plan_type TEXT,
            created_at TEXT
        )
    """)

    # Dim Customer
    adapter.execute("""
        CREATE TABLE dim_customer (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            email TEXT,
            segment TEXT,
            region TEXT,
            created_at TEXT
        )
    """)

    # Dim Customer SCD Type 2
    adapter.execute("""
        CREATE TABLE dim_customer_scd (
            surrogate_key INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            email TEXT,
            segment TEXT,
            valid_from TEXT NOT NULL,
            valid_to TEXT,
            is_current INTEGER DEFAULT 1
        )
    """)

    # Staging Customer (for SCD merge simulation)
    adapter.execute("""
        CREATE TABLE staging_customer (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            email TEXT,
            segment TEXT
        )
    """)

    # Dim Product
    adapter.execute("""
        CREATE TABLE dim_product (
            product_id TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT,
            subcategory TEXT,
            brand TEXT,
            unit_cost REAL,
            list_price REAL
        )
    """)

    # Dim Store
    adapter.execute("""
        CREATE TABLE dim_store (
            store_id INTEGER PRIMARY KEY,
            store_name TEXT NOT NULL,
            region TEXT,
            city TEXT,
            state TEXT,
            country TEXT,
            store_type TEXT
        )
    """)

    # Dim Date
    adapter.execute("""
        CREATE TABLE dim_date (
            date_id INTEGER PRIMARY KEY,
            full_date TEXT NOT NULL,
            year INTEGER,
            quarter INTEGER,
            month INTEGER,
            week INTEGER,
            day_of_week TEXT,
            day_of_month INTEGER,
            is_weekend INTEGER,
            is_holiday INTEGER
        )
    """)

    # Dim Promotion
    adapter.execute("""
        CREATE TABLE dim_promotion (
            promotion_id INTEGER PRIMARY KEY,
            promotion_name TEXT NOT NULL,
            promotion_type TEXT,
            discount_pct REAL,
            start_date TEXT,
            end_date TEXT
        )
    """)

    # =========================================================================
    # FACT TABLES
    # =========================================================================

    # Sales Fact (star schema center)
    adapter.execute("""
        CREATE TABLE sales_fact (
            transaction_id INTEGER PRIMARY KEY,
            tenant_id INTEGER,
            customer_id INTEGER,
            product_id TEXT,
            store_id INTEGER,
            date_id INTEGER,
            promotion_id INTEGER,
            quantity INTEGER,
            unit_price REAL,
            cost_amount REAL,
            order_date TEXT,
            load_timestamp TEXT,
            FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id),
            FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
            FOREIGN KEY (store_id) REFERENCES dim_store(store_id),
            FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
        )
    """)

    # Orders Fact
    adapter.execute("""
        CREATE TABLE orders_fact (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product_id TEXT,
            store_id INTEGER,
            date_id INTEGER,
            promotion_id INTEGER,
            order_date TEXT,
            total_amount REAL,
            cost_amount REAL,
            quantity INTEGER,
            unit_price REAL,
            status TEXT,
            load_timestamp TEXT,
            FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id),
            FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
            FOREIGN KEY (store_id) REFERENCES dim_store(store_id),
            FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
        )
    """)

    # User Events (for funnel and sessionization)
    adapter.execute("""
        CREATE TABLE user_events (
            event_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            event_type TEXT,
            event_timestamp TEXT,
            page_url TEXT,
            session_id TEXT
        )
    """)

    # =========================================================================
    # SUPPORTING TABLES
    # =========================================================================

    # Employees (for hierarchy)
    adapter.execute("""
        CREATE TABLE employees (
            employee_id INTEGER PRIMARY KEY,
            employee_name TEXT NOT NULL,
            title TEXT,
            department TEXT,
            manager_id INTEGER,
            hire_date TEXT,
            FOREIGN KEY (manager_id) REFERENCES employees(employee_id)
        )
    """)

    # Bill of Materials
    adapter.execute("""
        CREATE TABLE bill_of_materials (
            bom_id INTEGER PRIMARY KEY,
            parent_product_id TEXT,
            component_id TEXT,
            quantity INTEGER,
            FOREIGN KEY (parent_product_id) REFERENCES dim_product(product_id),
            FOREIGN KEY (component_id) REFERENCES dim_product(product_id)
        )
    """)

    # Inventory
    adapter.execute("""
        CREATE TABLE inventory (
            product_id TEXT PRIMARY KEY,
            current_stock INTEGER,
            reorder_point INTEGER,
            last_restock_date TEXT
        )
    """)

    # Shipping
    adapter.execute("""
        CREATE TABLE shipping (
            shipping_id INTEGER PRIMARY KEY,
            order_id INTEGER,
            carrier TEXT,
            shipping_method TEXT,
            ship_date TEXT,
            delivery_date TEXT,
            FOREIGN KEY (order_id) REFERENCES orders_fact(order_id)
        )
    """)

    # Payments
    adapter.execute("""
        CREATE TABLE payments (
            payment_id INTEGER PRIMARY KEY,
            order_id INTEGER,
            payment_method TEXT,
            payment_status TEXT,
            payment_date TEXT,
            amount REAL,
            FOREIGN KEY (order_id) REFERENCES orders_fact(order_id)
        )
    """)

    # Support Tickets
    adapter.execute("""
        CREATE TABLE support_tickets (
            ticket_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            subject TEXT,
            status TEXT,
            priority TEXT,
            created_at TEXT,
            resolved_at TEXT,
            resolution_hours REAL,
            FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id)
        )
    """)

    # Customer Engagement
    adapter.execute("""
        CREATE TABLE customer_engagement (
            engagement_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            last_login TEXT,
            page_views INTEGER,
            email_opens INTEGER,
            email_clicks INTEGER,
            FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id)
        )
    """)

    # Marketing Touches
    adapter.execute("""
        CREATE TABLE marketing_touches (
            touch_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            order_id INTEGER,
            channel TEXT,
            touch_timestamp TEXT,
            campaign_id TEXT,
            FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id)
        )
    """)

    # =========================================================================
    # INSERT SAMPLE DATA
    # =========================================================================

    _insert_sample_data(adapter)

    # Refresh schema
    executor.refresh_schema()

    return True


def _insert_sample_data(adapter):
    """Insert comprehensive sample data for enterprise queries."""

    # Tenants
    tenants = [
        (1, 'Acme Corp', 'Enterprise', '2023-01-01'),
        (2, 'TechStart Inc', 'Professional', '2023-03-15'),
        (3, 'Global Retail', 'Enterprise', '2023-02-01'),
    ]
    for t in tenants:
        adapter.execute(f"INSERT INTO tenants VALUES ({t[0]}, '{t[1]}', '{t[2]}', '{t[3]}')")

    # Customers
    segments = ['Enterprise', 'SMB', 'Consumer', 'Startup']
    regions = ['North', 'South', 'East', 'West']
    customers = []
    for i in range(1, 51):
        name = f"Customer_{i:03d}"
        email = f"customer{i}@example.com"
        segment = segments[i % len(segments)]
        region = regions[i % len(regions)]
        customers.append((i, name, email, segment, region, f'2023-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}'))

    for c in customers:
        adapter.execute(f"INSERT INTO dim_customer VALUES ({c[0]}, '{c[1]}', '{c[2]}', '{c[3]}', '{c[4]}', '{c[5]}')")

    # Customer SCD Type 2 (with history)
    scd_records = [
        (1001, 'John Smith', 'john@example.com', 'Consumer', '2023-01-01', '2024-03-15', 0),
        (1001, 'John Smith', 'john.smith@example.com', 'SMB', '2024-03-15', '2024-09-01', 0),
        (1001, 'John Smith', 'john.smith@example.com', 'Enterprise', '2024-09-01', None, 1),
        (1002, 'Jane Doe', 'jane@example.com', 'SMB', '2023-02-01', None, 1),
        (1003, 'Bob Wilson', 'bob@example.com', 'Consumer', '2023-03-01', '2024-06-01', 0),
        (1003, 'Bob Wilson', 'bob.wilson@example.com', 'Consumer', '2024-06-01', None, 1),
    ]
    for s in scd_records:
        valid_to = f"'{s[5]}'" if s[5] else "NULL"
        adapter.execute(f"INSERT INTO dim_customer_scd (customer_id, customer_name, email, segment, valid_from, valid_to, is_current) VALUES ({s[0]}, '{s[1]}', '{s[2]}', '{s[3]}', '{s[4]}', {valid_to}, {s[6]})")

    # Staging customers (for merge simulation)
    staging = [
        (1001, 'John Smith', 'john.smith.new@example.com', 'Enterprise'),  # Update
        (1002, 'Jane Doe', 'jane@example.com', 'SMB'),  # No change
        (1004, 'Alice Brown', 'alice@example.com', 'Startup'),  # Insert
    ]
    for s in staging:
        adapter.execute(f"INSERT INTO staging_customer VALUES ({s[0]}, '{s[1]}', '{s[2]}', '{s[3]}')")

    # Products
    categories = ['Electronics', 'Clothing', 'Home', 'Sports', 'Books']
    products = []
    for i in range(1, 31):
        prod_id = f"PROD{i:03d}"
        name = f"Product_{i:03d}"
        category = categories[i % len(categories)]
        subcategory = f"{category}_Sub{i % 3}"
        brand = f"Brand_{chr(65 + (i % 5))}"
        cost = round(10 + (i * 2.5), 2)
        price = round(cost * 1.4, 2)
        products.append((prod_id, name, category, subcategory, brand, cost, price))

    for p in products:
        adapter.execute(f"INSERT INTO dim_product VALUES ('{p[0]}', '{p[1]}', '{p[2]}', '{p[3]}', '{p[4]}', {p[5]}, {p[6]})")

    # Stores
    stores = [
        (1, 'Downtown Store', 'East', 'New York', 'NY', 'USA', 'Flagship'),
        (2, 'Mall Store', 'West', 'Los Angeles', 'CA', 'USA', 'Standard'),
        (3, 'Outlet Store', 'South', 'Miami', 'FL', 'USA', 'Outlet'),
        (4, 'Express Store', 'North', 'Chicago', 'IL', 'USA', 'Express'),
        (5, 'Online Store', 'National', 'Virtual', 'NA', 'USA', 'Digital'),
    ]
    for s in stores:
        adapter.execute(f"INSERT INTO dim_store VALUES ({s[0]}, '{s[1]}', '{s[2]}', '{s[3]}', '{s[4]}', '{s[5]}', '{s[6]}')")

    # Date dimension (2024)
    days_of_week = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    holidays = ['2024-01-01', '2024-07-04', '2024-11-28', '2024-12-25']

    start_date = datetime(2024, 1, 1)
    for i in range(365):
        d = start_date + timedelta(days=i)
        date_id = int(d.strftime('%Y%m%d'))
        full_date = d.strftime('%Y-%m-%d')
        year = d.year
        quarter = (d.month - 1) // 3 + 1
        month = d.month
        week = d.isocalendar()[1]
        dow = days_of_week[d.weekday()]
        dom = d.day
        is_weekend = 1 if d.weekday() >= 5 else 0
        is_holiday = 1 if full_date in holidays else 0

        adapter.execute(f"INSERT INTO dim_date VALUES ({date_id}, '{full_date}', {year}, {quarter}, {month}, {week}, '{dow}', {dom}, {is_weekend}, {is_holiday})")

    # Promotions
    promotions = [
        (1, 'Summer Sale', 'Seasonal', 15.0, '2024-06-01', '2024-08-31'),
        (2, 'Black Friday', 'Event', 25.0, '2024-11-29', '2024-11-29'),
        (3, 'Loyalty Bonus', 'Loyalty', 10.0, '2024-01-01', '2024-12-31'),
        (4, 'New Customer', 'Acquisition', 20.0, '2024-01-01', '2024-12-31'),
    ]
    for p in promotions:
        adapter.execute(f"INSERT INTO dim_promotion VALUES ({p[0]}, '{p[1]}', '{p[2]}', {p[3]}, '{p[4]}', '{p[5]}')")

    # Sales Fact (500 transactions)
    random.seed(42)  # For reproducibility
    for i in range(1, 501):
        tenant_id = random.choice([1, 2, 3])
        customer_id = random.randint(1, 50)
        product_id = f"PROD{random.randint(1, 30):03d}"
        store_id = random.randint(1, 5)

        # Random date in 2024
        day_offset = random.randint(0, 300)
        sale_date = datetime(2024, 1, 1) + timedelta(days=day_offset)
        date_id = int(sale_date.strftime('%Y%m%d'))
        order_date = sale_date.strftime('%Y-%m-%d')

        promotion_id = random.choice([None, 1, 2, 3, 4])
        quantity = random.randint(1, 10)
        unit_price = round(15 + random.random() * 100, 2)
        cost = round(unit_price * 0.6, 2)

        load_date = sale_date + timedelta(days=random.choice([0, 0, 0, 1, 2, 5]))  # Some late
        load_timestamp = load_date.strftime('%Y-%m-%d %H:%M:%S')

        promo_val = promotion_id if promotion_id else "NULL"
        adapter.execute(f"INSERT INTO sales_fact VALUES ({i}, {tenant_id}, {customer_id}, '{product_id}', {store_id}, {date_id}, {promo_val}, {quantity}, {unit_price}, {cost}, '{order_date}', '{load_timestamp}')")

    # Orders Fact (300 orders)
    for i in range(1, 301):
        customer_id = random.randint(1, 50)
        product_id = f"PROD{random.randint(1, 30):03d}"
        store_id = random.randint(1, 5)

        day_offset = random.randint(0, 300)
        order_datetime = datetime(2024, 1, 1) + timedelta(days=day_offset)
        order_date = order_datetime.strftime('%Y-%m-%d')
        date_id = int(order_datetime.strftime('%Y%m%d'))

        promotion_id = random.choice([None, 1, 2, 3, 4])
        quantity = random.randint(1, 5)
        unit_price = round(20 + random.random() * 100, 2)
        total = round(unit_price * quantity, 2)
        cost = round(total * 0.65, 2)
        status = random.choice(['completed', 'completed', 'completed', 'pending', 'cancelled'])

        load_date = order_datetime + timedelta(days=random.choice([0, 0, 1, 3]))
        load_timestamp = load_date.strftime('%Y-%m-%d %H:%M:%S')

        promo_val = promotion_id if promotion_id else "NULL"
        adapter.execute(f"INSERT INTO orders_fact VALUES ({i}, {customer_id}, '{product_id}', {store_id}, {date_id}, {promo_val}, '{order_date}', {total}, {cost}, {quantity}, {unit_price}, '{status}', '{load_timestamp}')")

    # User Events (for funnel and sessions)
    event_types = ['page_view', 'add_to_cart', 'checkout', 'purchase']
    for i in range(1, 1001):
        user_id = random.randint(1, 100)

        # Simulate funnel dropoff
        r = random.random()
        if r < 0.6:
            event_type = 'page_view'
        elif r < 0.8:
            event_type = 'add_to_cart'
        elif r < 0.9:
            event_type = 'checkout'
        else:
            event_type = 'purchase'

        day_offset = random.randint(0, 30)
        hour = random.randint(8, 22)
        minute = random.randint(0, 59)
        event_time = (datetime(2024, 10, 1) + timedelta(days=day_offset, hours=hour, minutes=minute)).strftime('%Y-%m-%d %H:%M:%S')

        page = f"/page/{random.randint(1, 20)}"

        adapter.execute(f"INSERT INTO user_events VALUES ({i}, {user_id}, '{event_type}', '{event_time}', '{page}', NULL)")

    # Employees (hierarchy)
    employees = [
        (1, 'CEO Smith', 'CEO', 'Executive', None, '2020-01-01'),
        (2, 'VP Johnson', 'VP Sales', 'Sales', 1, '2020-03-01'),
        (3, 'VP Williams', 'VP Engineering', 'Engineering', 1, '2020-02-15'),
        (4, 'Dir Brown', 'Sales Director', 'Sales', 2, '2021-01-01'),
        (5, 'Dir Davis', 'Engineering Director', 'Engineering', 3, '2021-02-01'),
        (6, 'Mgr Wilson', 'Sales Manager', 'Sales', 4, '2022-01-01'),
        (7, 'Mgr Taylor', 'Engineering Manager', 'Engineering', 5, '2022-03-01'),
        (8, 'Rep Anderson', 'Sales Rep', 'Sales', 6, '2023-01-01'),
        (9, 'Rep Thomas', 'Sales Rep', 'Sales', 6, '2023-02-01'),
        (10, 'Dev Jackson', 'Software Developer', 'Engineering', 7, '2023-01-15'),
    ]
    for e in employees:
        mgr = e[4] if e[4] else "NULL"
        adapter.execute(f"INSERT INTO employees VALUES ({e[0]}, '{e[1]}', '{e[2]}', '{e[3]}', {mgr}, '{e[5]}')")

    # Bill of Materials
    bom = [
        (1, 'PROD001', 'PROD010', 2),
        (2, 'PROD001', 'PROD011', 1),
        (3, 'PROD001', 'PROD012', 4),
        (4, 'PROD010', 'PROD020', 3),
        (5, 'PROD010', 'PROD021', 1),
        (6, 'PROD011', 'PROD022', 2),
    ]
    for b in bom:
        adapter.execute(f"INSERT INTO bill_of_materials VALUES ({b[0]}, '{b[1]}', '{b[2]}', {b[3]})")

    # Inventory
    for i in range(1, 31):
        prod_id = f"PROD{i:03d}"
        stock = random.randint(10, 500)
        reorder = random.randint(20, 100)
        adapter.execute(f"INSERT INTO inventory VALUES ('{prod_id}', {stock}, {reorder}, '2024-10-01')")

    # Shipping (for 200 orders)
    carriers = ['FedEx', 'UPS', 'USPS', 'DHL']
    methods = ['Standard', 'Express', 'Overnight']
    for i in range(1, 201):
        order_id = i
        carrier = random.choice(carriers)
        method = random.choice(methods)
        ship_date = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 300))).strftime('%Y-%m-%d')
        delivery_date = (datetime.strptime(ship_date, '%Y-%m-%d') + timedelta(days=random.randint(1, 7))).strftime('%Y-%m-%d')
        adapter.execute(f"INSERT INTO shipping VALUES ({i}, {order_id}, '{carrier}', '{method}', '{ship_date}', '{delivery_date}')")

    # Payments
    payment_methods = ['Credit Card', 'Debit Card', 'PayPal', 'Bank Transfer']
    for i in range(1, 301):
        order_id = i
        method = random.choice(payment_methods)
        status = random.choice(['completed', 'completed', 'completed', 'pending', 'failed'])
        date = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 300))).strftime('%Y-%m-%d')
        amount = round(20 + random.random() * 500, 2)
        adapter.execute(f"INSERT INTO payments VALUES ({i}, {order_id}, '{method}', '{status}', '{date}', {amount})")

    # Support Tickets
    for i in range(1, 101):
        customer_id = random.randint(1, 50)
        subject = f"Issue {i}"
        status = random.choice(['open', 'closed', 'closed', 'closed'])
        priority = random.choice(['low', 'medium', 'high'])
        created = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 300))).strftime('%Y-%m-%d %H:%M:%S')

        if status == 'closed':
            resolved = (datetime.strptime(created[:10], '%Y-%m-%d') + timedelta(hours=random.randint(1, 72))).strftime('%Y-%m-%d %H:%M:%S')
            hours = random.randint(1, 72)
            adapter.execute(f"INSERT INTO support_tickets VALUES ({i}, {customer_id}, '{subject}', '{status}', '{priority}', '{created}', '{resolved}', {hours})")
        else:
            adapter.execute(f"INSERT INTO support_tickets VALUES ({i}, {customer_id}, '{subject}', '{status}', '{priority}', '{created}', NULL, NULL)")

    # Customer Engagement
    for i in range(1, 51):
        customer_id = i
        last_login = (datetime(2024, 10, 1) + timedelta(days=random.randint(0, 60))).strftime('%Y-%m-%d')
        page_views = random.randint(10, 500)
        email_opens = random.randint(5, 50)
        email_clicks = random.randint(0, email_opens)
        adapter.execute(f"INSERT INTO customer_engagement VALUES ({i}, {customer_id}, '{last_login}', {page_views}, {email_opens}, {email_clicks})")

    # Marketing Touches
    channels = ['Email', 'Social', 'Search', 'Display', 'Referral', 'Direct']
    touch_id = 1
    for order_id in range(1, 201):
        customer_id = random.randint(1, 50)
        num_touches = random.randint(1, 5)

        base_date = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 300))
        for t in range(num_touches):
            channel = random.choice(channels)
            touch_time = (base_date - timedelta(days=num_touches - t, hours=random.randint(0, 23))).strftime('%Y-%m-%d %H:%M:%S')
            campaign = f"CAMP{random.randint(1, 10):03d}"
            adapter.execute(f"INSERT INTO marketing_touches VALUES ({touch_id}, {customer_id}, {order_id}, '{channel}', '{touch_time}', '{campaign}')")
            touch_id += 1


if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')
    sys.path.insert(0, 'src')

    from agentx import SQLExecutor, ExecutorConfig

    executor = SQLExecutor(ExecutorConfig(dialect="sqlite"))
    setup_enterprise_schema(executor)

    # Verify
    result = executor.process_query("SELECT COUNT(*) as cnt FROM sales_fact")
    print(f"Sales fact rows: {result.data[0]['cnt']}")

    result = executor.process_query("SELECT COUNT(*) as cnt FROM dim_customer")
    print(f"Customer dimension rows: {result.data[0]['cnt']}")

    result = executor.process_query("SELECT COUNT(*) as cnt FROM dim_date")
    print(f"Date dimension rows: {result.data[0]['cnt']}")

    result = executor.process_query("SELECT COUNT(*) as cnt FROM user_events")
    print(f"User events rows: {result.data[0]['cnt']}")

    # List all tables
    schema = executor.adapter.get_schema_snapshot()
    tables = [t.name if hasattr(t, 'name') else str(t) for t in schema.tables]
    print(f"\nTables created ({len(tables)}): {', '.join(sorted(tables))}")

    print("\nEnterprise schema setup complete!")
    executor.close()
