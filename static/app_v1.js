// Real-Time Dashboard Javascript Logic
const productsContainer = document.getElementById("products-container");
const a2uiRoot = document.getElementById("a2ui-root");
const consoleRoot = document.getElementById("console-root");
const serverStatus = document.getElementById("server-status");

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

// --- Operações da Aba de Pix em Lote ---
const pixCountBadge = document.getElementById("pix-count-badge");
const pixListContainer = document.getElementById("pix-list-container");

function switchTab(tabName) {
    const stockBtn = document.getElementById("tab-stock");
    const pixBtn = document.getElementById("tab-pix");
    const stockContent = document.getElementById("stock-content");
    const pixContent = document.getElementById("pix-content");
    
    if (tabName === "stock") {
        stockBtn.classList.add("active-tab");
        pixBtn.classList.remove("active-tab");
        stockContent.classList.add("active-content");
        pixContent.classList.remove("active-content");
        stockContent.style.display = "flex";
        pixContent.style.display = "none";
    } else {
        stockBtn.classList.remove("active-tab");
        pixBtn.classList.add("active-tab");
        stockContent.classList.remove("active-content");
        pixContent.classList.add("active-content");
        stockContent.style.display = "none";
        pixContent.style.display = "flex";
        fetchPendingPix();
    }
}

function fetchPendingPix() {
    fetch("/api/pix/pending")
    .then(res => res.json())
    .then(data => {
        // Atualizar o número de registros pendentes no badge
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
        fetchPendingPix(); // Recarregar a lista (que ficará vazia)
    })
    .catch(err => {
        console.error(err);
        addConsoleLog(`❌ [Lote-Pix] Falha ao exportar lote Pix: ${err.message}`);
    });
}
