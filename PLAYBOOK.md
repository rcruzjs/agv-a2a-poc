# 📖 Playbook do Projeto: Universal Control Plane (UCP)

Este Playbook serve como o manual definitivo de arquitetura, operação e engenharia para o ecossistema **Universal Control Plane (UCP) B2B & B2C**. Ele orienta desenvolvedores e engenheiros de produto sobre como configurar, operar, testar e expandir os sistemas inteligentes de estoque, finanças e logística do projeto.

---

## 🧭 1. Visão Geral do Ecossistema

O UCP é um plano de controle multitask reativo em tempo real projetado para orquestrar operações de hardware de ponta a ponta. Ele resolve a complexidade de dois fluxos comerciais acoplados de forma circular:

```mermaid
graph TD
    subgraph B2C - Canal de Varejo (Saída)
        A[Loja E-commerce] -->|Checkout Compra| B[Reserva Estoque Atômica]
        B -->|Pagamento Aprovado| C[Despertar Worker Logística]
        C -->|Despacho do Item| D[Emissão de Carga B2C]
    end

    subgraph B2B - Canal de Atacado (Entrada)
        D -->|Ruptura de Estoque < Mínimo| E[Agente de Estoque AP2]
        E -->|Trigger A2A| F[Agente de Compras UCP]
        F -->|MCP Tool: Preços| G[Seleção do Melhor Fornecedor]
        G -->|A2UI: Card HITL| H[Autorização de Ordem de Compra]
        H -->|Geração de Lote Pix| I[Exportação CNAB/Pix e Transmissão]
        I -->|Reabastecimento Físico| A
    end
```

---

## 🏗️ 2. Arquitetura de Software e Componentes

O projeto é dividido em camadas modulares e desacopladas, utilizando gRPC para alto volume de dados de entrada e SSE (Server-Sent Events) para entrega de atualizações em tempo real ao navegador.

### 🗄️ A. Camada de Dados (`ucp_db.py`, `ucp_database.db`)
Utiliza um banco relacional leve (SQLite) com as seguintes tabelas estruturadas:
* `products`: Registra os SKUs de hardware, quantidades mínimas e atuais, além das dimensões físicas (altura, largura, comprimento, peso) usadas no cálculo logístico de cubagem.
* `suppliers`: Armazena a matriz de fornecedores homologados para cada SKU, com seus respectivos preços e prazos de entrega.
* `purchases`: Ledger de ordens de compra B2B geradas pelos agentes (status: `PENDING`, `APPROVED`, `REJECTED`, `PROCESSED_PIX`).
* `pedidos` & `itens_pedido`: Ledger de transações B2C do e-commerce (status: `PENDING`, `PAID`, `CANCELLED`).
* `pix_batches`: Controle de lotes financeiros gerados para transmissão bancária.

### 🌐 B. Camada Backend REST e Event Stream (`ucp_server.py`)
Servidor web principal construído em **FastAPI (Uvicorn)** que escuta na porta `8000`:
* Expõe endpoints REST para checkout B2C, autorizações HITL, controle de lotes Pix e métricas analíticas.
* Hospeda o endpoint `/api/events` (Server-Sent Events) que mantém canais de comunicação unidirecional abertos com as interfaces clientes para atualização de tela.
* Executa workers assíncronos em segundo plano para simular análises logísticas e cotações de agentes de compras.

### 📥 C. Camada de Ingestão gRPC AP2 (`ap2_server.py`)
Servidor gRPC robusto rodando na porta `50051`:
* Utiliza a especificação de protocolo definida em `protos/demand.proto`.
* É otimizado para ingerir fluxos em massa de demandas e baixas de estoque oriundos de sistemas externos (como a rotina de stress).
* Comunica-se de forma assíncrona com o servidor web através do barramento REST para disparar atualizações visuais na interface do UCP.

### ⚡ D. Camada Frontend Reativa SPA (`static/index.html`, `static/app.js`)
Painel interativo premium desenvolvido em **Vanilla HTML5, Javascript e CSS Glassmorphism**:
* Implementa uma arquitetura **Single Page Application (SPA)** com transições de abas fluidas e instantâneas.
* **Otimização Cirúrgica de DOM**: Atualiza elements específicos (barras de progresso e textos de quantidade) diretamente pelo ID do SKU, evitando a destruição e recriação do HTML da tela sob estresse.
* **Lazy Log Processing**: Processa e acumula logs em um buffer em memória de no máximo 150 registros em segundo plano, atualizando o console apenas quando o usuário está ativamente na aba do Cockpit.

---

## 🛠️ 3. Guia de Instalação e Configuração

### Pré-requisitos
* Python 3.10 ou superior
* Sistema Operacional: Windows / Linux / macOS

