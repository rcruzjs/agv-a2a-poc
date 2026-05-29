// Real-Time Dashboard Javascript Logic
const productsContainer = document.getElementById("products-container");
const a2uiRoot = document.getElementById("a2ui-root");
const consoleRoot = document.getElementById("console-root");
const serverStatus = document.getElementById("server-status");

// Carregamento de Fallback Resiliente Inicial
fetchInitialData();

function fetchInitialData() {
    fetch("/api/products")
    .then(res => res.json())
    .then(products => {
        updateStockGrid(products);
    })
    .catch(err => console.error("Erro no fetch inicial de produtos:", err));
}

// SSE Event Stream Connection
const eventSource = new EventSource("/api/events");

eventSource.onopen = () => {
    console.log("SSE Connection opened.");
    serverStatus.innerText = "SSE Connected";
    serverStatus.parentElement.querySelector(".status-dot").style.backgroundColor = "var(--color-emerald)";
    serverStatus.parentElement.querySelector(".status-dot").style.boxShadow = "var(--glow-emerald)";
    addConsoleLog("🔌 [UCP] Conexão SSE estabelecida com sucesso com o plano de controle.");
    fetchPendingPix(); // Carregar fila Pix ao conectar
};

eventSource.onerror = (err) => {
    console.error("SSE Connection error:", err);
    serverStatus.innerText = "Disconnected";
    serverStatus.parentElement.querySelector(".status-dot").style.backgroundColor = "var(--color-rose)";
    serverStatus.parentElement.querySelector(".status-dot").style.boxShadow = "var(--glow-rose)";
    addConsoleLog("❌ [UCP] Conexão perdida. Tentando reconectar...");
};

// 1. Stock updates
eventSource.addEventListener("stock_update", (event) => {
    const products = JSON.parse(event.data);
    updateStockGrid(products);
});

// 2. Log updates
eventSource.addEventListener("log", (event) => {
    const logData = JSON.parse(event.data);
    addConsoleLog(logData.message);
});

// 3. Purchase pending action card (A2UI)
eventSource.addEventListener("purchase_pending", (event) => {
    const actionData = JSON.parse(event.data);
    renderActionCard(actionData);
});

// 4. Pix updates
eventSource.addEventListener("pix_update", (event) => {
    fetchPendingPix();
});

// 5. Analytics updates (V2)
eventSource.addEventListener("analytics_update", (event) => {
    fetchAnalyticsData();
});

function updateStockGrid(products) {
    if (!products || products.length === 0) {
        productsContainer.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 2rem;">Nenhum produto cadastrado no estoque.</div>`;
        return;
    }

    const skuImageMap = {
        "SKU-001": "/static/images/ssd_nvme.png",
        "SKU-002": "/static/images/ram_ddr5.png",
        "SKU-003": "/static/images/cpu_i7.png",
        "SKU-004": "/static/images/gpu_rtx.png"
    };

    productsContainer.innerHTML = "";
    products.forEach(p => {
        const isBreached = p.qtd_atual < p.qtd_minima;
        const progressPercentage = Math.min(100, (p.qtd_atual / (p.qtd_minima * 2)) * 100);
        const minPercentage = (p.qtd_minima / (p.qtd_minima * 2)) * 100;
        const imageUrl = skuImageMap[p.sku] || "/static/images/ssd_nvme.png";
        
        const card = document.createElement("div");
        card.className = "product-card";
        card.innerHTML = `
            <div class="product-meta" style="display: flex; align-items: center; gap: 15px; width: 100%; margin-bottom: 0.6rem;">
                <img src="${imageUrl}" alt="${p.name}" style="width: 48px; height: 48px; border-radius: 8px; object-fit: cover; border: 1px solid var(--card-border); box-shadow: 0 4px 10px rgba(0,0,0,0.3);" />
                <div style="flex: 1;">
                    <span class="product-name" style="display: block; font-weight: 500; font-size: 0.95rem; margin-bottom: 4px;">${p.name}</span>
                    <span class="product-sku" style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; background: rgba(99, 102, 241, 0.15); color: #a5b4fc; padding: 2px 6px; border-radius: 4px;">${p.sku}</span>
                </div>
                <div class="product-qty-info" style="color: ${isBreached ? 'var(--color-rose)' : 'var(--color-emerald)'}; font-weight: 500; font-size: 0.95rem; white-space: nowrap;">
                    ${p.qtd_atual} / ${p.qtd_minima} <span style="font-size: 0.75rem; color: var(--text-secondary); font-weight: normal;">(Mín)</span>
                </div>
            </div>
            <div class="progress-container">
                <div class="progress-bar ${isBreached ? 'status-breach' : 'status-ok'}" style="width: ${progressPercentage}%"></div>
                <div class="min-indicator" style="left: ${minPercentage}%" title="Quantidade Mínima"></div>
            </div>
        `;
        productsContainer.appendChild(card);
    });
}

