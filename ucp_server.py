from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import ucp_db
import pix_exporter
import os
import sys
import io
import uuid

# Force UTF-8 encoding on standard output for Windows console compatibility
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Fallback for older python versions
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

app = FastAPI(title="Universal Control Plane & A2A Orchestrator")

# Enable CORS for convenience
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SSE Connection Pools
listeners = []

async def broadcast_event(event_type: str, data: dict):
    """Broadcasts an event to all connected SSE clients."""
    event_payload = {
        "type": event_type,
        "data": data
    }
    for queue in listeners:
        await queue.put(event_payload)

# Pydantic schemas
class LogMessage(BaseModel):
    message: str

class BreachNotification(BaseModel):
    sku: str
    current_qty: int
    min_qty: int

class CheckoutItem(BaseModel):
    sku: str
    quantidade: int

class CheckoutRequest(BaseModel):
    cliente_nome: str
    cliente_cpf: str
    cep_destino: str
    endereco_logradouro: str
    forma_pagamento: str
    items: list[CheckoutItem]

class PayRequest(BaseModel):
    id_pedido: str

@app.get("/")
def read_root():
    return FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html"))

@app.get("/static/app.js")
def read_js():
    return FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "app.js"))

@app.get("/static/images/{image_name}")
def read_image(image_name: str):
    image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "images", image_name)
    if os.path.exists(image_path):
        return FileResponse(image_path)
    raise HTTPException(status_code=404, detail="Imagem não encontrada")

@app.get("/api/products")
def get_products():
    return ucp_db.get_products()

@app.get("/api/purchases")
def get_purchases():
    return ucp_db.get_purchases()

@app.get("/api/pix/pending")
def get_pending_pix():
    conn = ucp_db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM purchases WHERE status = 'APPROVED' ORDER BY timestamp DESC")
    pending = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Enriquecer com as chaves Pix reais
    for tx in pending:
        pix_info = pix_exporter.SUPPLIER_PIX_KEYS.get(
            tx["supplier"], 
            {"key_type": "EVP", "key": "38a7c29b-e85d-4f1a-b6c8-912a3d4f7e5b"}
        )
        tx["chave_pix"] = pix_info["key"]
        tx["tipo_chave"] = pix_info["key_type"]
        
    return pending

