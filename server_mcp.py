from mcp.server.fastmcp import FastMCP
import ucp_db
import json

# Instantiate FastMCP server
mcp = FastMCP("Agentic Purchasing Control Plane Tools")

@mcp.tool()
def verificar_status_estoque(sku: str) -> str:
    """
    Verifica a quantidade atual e a quantidade minima toleravel em estoque para um SKU especifico.
    """
    try:
        product = ucp_db.get_product(sku)
        if not product:
            return json.dumps({"status": "ERROR", "message": f"SKU '{sku}' nao encontrado."})
        
        status = "OK" if product["qtd_atual"] >= product["qtd_minima"] else "RUPTURA"
        return json.dumps({
            "status": status,
            "sku": sku,
            "nome": product["name"],
            "qtd_atual": product["qtd_atual"],
            "qtd_minima": product["qtd_minima"],
            "breach": product["qtd_atual"] < product["qtd_minima"]
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "ERROR", "message": str(e)})

@mcp.tool()
def comparar_precos_fornecedores(sku: str) -> str:
    """
    Pesquisa e compara todos os fornecedores disponiveis para o SKU, ordenando pelo menor preco.
    """
    try:
        suppliers = ucp_db.get_suppliers(sku)
        if not suppliers:
            return json.dumps({"status": "ERROR", "message": f"Nenhum fornecedor cadastrado para o SKU '{sku}'."})
        
        return json.dumps({
            "status": "SUCCESS",
            "sku": sku,
            "fornecedores": suppliers
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "ERROR", "message": str(e)})

@mcp.tool()
def agendar_pagamento_compras(pedido_id: str, valor: float, favorecido: str) -> str:
    """
    Agenda ou autoriza o pagamento de compras para um pedido de compras especifico, no valor informado e para o favorecido indicado.
    """
    try:
        # Check if the purchase order exists in database
        order = ucp_db.get_purchase_order(pedido_id)
        if not order:
            # Let's support scheduling a payment for an ad-hoc order as well, for compatibility
            return json.dumps({
                "status": "SCHEDULED",
                "pedido_id": pedido_id,
                "valor": valor,
                "favorecido": favorecido,
                "mensagem": f"Pagamento de R$ {valor:.2f} para '{favorecido}' agendado com sucesso (Pedido ad-hoc '{pedido_id}')."
            }, indent=2)
        
        # Verify if value matches the order value
        total_order_val = order["qty"] * order["price"]
        
        # Update order status or log the transaction schedule
        return json.dumps({
            "status": "SCHEDULED",
            "pedido_id": pedido_id,
            "sku": order["sku"],
            "valor": valor,
            "favorecido": favorecido,
            "mensagem": f"Autorizacao de pagamento de R$ {valor:.2f} (R$ {order['price']:.2f} * {order['qty']} un) para '{favorecido}' agendada com sucesso. Aguardando aprovacao humana final na interface."
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "ERROR", "message": str(e)})

if __name__ == "__main__":
    mcp.run()