function addConsoleLog(message) {
    const logLine = document.createElement("div");
    logLine.className = "console-line";
    
    // Add custom styling based on prefix
    if (message.includes("📥")) logLine.style.color = "#a5b4fc"; // Input / gRPC
    else if (message.includes("⚠️")) logLine.style.color = "#f43f5e"; // Stock breach
    else if (message.includes("🤖")) logLine.style.color = "#c084fc"; // A2A Broker
    else if (message.includes("🔍") || message.includes("⚖️")) logLine.style.color = "#38bdf8"; // MCP audit
    else if (message.includes("✅")) logLine.style.color = "#34d399"; // Approved
    else if (message.includes("❌")) logLine.style.color = "#fb7185"; // Error / Rejected
    
    logLine.innerText = message;
    consoleRoot.appendChild(logLine);
    consoleRoot.scrollTop = consoleRoot.scrollHeight;
}

function renderActionCard(order) {
    const skuImageMap = {
        "SKU-001": "/static/images/ssd_nvme.png",
        "SKU-002": "/static/images/ram_ddr5.png",
        "SKU-003": "/static/images/cpu_i7.png",
        "SKU-004": "/static/images/gpu_rtx.png"
    };
    const imageUrl = skuImageMap[order.sku] || "/static/images/ssd_nvme.png";

    a2uiRoot.innerHTML = `
        <div class="action-card">
            <div class="action-header">
                <span class="action-badge">Pagamento Pendente</span>
                <span class="action-order-id">${order.order_id}</span>
            </div>
            <div class="action-body">
                <h3 class="action-title">Autorizar Compra de Suprimentos</h3>
                <p class="action-subtitle">O Agente de Compras detectou estoque baixo de <strong>${order.product_name}</strong> e estruturou um pedido de reposição.</p>
                
                <div class="action-details" style="display: grid; grid-template-columns: 64px 1fr 1fr; gap: 12px; font-size: 0.85rem; align-items: center;">
                    <img src="${imageUrl}" alt="${order.product_name}" style="width: 64px; height: 64px; border-radius: 8px; object-fit: cover; border: 1px solid rgba(255,255,255,0.1); grid-row: span 2;" />
                    <div class="detail-item" style="grid-column: span 2;">
                        <span class="detail-label">Item / SKU</span>
                        <span class="detail-value">${order.product_name} (${order.sku})</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Quantidade de Compra</span>
                        <span class="detail-value">${order.qty} un</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Fornecedor Selecionado</span>
                        <span class="detail-value">${order.supplier} (prazo: ${order.delivery_days} dias)</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Preço Unitário</span>
                        <span class="detail-value">R$ ${order.price.toFixed(2)}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Valor Total Autorizável</span>
                        <span class="detail-value highlight">R$ ${order.total.toFixed(2)}</span>
                    </div>
                </div>
            </div>
            <div class="action-footer">
                <button class="action-btn btn-reject" onclick="handlePurchaseAction('${order.order_id}', 'reject')">Recusar Pedido</button>
                <button class="action-btn btn-approve" onclick="handlePurchaseAction('${order.order_id}', 'approve')">Autorizar Pagamento</button>
            </div>
        </div>
    `;
    
    // Add visual bounce animation to console
    addConsoleLog(`🔔 [Interface] A2UI: Card de ação renderizado para o pedido '${order.order_id}'. Autorização humana necessária.`);
}

function clearActionCard() {
    a2uiRoot.innerHTML = `
        <div class="a2ui-placeholder">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="m9 12 2 2 4-4"/>
            </svg>
            <p style="font-weight: 500;">Status do Sistema Seguro</p>
            <p style="font-size: 0.85rem; color: var(--text-secondary);">Aguardando eventos de ruptura do gRPC para processar autorizações.</p>
        </div>
    `;
}

