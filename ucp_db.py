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

    # Create Products Table (including V2 physical dimensions)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        sku TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        qtd_atual INTEGER NOT NULL,
        qtd_minima INTEGER NOT NULL,
        peso_kg REAL DEFAULT 0.0,
        altura_cm REAL DEFAULT 0.0,
        largura_cm REAL DEFAULT 0.0,
        comprimento_cm REAL DEFAULT 0.0
    )
    """)

    # Dynamic migration for V2 physical columns in products table (if it already existed)
    for col in ["peso_kg", "altura_cm", "largura_cm", "comprimento_cm"]:
        try:
            cursor.execute(f"ALTER TABLE products ADD COLUMN {col} REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass  # Column already exists

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

    # Create Pedidos Table (V2 Checkout)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pedidos (
        id_pedido TEXT PRIMARY KEY,
        data_criacao TEXT NOT NULL,
        status_pedido TEXT NOT NULL, -- PENDING, PAID, CANCELLED
        valor_produtos REAL NOT NULL,
        valor_frete REAL NOT NULL,
        valor_total REAL NOT NULL,
        cliente_nome TEXT NOT NULL,
        cliente_cpf TEXT NOT NULL,
        cep_destino TEXT NOT NULL,
        endereco_logradouro TEXT NOT NULL,
        forma_pagamento TEXT NOT NULL -- PIX, CREDIT_CARD, BOLETO
    )
    """)

    # Create Itens Pedido Table (V2 checkout items)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS itens_pedido (
        id_item_pedido TEXT PRIMARY KEY,
        id_pedido TEXT NOT NULL,
        sku TEXT NOT NULL,
        quantidade INTEGER NOT NULL,
        preco_unitario REAL NOT NULL,
        FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido),
        FOREIGN KEY (sku) REFERENCES products(sku)
    )
    """)

    # Check if we already have seeded data
    cursor.execute("SELECT COUNT(*) as count FROM products")
    if cursor.fetchone()["count"] == 0:
        # Seed Products
        products = [
            ("SKU-001", "SSD NVMe 1TB High-Speed", 15, 10, 0.08, 0.22, 2.20, 8.00),
            ("SKU-002", "Memória RAM 16GB DDR5 4800MHz", 8, 12, 0.05, 3.12, 13.30, 0.70),  # Already breached!
            ("SKU-003", "Processador Intel Core i7 13700K", 5, 5, 0.09, 4.50, 3.75, 3.75),
            ("SKU-004", "Placa de Vídeo RTX 4060 Ti 8GB", 10, 6, 1.20, 12.00, 24.00, 4.00)
        ]
        cursor.executemany("INSERT INTO products (sku, name, qtd_atual, qtd_minima, peso_kg, altura_cm, largura_cm, comprimento_cm) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", products)

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
        # DB already seeded, update realistic dimensions to existing products
        products_updates = [
            (0.08, 0.22, 2.20, 8.00, "SKU-001"),
            (0.05, 3.12, 13.30, 0.70, "SKU-002"),
            (0.09, 4.50, 3.75, 3.75, "SKU-003"),
            (1.20, 12.00, 24.00, 4.00, "SKU-004")
        ]
        cursor.executemany(
            "UPDATE products SET peso_kg = ?, altura_cm = ?, largura_cm = ?, comprimento_cm = ? WHERE sku = ?",
            products_updates
        )
        conn.commit()
        print("Database already initialized. Migrations and measurements verified.")

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
def reserve_stock_atomic(sku, qty):
    """
    Attempts to atomically reserve/decrement stock for a given SKU.
    Returns True if reservation was successful, False otherwise (Race Condition protection).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Atomic update check
    cursor.execute(
        "UPDATE products SET qtd_atual = qtd_atual - ? WHERE sku = ? AND qtd_atual >= ?",
        (qty, sku, qty)
    )
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def create_pedido(id_pedido, status, valor_produtos, valor_frete, valor_total, cliente_nome, cliente_cpf, cep, endereco, forma_pagamento, items):
    """
    Creates a new order and its items in a transaction.
    'items' is a list of dicts: [{'sku': '...', 'quantidade': X, 'preco_unitario': Y}]
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        data_criacao = datetime.datetime.now().isoformat()
        
        # Insert main order
        cursor.execute(
            """
            INSERT INTO pedidos (
                id_pedido, data_criacao, status_pedido, valor_produtos, valor_frete, 
                valor_total, cliente_nome, cliente_cpf, cep_destino, endereco_logradouro, forma_pagamento
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (id_pedido, data_criacao, status, valor_produtos, valor_frete, 
             valor_total, cliente_nome, cliente_cpf, cep, endereco, forma_pagamento)
        )
        
        # Insert items
        for item in items:
            id_item = "ITEM-" + str(uuid.uuid4())[:8].upper()
            cursor.execute(
                """
                INSERT INTO itens_pedido (id_item_pedido, id_pedido, sku, quantidade, preco_unitario)
                VALUES (?, ?, ?, ?, ?)
                """,
                (id_item, id_pedido, item["sku"], item["quantidade"], item["preco_unitario"])
            )
            
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error creating order in DB: {e}")
        return False
    finally:
        conn.close()

