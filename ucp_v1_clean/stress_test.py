import grpc
import time
import random
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

# Add protos directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "protos"))
import demand_pb2
import demand_pb2_grpc

GRPC_SERVER = "localhost:50051"

def send_demand(stub, sku, qty):
    print(f"📤 [Cliente de Teste] Enviando demanda via gRPC: Consumindo {qty} unidade(s) de '{sku}'...")
    try:
        request = demand_pb2.DemandRequest(sku=sku, quantity_consumed=qty)
        response = stub.ReportDemand(request)
        print(f"📥 [Resposta gRPC] SKU: {response.sku} | Qtd Restante: {response.current_quantity} | Ruptura: {response.breach_detected}")
        if response.breach_detected:
            print(f"   ⚠️ ALERTA: RUPTURA DE ESTOQUE DETECTADA!")
        print("-" * 50)
        return response
    except grpc.RpcError as e:
        print(f"❌ Erro gRPC: {e.code()} - {e.details()}")
        return None

def run_stress_test():
    print("=" * 60)
    print("🚀 INICIANDO CLIENTE DE SIMULAÇÃO DE ESTRESSE DE ESTOQUE V1")
    print(f"Conectando ao Servidor gRPC AP2 em {GRPC_SERVER}...")
    print("=" * 60)
    
    with grpc.insecure_channel(GRPC_SERVER) as channel:
        stub = demand_pb2_grpc.DemandServiceStub(channel)
        
        # 1. Trigger immediate breach for demo
        print("\n🔥 PASSO 1: Forçando artificialmente uma ruptura no SKU-002 ('Memória RAM 16GB DDR5')")
        print("Estoque inicial: 8 unidades. Limite mínimo: 12 unidades. Consumindo 3 unidades...")
        send_demand(stub, "SKU-002", 3)
        
        time.sleep(2.0)
        
        # 2. Continuous random simulation
        print("\n🎮 PASSO 2: Executando simulação de demanda ativa contínua e aleatória.")
        print("Pressione Ctrl+C para encerrar a simulação.")
        print("=" * 60)
        
        skus = ["SKU-001", "SKU-002", "SKU-003", "SKU-004"]
        
        try:
            while True:
                sku = random.choice(skus)
                qty = random.randint(1, 3)
                send_demand(stub, sku, qty)
                
                # Sleep between 2.5 to 4.5 seconds
                sleep_time = random.uniform(2.5, 4.5)
                print(f"Aguardando por {sleep_time:.1f} segundos...")
                time.sleep(sleep_time)
        except KeyboardInterrupt:
            print("\n👋 Cliente de teste de estresse interrompido pelo operador.")

if __name__ == "__main__":
    run_stress_test()
