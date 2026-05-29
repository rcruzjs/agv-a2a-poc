import sqlite3
import os
import uuid
import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ucp_database.db")

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Create Products Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        sku TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        qtd_atual INTEGER NOT NULL,
        qtd_minima INTEGER NOT NULL
    )
    """)

    # Create Suppliers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        sku TEXT NOT NULL,
        price REAL NOT NULL,
        delivery_days INTEGER NOT NULL,
        FOREIGN KEY (sku) REFERENCES products (sku)
    )
    """)

    # Create Purchase Orders Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id TEXT PRIMARY KEY,
        sku TEXT NOT NULL,
        qty INTEGER NOT NULL,
        price REAL NOT NULL,
        supplier TEXT NOT NULL,
        status TEXT NOT NULL, -- PENDING, APPROVED, REJECTED
        timestamp TEXT NOT NULL,
        FOREIGN KEY (sku) REFERENCES products (sku)
    )
    """)

    # Check if we already have seeded data
    cursor.execute("SELECT COUNT(*) as count FROM products")
    if cursor.fetchone()["count"] == 0:
        # Seed Products
        products = [
            ("SKU-001", "SSD NVMe 1TB High-Speed", 15, 10),
            ("SKU-002", "Memória RAM 16GB DDR5 4800MHz", 8, 12),  # Already breached!
            ("SKU-003", "Processador Intel Core i7 13700K", 5, 5),
            ("SKU-004", "Placa de Vídeo RTX 4060 Ti 8GB", 10, 6)
        ]
        cursor.executemany("INSERT INTO products (sku, name, qtd_atual, qtd_minima) VALUES (?, ?, ?, ?)", products)

        # Seed Suppliers
        suppliers = [
            # SSD NVMe 1TB
            ("Fornecedor Global Tech", "SKU-001", 350.00, 2),
            ("Mega Distribuidora", "SKU-001", 340.00, 5),
            ("Importadora Express", "SKU-001", 380.00, 1),
            
            # RAM 16GB DDR5
            ("Fornecedor Global Tech", "SKU-002", 290.00, 3),
            ("Mega Distribuidora", "SKU-002", 280.00, 6),
            ("Importadora Express", "SKU-002", 310.00, 2),
            
            # Core i7
            ("Fornecedor Global Tech", "SKU-003", 1500.00, 4),
            ("Mega Distribuidora", "SKU-003", 1450.00, 8),
            ("Importadora Express", "SKU-003", 1600.00, 2),

            # RTX 4060 Ti
            ("Fornecedor Global Tech", "SKU-004", 2200.00, 3),
            ("Mega Distribuidora", "SKU-004", 2150.00, 7),
            ("Importadora Express", "SKU-004", 2350.00, 2)
        ]
        cursor.executemany("INSERT INTO suppliers (name, sku, price, delivery_days) VALUES (?, ?, ?, ?)", suppliers)
        
        conn.commit()
        print("Database initialized and seeded successfully.")
    else:
        print("Database already initialized.")

    conn.close()

def get_products():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return products

def get_product(sku):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE sku = ?", (sku,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_product_qty(sku, qty_change):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT qtd_atual FROM products WHERE sku = ?", (sku,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"SKU {sku} not found.")
    
    new_qty = max(0, row["qtd_atual"] + qty_change)
    cursor.execute("UPDATE products SET qtd_atual = ? WHERE sku = ?", (new_qty, sku))
    conn.commit()
    conn.close()
    return new_qty

def get_suppliers(sku):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM suppliers WHERE sku = ? ORDER BY price ASC", (sku,))
    suppliers = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return suppliers

def create_purchase_order(sku, qty, price, supplier_name):
    conn = get_connection()
    cursor = conn.cursor()
    order_id = "PO-" + str(uuid.uuid4())[:8].upper()
    timestamp = datetime.datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO purchases (id, sku, qty, price, supplier, status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (order_id, sku, qty, price, supplier_name, "PENDING", timestamp)
    )
    conn.commit()
    conn.close()
    return order_id

def get_purchase_order(order_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM purchases WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def approve_purchase_order(order_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM purchases WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    
    order = dict(row)
    if order["status"] != "PENDING":
        conn.close()
        return False
    
    # Update status to APPROVED
    cursor.execute("UPDATE purchases SET status = 'APPROVED' WHERE id = ?", (order_id,))
    # Replenish stock
    cursor.execute("SELECT qtd_atual FROM products WHERE sku = ?", (order["sku"],))
    prod_row = cursor.fetchone()
    if prod_row:
        new_qty = prod_row["qtd_atual"] + order["qty"]
        cursor.execute("UPDATE products SET qtd_atual = ? WHERE sku = ?", (new_qty, order["sku"]))
    
    conn.commit()
    conn.close()
    return True

def reject_purchase_order(order_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM purchases WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    if not row or row["status"] != "PENDING":
        conn.close()
        return False
    
    cursor.execute("UPDATE purchases SET status = 'REJECTED' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    return True

def get_purchases():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM purchases ORDER BY timestamp DESC")
    purchases = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return purchases

if __name__ == "__main__":
    init_db()