function handlePurchaseAction(orderId, action) {
    addConsoleLog(`👤 [Operador] Enviando decisão de '${action === 'approve' ? 'APROVAÇÃO' : 'REJEIÇÃO'}' para o pedido ${orderId}...`);
    
    fetch(`/api/${action}/${orderId}`, {
        method: "POST"
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Erro ao enviar decisao: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        clearActionCard();
        console.log(`Action '${action}' submitted successfully for order ${orderId}`);
        fetchPendingPix(); // Recarregar fila Pix após aprovar
    })
    .catch(err => {
        console.error(err);
        addConsoleLog(`❌ [Interface] Erro ao submeter ação do operador: ${err.message}`);
    });
}

// --- Operações da Aba de Pix em Lote & Outras Abas (V2) ---
const pixCountBadge = document.getElementById("pix-count-badge");
const pixListContainer = document.getElementById("pix-list-container");

// Estados Globais de Checkout
let activeCheckoutSku = "";
let activeCheckoutPrice = 0.0;
let activeCheckoutProductName = "";
let currentCheckoutOrderId = "";

function switchTab(tabName) {
    const stockBtn = document.getElementById("tab-stock");
    const pixBtn = document.getElementById("tab-pix");
    const shopBtn = document.getElementById("tab-shop");
    const kpiBtn = document.getElementById("tab-kpi");
    
    const stockContent = document.getElementById("stock-content");
    const pixContent = document.getElementById("pix-content");
    const shopContent = document.getElementById("shop-content");
    const kpiContent = document.getElementById("kpi-content");
    
    // Reset buttons
    [stockBtn, pixBtn, shopBtn, kpiBtn].forEach(btn => btn.classList.remove("active-tab"));
    // Reset contents
    [stockContent, pixContent, shopContent, kpiContent].forEach(c => {
        c.classList.remove("active-content");
        c.style.display = "none";
    });
    
    if (tabName === "stock") {
        stockBtn.classList.add("active-tab");
        stockContent.classList.add("active-content");
        stockContent.style.display = "flex";
    } else if (tabName === "pix") {
        pixBtn.classList.add("active-tab");
        pixContent.classList.add("active-content");
        pixContent.style.display = "flex";
        fetchPendingPix();
    } else if (tabName === "shop") {
        shopBtn.classList.add("active-tab");
        shopContent.classList.add("active-content");
        shopContent.style.display = "flex";
        cancelCheckout(); // Volta ao catálogo padrão
        fetchShopCatalog();
    } else if (tabName === "kpi") {
        kpiBtn.classList.add("active-tab");
        kpiContent.classList.add("active-content");
        kpiContent.style.display = "flex";
        fetchAnalyticsData();
    }
}

function fetchPendingPix() {
    fetch("/api/pix/pending")
    .then(res => res.json())
    .then(data => {
        pixCountBadge.innerText = data.length;
        if (!data || data.length === 0) {
            pixListContainer.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 2.5rem 1rem;">Nenhum Pix pendente de envio para o banco no momento.</div>`;
            return;
        }
        
        const skuImageMap = {
            "SKU-001": "/static/images/ssd_nvme.png",
            "SKU-002": "/static/images/ram_ddr5.png",
            "SKU-003": "/static/images/cpu_i7.png",
            "SKU-004": "/static/images/gpu_rtx.png"
        };
        
        pixListContainer.innerHTML = "";
        data.forEach(tx => {
            const imageUrl = skuImageMap[tx.sku] || "/static/images/ssd_nvme.png";
            const row = document.createElement("div");
            row.className = "product-card";
            row.style.background = "rgba(245, 158, 11, 0.02)";
            row.style.border = "1px solid rgba(245, 158, 11, 0.1)";
            row.style.padding = "10px 12px";
            row.innerHTML = `
                <div style="display: flex; align-items: center; gap: 12px; width: 100%;">
                    <img src="${imageUrl}" alt="${tx.supplier}" style="width: 36px; height: 36px; border-radius: 6px; object-fit: cover;" />
                    <div style="flex: 1; font-size: 0.8rem;">
                        <div style="font-weight: 600; color: var(--text-primary);">${tx.supplier}</div>
                        <div style="color: var(--text-secondary); font-size: 0.75rem; font-family: monospace;">Pix (${tx.tipo_chave}): ${tx.chave_pix}</div>
                        <div style="color: var(--text-secondary); font-size: 0.7rem; margin-top: 2px;">ID: ${tx.id} | ${tx.timestamp.replace('T', ' ').substring(0, 19)}</div>
                    </div>
                    <div style="text-align: right;">
                        <span style="color: var(--color-amber); font-weight: 600; font-size: 0.9rem;">R$ ${(tx.price * tx.qty).toFixed(2)}</span>
                        <br/>
                        <div style="font-size: 0.65rem; color: #a5b4fc; background: rgba(99,102,241,0.15); padding: 1px 4px; border-radius: 4px; display: inline-block; margin-top: 2px;">Lote Pix</div>
                    </div>
                </div>
            `;
            pixListContainer.appendChild(row);
        });
    })
    .catch(err => {
        console.error("Erro ao buscar fila de Pix:", err);
    });
}