@app.post("/api/pix/export")
async def export_pix():
    try:
        # Executar a exportação em lote
        payload = pix_exporter.export_pix_batch()
        if not payload:
            return {"status": "empty", "message": "Nenhum Pix pendente de envio."}
        
        # Notificar o Console via SSE
        await broadcast_event("log", {
            "message": f"🚀 [Lote-Pix] Lote '{payload['lote_id']}' de R$ {payload['valor_total_lote']:.2f} ({payload['total_transacoes']} transações) exportado com sucesso em exports/!"
        })
        
        # Notificar o dashboard para recarregar o estoque e a lista de Pix pendentes
        await broadcast_event("stock_update", ucp_db.get_products())
        await broadcast_event("pix_update", {})
        
        return {"status": "success", "batch_id": payload["lote_id"], "total": payload["valor_total_lote"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/a2a/log")
async def post_log(log: LogMessage):
    """Helper to receive log messages from other servers (like gRPC) and stream to UI."""
    await broadcast_event("log", {"message": log.message})
    return {"status": "success"}

async def run_purchasing_agent(sku: str, current_qty: int, min_qty: int):
    """
    Simulates the Purchasing Agent (woken up asynchronously by the Stock Agent).
    It queries the database (via MCP tools equivalent) to resolve the breach.
    """
    await asyncio.sleep(1.0)  # Add realistic agent processing lag
    
    await broadcast_event("log", {
        "message": f"🤖 [Agente-Compras] Agente de Compras despertado para o SKU {sku}. Iniciando análise de mercado..."
    })
    
    await asyncio.sleep(1.5)
    
    # 1. MCP Tool: comparar_precos_fornecedores
    await broadcast_event("log", {
        "message": f"🔍 [Agente-Compras] Executando ferramenta MCP 'comparar_precos_fornecedores' para o SKU {sku}..."
    })
    
    suppliers = ucp_db.get_suppliers(sku)
    if not suppliers:
        await broadcast_event("log", {
            "message": f"❌ [Agente-Compras] Falha ao encontrar fornecedores para o SKU {sku}!"
        })
        return
        
    await asyncio.sleep(1.0)
    
    # Log comparison details
    for s in suppliers:
        await broadcast_event("log", {
            "message": f"⚖️ [Ferramenta-MCP] Fornecedor avaliado: '{s['name']}' | Preço: R$ {s['price']:.2f} | Prazo: {s['delivery_days']} dias"
        })
        
    # 2. Decision logic: Cheapest supplier
    best_supplier = suppliers[0]  # Sorted by price ASC in get_suppliers
    await broadcast_event("log", {
        "message": f"💡 [Agente-Compras] Decisão: Selecionado '{best_supplier['name']}' como melhor fornecedor (Mais barato: R$ {best_supplier['price']:.2f})"
    })
    
    # 3. Calculate purchase volume: replenish enough to bring stock to min_qty * 2
    target_qty = (min_qty * 2) - current_qty
    if target_qty <= 0:
        target_qty = 10  # fallback quantity
        
    total_cost = target_qty * best_supplier["price"]
    
    await asyncio.sleep(1.0)
    
    # 4. MCP Tool: agendar_pagamento_compras
    # First, create the purchase in SQLite database (representing the pending invoice)
    order_id = ucp_db.create_purchase_order(sku, target_qty, best_supplier["price"], best_supplier["name"])
    
    await broadcast_event("log", {
        "message": f"💳 [Agente-Compras] Executando ferramenta MCP 'agendar_pagamento_compras' para a Ordem {order_id} | Total: R$ {total_cost:.2f}"
    })
    
    # Generate A2UI Action Card (payment authorization card)
    await asyncio.sleep(1.2)
    await broadcast_event("log", {
        "message": f"⚡ [A2UI] Card dinâmico de ação humana (Human-in-the-Loop) despachado para a Ordem {order_id}!"
    })
    
    # Notify UI about pending action
    product = ucp_db.get_product(sku)
    action_card = {
        "order_id": order_id,
        "sku": sku,
        "product_name": product["name"],
        "qty": target_qty,
        "price": best_supplier["price"],
        "total": total_cost,
        "supplier": best_supplier["name"],
        "delivery_days": best_supplier["delivery_days"]
    }
    await broadcast_event("purchase_pending", action_card)

@app.post("/api/a2a/trigger_purchase")
async def trigger_purchase(breach: BreachNotification, background_tasks: BackgroundTasks):
    """Triggered by the Stock Agent when quantity is lower than minimum."""
    background_tasks.add_task(run_purchasing_agent, breach.sku, breach.current_qty, breach.min_qty)
    return {"status": "purchasing_agent_woken"}

@app.post("/api/approve/{purchase_id}")
async def approve_purchase(purchase_id: str):
    """Endpoint called when the human operator clicks 'Approve' on the A2UI card."""
    order = ucp_db.get_purchase_order(purchase_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    success = ucp_db.approve_purchase_order(purchase_id)
    if not success:
        raise HTTPException(status_code=400, detail="Order could not be approved (already processed or invalid state)")
        
    await broadcast_event("log", {
        "message": f"✅ [Pagamento] Ordem {purchase_id} APROVADA pelo operador humano! Transação executada."
    })
    await broadcast_event("log", {
        "message": f"📦 [Estoque] Reabastecidas {order['qty']} unidade(s) do SKU {order['sku']} no estoque ativo."
    })
    
    # Broadcast updated products list to refresh active stock monitors in UI
    await broadcast_event("stock_update", ucp_db.get_products())
    return {"status": "approved"}

@app.post("/api/reject/{purchase_id}")
async def reject_purchase(purchase_id: str):
    """Endpoint called when the human operator clicks 'Reject' on the A2UI card."""
    order = ucp_db.get_purchase_order(purchase_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    success = ucp_db.reject_purchase_order(purchase_id)
    if not success:
        raise HTTPException(status_code=400, detail="Order could not be rejected")
        
    await broadcast_event("log", {
        "message": f"❌ [Pagamento] Ordem {purchase_id} REJEITADA pelo operador humano. Compra cancelada."
    })
    return {"status": "rejected"}

# ==========================================
# MÓDULOS DA VERSÃO 2 (E-COMMERCE & LOGÍSTICA)
# ==========================================

async def run_logistics_worker(id_pedido: str):
    """
    Worker assíncrono (BackgroundTask) acionado pós-pagamento.
    Calcula cubagem e peso total do pedido e gera a remessa de despacho.
    """
    await asyncio.sleep(1.5) # Lag de processamento realista do worker
    
    await broadcast_event("log", {
        "message": f"🤖 [Worker-Logística] Despertado para processar o despacho do pedido {id_pedido}."
    })
    
    pedido = ucp_db.get_pedido(id_pedido)
    if not pedido:
        await broadcast_event("log", {
            "message": f"❌ [Worker-Logística] Erro: Pedido {id_pedido} não encontrado!"
        })
        return
        
    await broadcast_event("log", {
        "message": f"⚖️ [Worker-Logística] Calculando atributos físicos para os itens do pedido..."
    })
    await asyncio.sleep(1.0)
    
    peso_total_kg = 0.0
    volume_cubagem_m3 = 0.0
    
    for item in pedido["items"]:
        # Recupera informações físicas direto da V1 via ucp_db
        prod = ucp_db.get_product(item["sku"])
        if prod:
            item_peso = prod["peso_kg"] * item["quantidade"]
            # Volume = (A * L * C) em cm / 1.000.000 (para m3) * quantidade
            item_volume = ((prod["altura_cm"] * prod["largura_cm"] * prod["comprimento_cm"]) / 1000000.0) * item["quantidade"]
            
            peso_total_kg += item_peso
            volume_cubagem_m3 += item_volume
            
            await broadcast_event("log", {
                "message": f"📦 [Worker-Logística] Item: {item['product_name']} | Peso: {item_peso:.3f} kg | Cubagem: {item_volume:.4f} m³"
            })
            
    # Limpar CEP (somente dígitos)
    cep_entrega_limpo = "".join(filter(str.isdigit, pedido["cep_destino"]))
    
    # Monta payload para transportadora
    payload_transportadora = {
        "id_pedido": pedido["id_pedido"],
        "cliente_nome": pedido["cliente_nome"],
        "cliente_documento": pedido["cliente_cpf"],
        "endereco_completo": f"{pedido['endereco_logradouro']}, CEP {pedido['cep_destino']}",
        "cep_entrega": cep_entrega_limpo,
        "peso_total_kg": round(peso_total_kg, 3),
        "volume_cubagem_m3": round(volume_cubagem_m3, 4)
    }
    
    # Salva arquivo de despacho na pasta exports/despacho/
    dir_despacho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports", "despacho")
    os.makedirs(dir_despacho, exist_ok=True)
    
    file_path = os.path.join(dir_despacho, f"DESPACHO-{pedido['id_pedido']}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload_transportadora, f, indent=2, ensure_ascii=False)
        
    await broadcast_event("log", {
        "message": f"🚚 [Worker-Logística] Arquivo de remessa gerado com sucesso: exports/despacho/DESPACHO-{pedido['id_pedido']}.json"
    })
    
    # Notifica a UI de que há atualizações analíticas disponíveis
    await broadcast_event("analytics_update", {})
    await broadcast_event("stock_update", ucp_db.get_products())

@app.get("/api/shipping/calculate")
def calculate_shipping(sku: str, qty: int, cep: str):
    """Calcula custo de frete e traz endereço com base no CEP e dimensões do produto."""
    product = ucp_db.get_product(sku)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
        
    # Peso e volume
    peso_total = product["peso_kg"] * qty
    volume_m3 = ((product["altura_cm"] * product["largura_cm"] * product["comprimento_cm"]) / 1000000.0) * qty
    
    # Roteamento básico fictício por faixa de CEP
    primeiro_digito = int(cep[0]) if cep and cep[0].isdigit() else 5
    frete_base = 15.0 + (primeiro_digito * 5.0)
    
    # Fórmula: frete_base + R$ 2.50 por kg + R$ 150.00 por m³ cubado
    custo_frete = frete_base + (peso_total * 2.5) + (volume_m3 * 150.0)
    
    # Endereços simulados divertidos por região de CEP
    if cep.startswith("0"):
        endereco = "Av. Paulista, 1000, Bela Vista - São Paulo / SP"
    elif cep.startswith("2"):
        endereco = "Av. Atlântica, 500, Copacabana - Rio de Janeiro / RJ"
    elif cep.startswith("3"):
        endereco = "Av. Afonso Pena, 1500, Centro - Belo Horizonte / MG"
    elif cep.startswith("8"):
        endereco = "Rua das Flores, 123, Centro - Curitiba / PR"
    else:
        endereco = "Rua Principal, 240, Setor Central - Brasília / DF"
        
    return {
        "sku": sku,
        "product_name": product["name"],
        "peso_total_kg": round(peso_total, 3),
        "volume_cubagem_m3": round(volume_m3, 4),
        "custo_frete": round(custo_frete, 2),
        "endereco_completo": endereco
    }

@app.post("/api/checkout")
async def post_checkout(req: CheckoutRequest):
    """Cria um pedido no status PENDING aplicando reserva de estoque atômica para todos os itens."""
    # 1. Tenta reservar estoque atômico para todos os itens
    # Se falhar para qualquer um, a transação não é consolidada
    reserved_items = []
    
    # Como SQLite é de arquivo único, faremos uma verificação sequencial simples.
    # Em caso de falha, nós devolvemos o estoque reservado dos itens anteriores (rollbacks de estoque manuais!)
    for item in req.items:
        success = ucp_db.reserve_stock_atomic(item.sku, item.quantidade)
        if not success:
            # Rollback de estoque manual para os itens que já tinham sido reservados
            for r_sku, r_qty in reserved_items:
                ucp_db.update_product_qty(r_sku, r_qty)
            raise HTTPException(
                status_code=400, 
                detail=f"Estoque insuficiente para o produto SKU {item.sku}!"
            )
        reserved_items.append((item.sku, item.quantidade))
        
    # 2. Calcula valores dos produtos e frete
    valor_produtos = 0.0
    valor_frete = 0.0
    
    db_items = []
    for item in req.items:
        prod = ucp_db.get_product(item.sku)
        preco_unitario = 0.0
        
        # Obter o preço do primeiro fornecedor (ou default)
        suppliers = ucp_db.get_suppliers(item.sku)
        if suppliers:
            preco_unitario = suppliers[0]["price"] * 1.25 # Margem de e-commerce de 25% sobre cotação
        else:
            preco_unitario = 500.00 # fallback
            
        valor_produtos += preco_unitario * item.quantidade
        
        # Calcular frete unitário
        peso_total = prod["peso_kg"] * item.quantidade
        volume_m3 = ((prod["altura_cm"] * prod["largura_cm"] * prod["comprimento_cm"]) / 1000000.0) * item.quantidade
        primeiro_digito = int(req.cep_destino[0]) if req.cep_destino and req.cep_destino[0].isdigit() else 5
        frete_base = 15.0 + (primeiro_digito * 5.0)
        valor_frete += frete_base + (peso_total * 2.5) + (volume_m3 * 150.0)
        
        db_items.append({
            "sku": item.sku,
            "quantidade": item.quantidade,
            "preco_unitario": preco_unitario
        })
        
    valor_total = valor_produtos + valor_frete
    id_pedido = "V2-" + str(uuid.uuid4())[:8].upper()
    
    # 3. Grava no banco como PENDING
    success = ucp_db.create_pedido(
        id_pedido, "PENDING", valor_produtos, valor_frete, valor_total,
        req.cliente_nome, req.cliente_cpf, req.cep_destino, req.endereco_logradouro,
        req.forma_pagamento, db_items
    )
    
    if not success:
        # Devolve estoque se falhar gravação
        for r_sku, r_qty in reserved_items:
            ucp_db.update_product_qty(r_sku, r_qty)
        raise HTTPException(status_code=500, detail="Erro interno ao gravar pedido.")
        
    await broadcast_event("log", {
        "message": f"🛒 [Checkout] Novo pedido {id_pedido} criado (Aguardando Pagamento) | Total: R$ {valor_total:.2f}"
    })
    
    await broadcast_event("stock_update", ucp_db.get_products())
    return {
        "id_pedido": id_pedido,
        "valor_produtos": round(valor_produtos, 2),
        "valor_frete": round(valor_frete, 2),
        "valor_total": round(valor_total, 2),
        "status": "PENDING"
    }

@app.post("/api/checkout/pay")
async def pay_checkout(req: PayRequest, background_tasks: BackgroundTasks):
    """Processa o pagamento simulado do gateway multifase."""
    pedido = ucp_db.get_pedido(req.id_pedido)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
        
    if pedido["status_pedido"] != "PENDING":
        raise HTTPException(status_code=400, detail="Este pedido já foi pago ou cancelado.")
        
    await broadcast_event("log", {
        "message": f"💳 [Gateway] Processando pagamento para o Pedido {req.id_pedido} ({pedido['forma_pagamento']})..."
    })
    
    # Simula anti-fraude síncrono para Cartão ou processamento curto para Pix
    if pedido["forma_pagamento"] == "CREDIT_CARD":
        await asyncio.sleep(1.0)
        # Simula score simples
        score_cpf = len(pedido["cliente_cpf"])
        if score_cpf < 11:
            # CPF inválido, cancela
            ucp_db.update_pedido_status(req.id_pedido, "CANCELLED")
            # Devolve estoque
            for item in pedido["items"]:
                ucp_db.update_product_qty(item["sku"], item["quantidade"])
            await broadcast_event("log", {
                "message": f"❌ [Anti-Fraude] Pedido {req.id_pedido} REJEITADO devido a inconsistência de CPF. Pedido Cancelado."
            })
            await broadcast_event("stock_update", ucp_db.get_products())
            return {"status": "fraud_rejected", "message": "Pagamento recusado por suspeita de fraude."}
            
    elif pedido["forma_pagamento"] == "PIX":
        await asyncio.sleep(0.5)
        
    # Aprovação
    ucp_db.update_pedido_status(req.id_pedido, "PAID")
    
    await broadcast_event("log", {
        "message": f"✅ [Gateway] Pagamento do Pedido {req.id_pedido} CONFIRMADO com sucesso!"
    })
    
    # Agenda o worker de logística
    background_tasks.add_task(run_logistics_worker, req.id_pedido)
    
    return {"status": "PAID", "message": "Pagamento aprovado com sucesso!"}

@app.get("/api/analytics/summary")
def get_analytics():
    """Retorna os relatórios analíticos ricos usando Window Functions."""
    return ucp_db.get_analytics_summary()

@app.get("/api/events")
async def sse_events():
    """SSE endpoint for broadcasting events in real-time to the dashboard."""
    async def sse_generator():
        queue = asyncio.Queue()
        listeners.append(queue)
        
        # Stream initial stock status upon connection
        initial_stock = ucp_db.get_products()
        yield f"event: stock_update\ndata: {json.dumps(initial_stock)}\n\n"
        
        try:
            while True:
                event = await queue.get()
                yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            listeners.remove(queue)

    return StreamingResponse(sse_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    # Initialize the database just in case
    ucp_db.init_db()
    print("🚀 Iniciando Servidor FastAPI UCP em http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
