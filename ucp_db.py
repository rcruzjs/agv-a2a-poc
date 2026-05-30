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

    # Create Pix Batches Table (V4 Control)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pix_batches (
        batch_id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        total_transactions INTEGER NOT NULL,
        total_amount REAL NOT NULL,
        sent_to_bank INTEGER DEFAULT 0, -- 0 = Pendente, 1 = Enviado
        sent_timestamp TEXT
    )
    """)

    # Migration: Add batch_id to purchases
    try:
        cursor.execute("ALTER TABLE purchases ADD COLUMN batch_id TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

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

def get_operations_summary():
    """
    Computes B2B & B2C consolidated operations, detailed Brazilian hardware taxes,
    unified payment queue, and logistics tracking for V4.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Volume flows
    # B2C units sold
    cursor.execute("""
        SELECT TOTAL(quantidade) as b2c_units_sold 
        FROM itens_pedido ip
        JOIN pedidos p ON ip.id_pedido = p.id_pedido
        WHERE p.status_pedido = 'PAID'
    """)
    b2c_units = cursor.fetchone()["b2c_units_sold"] or 0
    
    # B2B units bought
    cursor.execute("""
        SELECT TOTAL(qty) as b2b_units_bought 
        FROM purchases 
        WHERE status IN ('APPROVED', 'PROCESSED_PIX')
    """)
    b2b_units = cursor.fetchone()["b2b_units_bought"] or 0
    
    # 2. Financials & Taxes
    # B2C Gross product revenue & shipping revenue
    cursor.execute("""
        SELECT 
            TOTAL(valor_produtos) as b2c_product_revenue,
            TOTAL(valor_frete) as b2c_shipping_revenue,
            TOTAL(valor_total) as b2c_gross_revenue
        FROM pedidos
        WHERE status_pedido = 'PAID'
    """)
    b2c_fin = cursor.fetchone()
    b2c_prod_rev = b2c_fin["b2c_product_revenue"] or 0.0
    b2c_freight_rev = b2c_fin["b2c_shipping_revenue"] or 0.0
    b2c_gross_rev = b2c_fin["b2c_gross_revenue"] or 0.0
    
    # B2B Procurement Cost
    cursor.execute("""
        SELECT TOTAL(qty * price) as b2b_procurement_cost
        FROM purchases
        WHERE status IN ('APPROVED', 'PROCESSED_PIX')
    """)
    b2b_cost = cursor.fetchone()["b2b_procurement_cost"] or 0.0
    
    # Brazilian hardware tax engineering:
    # B2C Tax Deductions: 18% ICMS + 10% IPI on B2C products value (total 28% tax on sales)
    tax_b2c_icms = b2c_prod_rev * 0.18
    tax_b2c_ipi = b2c_prod_rev * 0.10
    total_tax_b2c = tax_b2c_icms + tax_b2c_ipi
    
    # B2B Tax Credits: 12% ICMS credit recovered from procurement cost
    tax_b2b_credit = b2b_cost * 0.12
    
    # Net tax balance owed to the tax authority
    tax_balance_owed = max(0.0, total_tax_b2c - tax_b2b_credit)
    
    # Operational Margins
    # Net product profit = (B2C product revenue - B2C taxes) - (B2B cost - B2B credits)
    # Net overall profit = Net product profit + B2C shipping revenue (assuming shipping runs at break-even or is pass-through)
    net_product_profit = (b2c_prod_rev - total_tax_b2c) - (b2b_cost - tax_b2b_credit)
    net_overall_profit = net_product_profit + b2c_freight_rev
    
    profit_margin_pct = (net_overall_profit / b2c_gross_rev * 100) if b2c_gross_rev > 0 else 0.0
    
    # 3. Unified bank payment liquidations queue (merging B2B and B2C)
    # We retrieve B2C payments
    cursor.execute("""
        SELECT 
            'B2C' as type,
            id_pedido as id,
            cliente_nome as party,
            forma_pagamento as method,
            valor_total as amount,
            status_pedido as raw_status,
            data_criacao as timestamp
        FROM pedidos
        ORDER BY data_criacao DESC LIMIT 30
    """)
    b2c_payments = [dict(row) for row in cursor.fetchall()]
    
    # We retrieve B2B payments
    cursor.execute("""
        SELECT 
            'B2B' as type,
            id as id,
            supplier as party,
            'PIX' as method,
            (qty * price) as amount,
            status as raw_status,
            timestamp as timestamp
        FROM purchases
        ORDER BY timestamp DESC LIMIT 30
    """)
    b2b_payments = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    # Merge and format payment status
    unified_queue = []
    
    for p in b2c_payments:
        # Determine status
        bank_status = ""
        status_color = ""
        
        if p["raw_status"] == "PAID":
            if p["method"] == "PIX":
                bank_status = "Liquidado via Pix BC"
                status_color = "var(--color-emerald)"
            elif p["method"] == "CREDIT_CARD":
                bank_status = "Autorizado pelo Emissor"
                status_color = "var(--color-emerald)"
            else:
                bank_status = "Compensado no Banco"
                status_color = "var(--color-emerald)"
        elif p["raw_status"] == "PENDING":
            if p["method"] == "PIX":
                bank_status = "Aguardando Pix Copia e Cola"
                status_color = "var(--color-amber)"
            elif p["method"] == "CREDIT_CARD":
                bank_status = "Em Análise Anti-Fraude"
                status_color = "var(--color-cyan)"
            else:
                bank_status = "Aguardando Boleto Bancário"
                status_color = "var(--color-cyan)"
        else: # CANCELLED
            bank_status = "Recusado / Estornado"
            status_color = "var(--color-rose)"
            
        unified_queue.append({
            "type": "Venda (B2C)",
            "id": p["id"],
            "party": p["party"],
            "method": p["method"],
            "amount": p["amount"],
            "bank_status": bank_status,
            "status_color": status_color,
            "timestamp": p["timestamp"]
        })
        
    for p in b2b_payments:
        bank_status = ""
        status_color = ""
        
        if p["raw_status"] == "PROCESSED_PIX":
            bank_status = "Remessa Pix Liquidada"
            status_color = "var(--color-emerald)"
        elif p["raw_status"] == "APPROVED":
            bank_status = "Fila de Envio Pix"
            status_color = "var(--color-amber)"
        elif p["raw_status"] == "REJECTED":
            bank_status = "Cancelado pelo Operador"
            status_color = "var(--color-rose)"
        else: # PENDING
            bank_status = "Aguardando Aprovação IA"
            status_color = "var(--color-cyan)"
            
        unified_queue.append({
            "type": "Compra (B2B)",
            "id": p["id"],
            "party": p["party"],
            "method": p["method"],
            "amount": p["amount"],
            "bank_status": bank_status,
            "status_color": status_color,
            "timestamp": p["timestamp"]
        })
        
    # Sort unified queue DESC by timestamp
    unified_queue.sort(key=lambda x: x["timestamp"], reverse=True)
    unified_queue = unified_queue[:15] # Top 15 transactions
    
    return {
        "metrics": {
            "b2c_units_sold": int(b2c_units),
            "b2b_units_bought": int(b2b_units),
            "b2c_product_revenue": b2c_prod_rev,
            "b2c_shipping_revenue": b2c_freight_rev,
            "b2c_gross_revenue": b2c_gross_rev,
            "b2b_procurement_cost": b2b_cost,
            "taxes": {
                "tax_b2c_icms": tax_b2c_icms,
                "tax_b2c_ipi": tax_b2c_ipi,
                "total_tax_b2c": total_tax_b2c,
                "tax_b2b_credit": tax_b2b_credit,
                "tax_balance_owed": tax_balance_owed
            },
            "net_product_profit": net_product_profit,
            "net_overall_profit": net_overall_profit,
            "profit_margin_pct": profit_margin_pct
        },
        "unified_queue": unified_queue
    }

def create_pix_batch(batch_id, total_transactions, total_amount):
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    cursor.execute(
        """
        INSERT INTO pix_batches (batch_id, timestamp, total_transactions, total_amount, sent_to_bank)
        VALUES (?, ?, ?, ?, 0)
        """,
        (batch_id, timestamp, total_transactions, total_amount)
    )
    conn.commit()
    conn.close()

def get_pix_batches():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pix_batches ORDER BY timestamp DESC")
    batches = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return batches

def get_batch_details(batch_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM purchases WHERE batch_id = ? ORDER BY timestamp DESC", (batch_id,))
    purchases = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return purchases

def mark_batch_sent(batch_id):
    conn = get_connection()
    cursor = conn.cursor()
    sent_timestamp = datetime.datetime.now().isoformat()
    cursor.execute(
        "UPDATE pix_batches SET sent_to_bank = 1, sent_timestamp = ? WHERE batch_id = ?",
        (sent_timestamp, batch_id)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

if __name__ == "__main__":
    init_db()