function exportPixBatchToServer() {
    addConsoleLog("🚀 [Lote-Pix] Enviando solicitação de geração de lote Pix para o UCP...");
    
    fetch("/api/pix/export", {
        method: "POST"
    })
    .then(res => {
        if (!res.ok) throw new Error("Erro na exportação.");
        return res.json();
    })
    .then(data => {
        if (data.status === "empty") {
            addConsoleLog("ℹ️ [Lote-Pix] Nenhum pagamento autorizado para exportar no lote.");
            alert("Nenhum pagamento autorizado pendente de envio Pix.");
            return;
        }
        
        addConsoleLog(`✅ [Lote-Pix] Lote '${data.batch_id}' gerado com sucesso! Valor total: R$ ${data.total.toFixed(2)}.`);
        alert(`Sucesso! Lote '${data.batch_id}' gerado na pasta /exports.`);
        fetchPendingPix();
    })
    .catch(err => {
        console.error(err);
        addConsoleLog(`❌ [Lote-Pix] Falha ao exportar lote Pix: ${err.message}`);
    });
}

// ==========================================
// MÓDULOS DE FRONTEND DA VERSÃO 2 (E-COMMERCE)
// ==========================================

function fetchShopCatalog() {
    const catalogContainer = document.getElementById("shop-catalog");
    catalogContainer.innerHTML = `<div style="text-align: center; color: var(--text-secondary); width: 100%; padding: 2rem;">Carregando catálogo de hardware...</div>`;
    
    fetch("/api/products")
    .then(res => res.json())
    .then(products => {
        const skuImageMap = {
            "SKU-001": "/static/images/ssd_nvme.png",
            "SKU-002": "/static/images/ram_ddr5.png",
            "SKU-003": "/static/images/cpu_i7.png",
            "SKU-004": "/static/images/gpu_rtx.png"
        };
        
        // Custo estimado do produto baseado no mercado (cotação de compras x 1.25)
        const pricesMap = {
            "SKU-001": 425.00,
            "SKU-002": 350.00,
            "SKU-003": 1812.50,
            "SKU-004": 2687.50
        };

        catalogContainer.innerHTML = "";
        products.forEach(p => {
            const imageUrl = skuImageMap[p.sku] || "/static/images/ssd_nvme.png";
            const price = pricesMap[p.sku] || 499.00;
            const isOutOfStock = p.qtd_atual <= 0;
            
            const card = document.createElement("div");
            card.className = "product-card";
            card.style.display = "flex";
            card.style.flexDirection = "column";
            card.style.justifyContent = "space-between";
            card.style.padding = "12px";
            card.innerHTML = `
                <div>
                    <img src="${imageUrl}" alt="${p.name}" style="width: 100%; height: 100px; border-radius: 8px; object-fit: cover; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 8px;"/>
                    <h4 style="font-size: 0.85rem; font-weight: 600; margin-bottom: 2px;">${p.name}</h4>
                    <span style="font-family: monospace; font-size: 0.7rem; color: var(--text-secondary);">${p.sku}</span>
                    
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px;">
                        <span style="font-size: 0.75rem; color: ${isOutOfStock ? 'var(--color-rose)' : 'var(--color-emerald)'}; font-weight: 500;">
                            ${isOutOfStock ? 'Esgotado' : `Estoque: ${p.qtd_atual} un`}
                        </span>
                        <span style="font-size: 0.95rem; font-weight: 700; color: var(--color-emerald);">R$ ${price.toFixed(2)}</span>
                    </div>
                </div>
                
                <button onclick="openCheckout('${p.sku}', '${p.name}', '${imageUrl}', ${price})" 
                        ${isOutOfStock ? 'disabled' : ''} 
                        class="action-btn btn-approve" 
                        style="width: 100%; margin-top: 10px; padding: 6px; font-size: 0.8rem; background: ${isOutOfStock ? 'rgba(255,255,255,0.05)' : 'var(--color-indigo)'}; color: ${isOutOfStock ? 'var(--text-secondary)' : '#fff'}; box-shadow: ${isOutOfStock ? 'none' : 'var(--glow-indigo)'}; cursor: ${isOutOfStock ? 'not-allowed' : 'pointer'}; border: none;">
                    ${isOutOfStock ? 'Sem Estoque' : 'Comprar SKU'}
                </button>
            `;
            catalogContainer.appendChild(card);
        });
    })
    .catch(err => {
        console.error("Erro ao buscar catálogo:", err);
    });
}

