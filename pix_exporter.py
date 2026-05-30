import sqlite3
import csv
import json
import os
import datetime
import ucp_db
import sys
import io

# Force UTF-8 encoding on standard output for Windows console compatibility
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Fallback for older python versions
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ucp_database.db")
EXPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")

# Banco de dados simulado de chaves Pix dos fornecedores
SUPPLIER_PIX_KEYS = {
    "Mega Distribuidora": {"key_type": "CNPJ", "key": "12.345.678/0001-99"},
    "Fornecedor Global Tech": {"key_type": "CNPJ", "key": "98.765.432/0001-88"},
    "Importadora Express": {"key_type": "EMAIL", "key": "financeiro@importadoraexpress.com"}
}

def export_pix_batch():
    # 1. Cria diretório de exportação se não existir
    if not os.path.exists(EXPORTS_DIR):
        os.makedirs(EXPORTS_DIR)
        
    conn = ucp_db.get_connection()
    cursor = conn.cursor()
    
    # 2. Busca todas as compras autorizadas (APPROVED) que ainda não foram pagas
    cursor.execute("SELECT * FROM purchases WHERE status = 'APPROVED'")
    approved_purchases = [dict(row) for row in cursor.fetchall()]
    
    if not approved_purchases:
        print("ℹ️ Nenhum pedido autorizado pendente de pagamento Pix encontrado.")
        conn.close()
        return None
        
    batch_id = "BATCH-PIX-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_file_path = os.path.join(EXPORTS_DIR, f"{batch_id}.csv")
    json_file_path = os.path.join(EXPORTS_DIR, f"{batch_id}.json")
    
    pix_transactions = []
    
    # 3. Processa cada pedido aprovado estruturando os dados de pagamento
    for order in approved_purchases:
        supplier = order["supplier"]
        # Resgata a chave Pix cadastrada ou gera uma padrão baseada no nome do fornecedor
        pix_info = SUPPLIER_PIX_KEYS.get(
            supplier, 
            {"key_type": "EVP", "key": "38a7c29b-e85d-4f1a-b6c8-912a3d4f7e5b"} # Chave aleatória
        )
        
        total_value = order["qty"] * order["price"]
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        transaction = {
            "id_pedido": order["id"],
            "sku": order["sku"],
            "favorecido": supplier,
            "chave_pix": pix_info["key"],
            "tipo_chave": pix_info["key_type"],
            "valor": total_value,
            "data_hora": now_str,
            "descricao": f"Pagamento lote referente ao Pedido {order['id']}"
        }
        pix_transactions.append(transaction)

    # 4. Formato 1: Geração de CSV (Para importação no Internet Banking)
    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as csv_file:
        fieldnames = ["id_pedido", "favorecido", "tipo_chave", "chave_pix", "valor", "data_hora", "descricao"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        
        writer.writeheader()
        for tx in pix_transactions:
            writer.writerow({
                "id_pedido": tx["id_pedido"],
                "favorecido": tx["favorecido"],
                "tipo_chave": tx["tipo_chave"],
                "chave_pix": tx["chave_pix"],
                "valor": f"{tx['valor']:.2f}",
                "data_hora": tx["data_hora"],
                "descricao": tx["descricao"]
            })
            
    # 5. Formato 2: Geração de JSON (Para integração direta via API de Banco)
    api_payload = {
        "lote_id": batch_id,
        "data_geracao": datetime.datetime.now().isoformat(),
        "total_transacoes": len(pix_transactions),
        "valor_total_lote": sum(tx["valor"] for tx in pix_transactions),
        "transacoes": [
            {
                "endToEndId": f"E2E{tx['id_pedido'].replace('-', '')}",
                "amount": int(tx["valor"] * 100), # Bancos geralmente leem centavos inteiros
                "key": tx["chave_pix"],
                "keyType": tx["tipo_chave"].lower(),
                "createdAt": tx["data_hora"],
                "description": tx["descricao"],
                "receiver": {
                    "name": tx["favorecido"]
                }
            } for tx in pix_transactions
        ]
    }
    
    with open(json_file_path, mode='w', encoding='utf-8') as json_file:
        json.dump(api_payload, json_file, indent=2, ensure_ascii=False)
        
    # 6. Atualiza o status no banco de dados para evitar pagamentos duplicados
    for order in approved_purchases:
        cursor.execute(
            "UPDATE purchases SET status = 'PROCESSED_PIX', batch_id = ? WHERE id = ?",
            (batch_id, order["id"])
        )
        
    # Salva o lote gerado na tabela pix_batches
    now_iso = datetime.datetime.now().isoformat()
    cursor.execute(
        """
        INSERT INTO pix_batches (batch_id, timestamp, total_transactions, total_amount, sent_to_bank)
        VALUES (?, ?, ?, ?, 0)
        """,
        (batch_id, now_iso, len(approved_purchases), sum(order["qty"] * order["price"] for order in approved_purchases))
    )
    conn.commit()
    conn.close()
    
    print(f"✅ Lote de Pagamentos Pix exportado com sucesso!")
    print(f"📂 CSV gerado em: {csv_file_path}")
    print(f"📂 JSON API gerado em: {json_file_path}")
    print(f"💰 Valor Total do Lote: R$ {api_payload['valor_total_lote']:.2f} ({api_payload['total_transacoes']} transações)")
    
    return api_payload

if __name__ == "__main__":
    export_pix_batch()