def update_pedido_status(id_pedido, new_status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE pedidos SET status_pedido = ? WHERE id_pedido = ?", (new_status, id_pedido))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def get_pedido(id_pedido):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pedidos WHERE id_pedido = ?", (id_pedido,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    
    pedido = dict(row)
    # Get items
    cursor.execute(
        "SELECT ip.*, p.name as product_name FROM itens_pedido ip JOIN products p ON ip.sku = p.sku WHERE ip.id_pedido = ?", 
        (id_pedido,)
    )
    pedido["items"] = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return pedido

def get_pedidos():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pedidos ORDER BY data_criacao DESC")
    pedidos = [dict(row) for row in cursor.fetchall()]
    for p in pedidos:
        cursor.execute(
            "SELECT ip.*, p.name as product_name FROM itens_pedido ip JOIN products p ON ip.sku = p.sku WHERE ip.id_pedido = ?", 
            (p["id_pedido"],)
        )
        p["items"] = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return pedidos

def get_analytics_summary():
    """
    Computes business and inventory metrics using advanced SQL aggregations and Window Functions.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Total faturamento, ticket médio, total pedidos
    cursor.execute("""
        SELECT 
            COUNT(*) as total_pedidos,
            SUM(CASE WHEN status_pedido = 'PAID' THEN 1 ELSE 0 END) as total_pagos,
            TOTAL(CASE WHEN status_pedido = 'PAID' THEN valor_total ELSE 0 END) as faturamento_total,
            AVG(CASE WHEN status_pedido = 'PAID' THEN valor_total ELSE NULL END) as ticket_medio
        FROM pedidos
    """)
    res = cursor.fetchone()
    total_pedidos = res["total_pedidos"] or 0
    total_pagos = res["total_pagos"] or 0
    faturamento_total = res["faturamento_total"] or 0.0
    ticket_medio = res["ticket_medio"] or 0.0
    
    taxa_conversao = (total_pagos / total_pedidos * 100) if total_pedidos > 0 else 0.0
    
    # 2. Faturamento acumulado diário usando Window Functions!
    cursor.execute("""
        SELECT 
            data_dia,
            valor_dia,
            SUM(valor_dia) OVER (ORDER BY data_dia ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as faturamento_acumulado
        FROM (
            SELECT 
                SUBSTR(data_criacao, 1, 10) as data_dia,
                SUM(valor_total) as valor_dia
            FROM pedidos
            WHERE status_pedido = 'PAID'
            GROUP BY SUBSTR(data_criacao, 1, 10)
        )
        ORDER BY data_dia ASC
    """)
    daily_revenue = [dict(row) for row in cursor.fetchall()]
    
    # 3. Métricas de Inventário: Giro de Estoque e Posição Geral
    cursor.execute("""
        SELECT 
            p.sku,
            p.name,
            p.qtd_atual,
            p.qtd_minima,
            p.peso_kg,
            p.altura_cm,
            p.largura_cm,
            p.comprimento_cm,
            TOTAL(CASE WHEN pe.status_pedido = 'PAID' THEN ip.quantidade ELSE 0 END) as total_vendido
        FROM products p
        LEFT JOIN itens_pedido ip ON p.sku = ip.sku
        LEFT JOIN pedidos pe ON ip.id_pedido = pe.id_pedido
        GROUP BY p.sku
    """)
    inventory_metrics = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "kpis": {
            "faturamento_total": faturamento_total,
            "ticket_medio": ticket_medio,
            "taxa_conversao": taxa_conversao,
            "total_pedidos": total_pedidos,
            "total_pagos": total_pagos
        },
        "daily_revenue": daily_revenue,
        "inventory_metrics": inventory_metrics
    }

if __name__ == "__main__":
    init_db()