### Configuração do Ambiente
1. Clone o repositório ou navegue até a pasta raiz:
   ```powershell
   cd c:\Users\rcruz\Downloads\agv_prj_a2a
   ```
2. Inicialize o ambiente virtual e ative-o:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
3. Instale as dependências essenciais do projeto (como `fastapi`, `uvicorn`, `httpx`, `grpcio` e `protobuf`):
   ```powershell
   pip install -r requirements.txt
   ```
4. O banco de dados SQLite (`ucp_database.db`) será criado e populado automaticamente com os SKUs base (SSD, RAM, CPU e GPU) e fornecedores homologados na primeira inicialização de qualquer servidor.

---

## 🎮 4. Instruções de Operação (Como Executar o Ecossistema)

Para colocar o ecossistema inteiro para rodar em tempo real e visualizar o ciclo fechado das operações, execute os seguintes passos em terminais separados (garantindo que o ambiente `.venv` esteja ativado em cada um):

### Passo 1: Subir o Servidor gRPC AP2 (Ingestão de Demanda)
Este servidor lida com as baixas de estoque de alta performance.
```powershell
.venv\Scripts\python ap2_server.py
```
*Saída esperada:* `🚀 Servidor gRPC AP2 de Ingestão de Demanda escutando na porta 50051`

### Passo 2: Subir o Servidor UCP Principal (FastAPI)
Este é o coração do ecossistema que serve a interface web e gerencia as APIs.
```powershell
.venv\Scripts\python ucp_server.py
```
*Saída esperada:* `🚀 Iniciando Servidor FastAPI UCP em http://localhost:8000`

### Passo 3: Iniciar o Simulador de Estresse de Estoque (gRPC)
Esta rotina realiza baixas contínuas e aleatórias nos produtos para forçar rupturas de estoque e testar a estabilidade da interface e dos agentes em tempo real.
```powershell
.venv\Scripts\python stress_test.py
```
*Saída esperada:* Consumo periódico e alertas de rupturas aparecendo a cada 3 segundos no terminal.

### Passo 4: Acessar a Interface Gráfica
* Abra o seu navegador e acesse: **`http://localhost:8000`**
* Você verá a interface escura com efeitos neon em pleno funcionamento, com as quantidades de estoque flutuando e os logs gRPC rolando no console a 60 FPS estáveis!

---

## 🔬 5. Guia de Testes Automatizados

O projeto possui uma suíte robusta de testes de integração e unitários localizada em `test_suite.py`. Ela cobre 100% dos fluxos transacionais, concorrência atômica, cálculos matemáticos tributários da Versão 4 e exportação de lotes Pix.

Para executar os testes e atestar a integridade do código, execute na raiz do projeto:
```powershell
.venv\Scripts\python test_suite.py
```

### 🎯 O que a suíte de testes valida:
* **Concorrência e Reserva Atômica**: Garante que o banco SQLite impede a venda concorrente de produtos que ficaram com estoque zerado no milissegundo anterior.
* **Ingestão gRPC e Rupturas**: Valida que consumos gRPC abaixo do mínimo regulatório disparam de imediato o alerta e acordam o fluxo de compras B2B.
* **Engenharia Fiscal da V4**: Valida matematicamente as equações de impostos:
  * Débito de **18% ICMS + 10% IPI** sobre vendas B2C.
  * Crédito de **12% ICMS** sobre compras B2B.
  * Saldo tributário líquido a recolher e margem percentual real.
* **Controle de Lotes Pix**: Garante que lotes financeiros gerados associam corretamente as compras B2B correspondentes e atualizam os status de compensação bancária (`PENDING` -> `SENT`).

---

## 📐 6. Políticas de Engenharia e Boas Práticas (Google-like)

Para expandir o projeto mantendo os mais altos critérios de excelência:

### A. Performance de Renderização
* **Nunca utilize `innerHTML = ""` ou re-renderizações totais de listas no JavaScript se os itens já existirem na tela.** Prefira atualizações cirúrgicas de nós por ID.
* **Limite nós do DOM**: Mantenha no máximo 150 nós nos logs.
* **Utilize Memory Buffers para dados fora de tela**: Se o usuário não está olhando para a aba de logs, guarde a informação em variáveis locais e renderize apenas na reativação da aba.

### B. Integração de Eventos
* Qualquer alteração no banco de dados que mude o inventário físico deve notificar a rota `/api/stock/broadcast` do UCP, garantindo que todos os clientes conectados ao SSE atualizem suas barras de estoque em tempo real.

### C. Concorrência no Banco de Dados
* Modificações de escrita no SQLite que dependem de verificação de limites (como a quantidade de estoque) devem sempre utilizar a transação segura de reserva atômica (`ucp_db.reserve_stock_atomic`) para evitar condições de corrida em checkout concorrente.