function openCheckout(sku, name, imageUrl, price) {
    activeCheckoutSku = sku;
    activeCheckoutPrice = price;
    activeCheckoutProductName = name;
    
    document.getElementById("shop-catalog").style.display = "none";
    document.getElementById("checkout-form-container").style.display = "block";
    document.getElementById("payment-gateway-modal").style.display = "none";
    
    document.getElementById("checkout-item-summary").innerHTML = `
        <img src="${imageUrl}" alt="${name}" style="width: 40px; height: 40px; border-radius: 6px; object-fit: cover;" />
        <div>
            <div style="font-weight: 600; color: #fff;">${name}</div>
            <div style="color: var(--text-secondary); font-size: 0.75rem;">SKU: ${sku} | Preço: R$ ${price.toFixed(2)}</div>
        </div>
    `;
    
    document.getElementById("chk-qty").value = 1;
    calculateShippingPrice();
}

function cancelCheckout() {
    document.getElementById("shop-catalog").style.display = "grid";
    document.getElementById("checkout-form-container").style.display = "none";
    document.getElementById("payment-gateway-modal").style.display = "none";
}

function toggleCardInputs() {
    const payment = document.getElementById("chk-payment").value;
    const cardFields = document.getElementById("card-fields-container");
    cardFields.style.display = (payment === "CREDIT_CARD") ? "block" : "none";
}

function calculateShippingPrice() {
    const qty = parseInt(document.getElementById("chk-qty").value) || 1;
    const cep = document.getElementById("chk-cep").value;
    
    if (!cep) return;
    
    fetch(`/api/shipping/calculate?sku=${activeCheckoutSku}&qty=${qty}&cep=${cep}`)
    .then(res => res.json())
    .then(data => {
        document.getElementById("chk-address").value = data.endereco_completo;
        
        const subtotal = activeCheckoutPrice * qty;
        const frete = data.custo_frete;
        const total = subtotal + frete;
        
        document.getElementById("summary-prod-val").innerText = `R$ ${subtotal.toFixed(2)}`;
        document.getElementById("summary-shipping-val").innerText = `R$ ${frete.toFixed(2)}`;
        document.getElementById("summary-total-val").innerText = `R$ ${total.toFixed(2)}`;
        document.getElementById("summary-logistics-info").innerHTML = `
            📦 Peso Estimado: ${data.peso_total_kg.toFixed(3)} kg | Cubagem: ${data.volume_cubagem_m3.toFixed(4)} m³
        `;
    })
    .catch(err => {
        console.error("Erro ao calcular frete:", err);
    });
}

