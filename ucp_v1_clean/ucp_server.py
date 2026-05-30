from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import os
import sys
import io
import uuid
import ucp_db
import pix_exporter

# Force UTF-8 encoding on standard output for Windows console compatibility
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Fallback for older python versions
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

app = FastAPI(title="Universal Control Plane V1 Clean - B2B Cockpit & A2A PoC")

# Enable CORS
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

@app.get("/")
def read_root():
    return FileResponse(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

@app.get("/static/app.js")
def read_js():
    return FileResponse(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "app.js"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

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
    
    # Enrich with supplier Pix keys
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
        # Export batched purchases
        payload = pix_exporter.export_pix_batch()
        if not payload:
            return {"status": "empty", "message": "Nenhum Pix pendente de envio."}
        
        # Notify via SSE
        await broadcast_event("log", {
            "message": f"🚀 [Lote-Pix] Lote '{payload['lote_id']}' de R$ {payload['valor_total_lote']:.2f} ({payload['total_transacoes']} transações) exportado com sucesso em exports/!"
        })
        
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

@app.post("/api/stock/broadcast")
async def post_stock_broadcast():
    """Broadcasts current stock levels to all SSE clients."""
    await broadcast_event("stock_update", ucp_db.get_products())
    return {"status": "success"}

async def run_purchasing_agent(sku: str, current_qty: int, min_qty: int):
    """
    Simulates the Purchasing Agent (woken up asynchronously by the Stock Agent).
    It queries the database to select the best supplier and dispatch an action card.
    """
    await asyncio.sleep(1.0)
    
    await broadcast_event("log", {
        "message": f"🤖 [Agente-Compras] Agente de Compras despertado para o SKU {sku}. Iniciando análise de mercado..."
    })
    
    await asyncio.sleep(1.5)
    
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
    
    # Log supplier quotes
    for s in suppliers:
        await broadcast_event("log", {
            "message": f"⚖️ [Ferramenta-MCP] Fornecedor avaliado: '{s['name']}' | Preço: R$ {s['price']:.2f} | Prazo: {s['delivery_days']} dias"
        })
        
    # Decision logic: choose cheapest
    best_supplier = suppliers[0]
    await broadcast_event("log", {
        "message": f"💡 [Agente-Compras] Decisão: Selecionado '{best_supplier['name']}' como melhor fornecedor (Mais barato: R$ {best_supplier['price']:.2f})"
    })
    
    # Replenish to bring stock to min_qty * 2
    target_qty = (min_qty * 2) - current_qty
    if target_qty <= 0:
        target_qty = 10
        
    total_cost = target_qty * best_supplier["price"]
    
    await asyncio.sleep(1.0)
    
    # Create PO in SQLite
    order_id = ucp_db.create_purchase_order(sku, target_qty, best_supplier["price"], best_supplier["name"])
    
    await broadcast_event("log", {
        "message": f"💳 [Agente-Compras] Executando ferramenta MCP 'agendar_pagamento_compras' para a Ordem {order_id} | Total: R$ {total_cost:.2f}"
    })
    
    await asyncio.sleep(1.2)
    await broadcast_event("log", {
        "message": f"⚡ [A2UI] Card dinâmico de ação humana (Human-in-the-Loop) despachado para a Ordem {order_id}!"
    })
    
    # Dispatch action card to UI
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
    """Called when operator clicks 'Approve' on the A2UI card."""
    order = ucp_db.get_purchase_order(purchase_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    success = ucp_db.approve_purchase_order(purchase_id)
    if not success:
        raise HTTPException(status_code=400, detail="Order could not be approved")
        
    await broadcast_event("log", {
        "message": f"✅ [Pagamento] Ordem {purchase_id} APROVADA pelo operador humano! Transação executada."
    })
    await broadcast_event("log", {
        "message": f"📦 [Estoque] Reabastecidas {order['qty']} unidade(s) do SKU {order['sku']} no estoque ativo."
    })
    
    await broadcast_event("stock_update", ucp_db.get_products())
    return {"status": "approved"}

@app.post("/api/reject/{purchase_id}")
async def reject_purchase(purchase_id: str):
    """Called when operator clicks 'Reject' on the A2UI card."""
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
    # Initialize the database
    ucp_db.init_db()
    print("🚀 Iniciando Servidor FastAPI UCP V1 Clean em http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
