import grpc
from concurrent import futures
import time
import httpx
import ucp_db
import sys
import os
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

# Add protos directory to path so imports work correctly
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "protos"))
import demand_pb2
import demand_pb2_grpc

PORT = "50051"
UCP_URL = "http://localhost:8000"

class DemandService(demand_pb2_grpc.DemandServiceServicer):
    
    def process_demand(self, sku, qty):
        print(f"📥 [AP2 gRPC] Processando demanda: {qty} unidade(s) consumida(s) para o SKU '{sku}'")
        
        # Log to UCP event stream
        self._notify_ucp_log(f"📥 [AP2-gRPC] Demanda recebida: consumo de {qty} unidades do SKU {sku}")

        try:
            # 1. Update stock in DB
            new_qty = ucp_db.update_product_qty(sku, -qty)
            product = ucp_db.get_product(sku)
            
            breach_detected = False
            msg = f"Nível de estoque atualizado. SKU {sku}: {new_qty} unidades restantes."

            # 2. Check for breach
            if new_qty < product["qtd_minima"]:
                breach_detected = True
                msg = f"⚠️ [Ruptura] SKU {sku} está abaixo do mínimo ({new_qty} < {product['qtd_minima']})!"
                print(msg)
                
                # Notify UCP event log
                self._notify_ucp_log(f"⚠️ [Estoque] Ruptura de estoque detectada para {sku}: {new_qty} unidades restantes (Mín: {product['qtd_minima']})")
                
                # 3. A2A Trigger: Stock Agent calls Purchasing Agent (via UCP FastAPI Server)
                self._trigger_purchasing_agent(sku, new_qty, product["qtd_minima"])
            else:
                self._notify_ucp_log(f"✅ [Estoque] Status do estoque para {sku}: OK ({new_qty} restantes)")

            return demand_pb2.DemandResponse(
                sku=sku,
                current_quantity=new_qty,
                breach_detected=breach_detected,
                message=msg
            )
        except Exception as e:
            error_msg = f"❌ Erro ao processar demanda: {str(e)}"
            print(error_msg)
            self._notify_ucp_log(error_msg)
            return demand_pb2.DemandResponse(
                sku=sku,
                current_quantity=-1,
                breach_detected=False,
                message=error_msg
            )

    def ReportDemand(self, request, context):
        return self.process_demand(request.sku, request.quantity_consumed)

    def StreamDemands(self, request_iterator, context):
        for request in request_iterator:
            yield self.process_demand(request.sku, request.quantity_consumed)

    def _notify_ucp_log(self, message):
        """Sends an event log to the UCP Server to broadcast to the UI via SSE."""
        try:
            # Running synchronous post in thread pool to not block gRPC
            httpx.post(f"{UCP_URL}/api/a2a/log", json={"message": message}, timeout=1.0)
        except Exception:
            # UCP server might not be running yet, fail silently
            pass

    def _trigger_purchasing_agent(self, sku, current_qty, min_qty):
        """Triggers the Purchasing Agent flow on the UCP Server."""
        try:
            self._notify_ucp_log(f"🤖 [A2A-Trigger] Agente de Estoque acionando Agente de Compras para resolver a ruptura do {sku}")
            httpx.post(
                f"{UCP_URL}/api/a2a/trigger_purchase",
                json={"sku": sku, "current_qty": current_qty, "min_qty": min_qty},
                timeout=2.0
            )
        except Exception as e:
            print(f"Failed to trigger Purchasing Agent: {e}")
            self._notify_ucp_log(f"❌ [A2A-Trigger] Falha ao contatar Agente de Compras: {str(e)}")

def serve():
    # Make sure DB is initialized
    ucp_db.init_db()
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    demand_pb2_grpc.add_DemandServiceServicer_to_server(DemandService(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    print(f"🚀 Servidor gRPC AP2 de Ingestão de Demanda escutando na porta {PORT}")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    serve()