function submitCheckoutOrder() {
    const name = document.getElementById("chk-name").value;
    const cpf = document.getElementById("chk-cpf").value;
    const cep = document.getElementById("chk-cep").value;
    const address = document.getElementById("chk-address").value;
    const payment = document.getElementById("chk-payment").value;
    const qty = parseInt(document.getElementById("chk-qty").value) || 1;
    
    if (!name || !cpf || !cep || !address) {
        alert("Por favor, preencha todos os campos do checkout.");
        return;
    }
    
    const payload = {
        cliente_nome: name,
        cliente_cpf: cpf,
        cep_destino: cep,
        endereco_logradouro: address,
        forma_pagamento: payment,
        items: [
            { sku: activeCheckoutSku, quantidade: qty }
        ]
    };
    
    addConsoleLog(`🛒 [Checkout] Enviando requisição de criação de pedido para o SKU ${activeCheckoutSku}...`);
    
    fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => { throw new Error(err.detail || "Erro no estoque."); });
        }
        return res.json();
    })
    .then(order => {
        currentCheckoutOrderId = order.id_pedido;
        openGatewayModal(order, payment);
    })
    .catch(err => {
        console.error(err);
        addConsoleLog(`❌ [Checkout] Erro ao criar pedido: ${err.message}`);
        alert(`Checkout Recusado: ${err.message}`);
    });
}

function openGatewayModal(order, payment) {
    document.getElementById("checkout-form-container").style.display = "none";
    
    const gatewayModal = document.getElementById("payment-gateway-modal");
    const title = document.getElementById("gateway-title");
    const subtitle = document.getElementById("gateway-subtitle");
    const dynamicArea = document.getElementById("gateway-dynamic-area");
    
    gatewayModal.style.display = "block";
    subtitle.innerText = `ID do Pedido: ${order.id_pedido} | Valor Total: R$ ${order.valor_total.toFixed(2)}`;
    
    if (payment === "PIX") {
        title.innerHTML = "⚡ Gateway de Pagamento: PIX IMEDIATO";
        title.style.color = "var(--color-amber)";
        gatewayModal.style.borderColor = "var(--color-amber)";
        gatewayModal.style.boxShadow = "var(--glow-amber)";
        
        dynamicArea.innerHTML = `
            <p style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 10px;">Escaneie o QR Code ou copie o código Copia e Cola para pagar:</p>
            <div style="background: white; padding: 10px; width: 140px; height: 140px; margin: 0 auto 10px; border-radius: 8px; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(0,0,0,0.3);">
                <!-- Falso QR Code usando emoji -->
                <span style="font-size: 80px; filter: grayscale(1);">🏁</span>
            </div>
            <code style="font-family: monospace; font-size: 0.7rem; background: #000; padding: 6px; border-radius: 4px; display: block; color: var(--color-amber); word-break: break-all;">00020101021226830014br.gov.bcb.pix2561api.itau/pix/v2/${order.id_pedido}5204000053039865802BR5912Ricardo_Cruz6009Sao_Paulo62070503***6304CA12</code>
        `;
    } else if (payment === "CREDIT_CARD") {
        title.innerHTML = "💳 Gateway de Pagamento: CARTÃO DE CRÉDITO";
        title.style.color = "var(--color-indigo)";
        gatewayModal.style.borderColor = "var(--color-indigo)";
        gatewayModal.style.boxShadow = "var(--glow-indigo)";
        
        dynamicArea.innerHTML = `
            <p style="font-size: 0.85rem; color: #fff; font-weight: 500;">Checagem Anti-Fraude Síncrona Ativa</p>
            <p style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 4px; line-height: 1.4;">Seu CPF está sendo avaliado em tempo real no banco de dados consolidado. Clique abaixo para rodar a simulação.</p>
        `;
    } else {
        title.innerHTML = "📄 Gateway de Pagamento: BOLETO BANCÁRIO";
        title.style.color = "var(--color-cyan)";
        gatewayModal.style.borderColor = "var(--color-cyan)";
        gatewayModal.style.boxShadow = "var(--glow-cyan)";
        
        dynamicArea.innerHTML = `
            <p style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 8px;">Linha Digitável do Boleto:</p>
            <code style="font-family: monospace; font-size: 0.75rem; background: #000; padding: 6px; border-radius: 4px; display: block; color: var(--color-cyan); font-weight: bold; letter-spacing: 0.5px;">34191.79001 01043.513184 91020.150008 7 90050000${order.valor_total.toFixed(0)}00</code>
            <p style="font-size: 0.7rem; color: var(--text-secondary); margin-top: 8px;">Compensação em até 48 horas úteis.</p>
        `;
    }
}

function cancelPayment() {
    cancelCheckout();
    addConsoleLog(`⚠️ [Checkout] Checkout de pedido ${currentCheckoutOrderId} pausado. Aguardando confirmação do gateway.`);
}

function executeGatewayPayment() {
    addConsoleLog(`💳 [Gateway] Confirmando transação do pedido ${currentCheckoutOrderId} com o banco emissor...`);
    
    fetch("/api/checkout/pay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_pedido: currentCheckoutOrderId })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "fraud_rejected") {
            alert("❌ PAGAMENTO RECUSADO POR SUSPEITA DE FRAUDE (CPF inconsistente no Score síncrono!).");
            cancelCheckout();
            return;
        }
        
        alert("✅ Pagamento aprovado! O Worker de Logística foi despertado para processar a remessa física.");
        cancelCheckout();
        switchTab("stock");
    })
    .catch(err => {
        console.error(err);
        addConsoleLog(`❌ [Gateway] Erro ao pagar: ${err.message}`);
    });
}

// ==========================================
// MÓDULOS DE KPI & WINDOW FUNCTIONS (V2)
// ==========================================

function fetchAnalyticsData() {
    const revTable = document.getElementById("kpi-revenue-table");
    const invList = document.getElementById("kpi-inventory-list");
    
    fetch("/api/analytics/summary")
    .then(res => res.json())
    .then(analytics => {
        const kpis = analytics.kpis;
        document.getElementById("kpi-total-revenue").innerText = `R$ ${kpis.faturamento_total.toFixed(2)}`;
        document.getElementById("kpi-ticket-avg").innerText = `R$ ${kpis.ticket_medio.toFixed(2)}`;
        document.getElementById("kpi-conversion-rate").innerText = `${kpis.taxa_conversao.toFixed(2)} %`;
        document.getElementById("kpi-total-orders").innerText = `${kpis.total_pagos} / ${kpis.total_pedidos}`;
        
        if (!analytics.daily_revenue || analytics.daily_revenue.length === 0) {
            revTable.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 1rem;">Sem dados de faturamento consolidado.</div>`;
        } else {
            revTable.innerHTML = `
                <table style="width: 100%; border-collapse: collapse; text-align: left;">
                    <thead>
                        <tr style="color: var(--text-primary); border-bottom: 1px solid rgba(255,255,255,0.1); font-size: 0.7rem; text-transform: uppercase;">
                            <th style="padding: 4px;">Data</th>
                            <th style="padding: 4px;">Faturamento Dia</th>
                            <th style="padding: 4px; text-align: right; color: var(--color-emerald);">Acumulado (Window)</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${analytics.daily_revenue.map(r => `
                            <tr style="border-bottom: 1px solid rgba(255,255,255,0.02);">
                                <td style="padding: 4px; color: var(--text-primary); font-weight: 500;">${r.data_dia}</td>
                                <td style="padding: 4px; color: var(--text-secondary);">R$ ${r.valor_dia.toFixed(2)}</td>
                                <td style="padding: 4px; text-align: right; color: var(--color-emerald); font-weight: 600;">R$ ${r.faturamento_acumulado.toFixed(2)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            `;
        }
        
        if (!analytics.inventory_metrics || analytics.inventory_metrics.length === 0) {
            invList.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 1rem;">Sem dados de inventário.</div>`;
        } else {
            invList.innerHTML = "";
            analytics.inventory_metrics.forEach(m => {
                const totalGiro = m.total_vendido;
                const percent = Math.min(100, (totalGiro / 10) * 100);
                
                const itemDiv = document.createElement("div");
                itemDiv.className = "product-card";
                itemDiv.style.background = "rgba(255,255,255,0.01)";
                itemDiv.style.padding = "8px 10px";
                itemDiv.innerHTML = `
                    <div style="display: flex; justify-content: space-between; font-size: 0.75rem; margin-bottom: 4px;">
                        <span style="font-weight: 500;">${m.name}</span>
                        <span style="color: var(--color-cyan); font-weight: 600;">${totalGiro} vendidos <span style="font-size: 0.65rem; color: var(--text-secondary);">(estoque: ${m.qtd_atual})</span></span>
                    </div>
                    <div class="progress-container" style="height: 6px;">
                        <div class="progress-bar" style="width: ${percent}%; background: linear-gradient(90deg, var(--color-indigo), var(--color-cyan));"></div>
                    </div>
                `;
                invList.appendChild(itemDiv);
            });
        }
    })
    .catch(err => {
        console.error("Erro ao buscar analíticos de KPIs:", err);
    });
}
