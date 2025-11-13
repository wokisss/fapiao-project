// frontend/static/js/main.js
document.addEventListener('DOMContentLoaded', function() {

    // --- (新) API 配置 ---
    // (后端 API 的地址)
    const API_BASE_URL = 'http://127.0.0.1:5000/api/v1';

    // --- (新) DOM 元素引用 ---
    const invoiceTableBody = document.getElementById('invoice-table-body');
    const noInvoicesMessage = document.getElementById('no-invoices');
    const searchForm = document.getElementById('search-form');
    const searchInput = document.getElementById('search-input');
    const uploadForm = document.getElementById('upload-form');
    const uploadBtn = document.getElementById('upload-btn');
    const fileInput = document.getElementById('zip-file-input');
    const clearDatabaseForm = document.getElementById('clear-database-form');
    const flashContainer = document.getElementById('flash-container');

    // 统计数据
    const statTotalCount = document.getElementById('stat-total-count');
    const statTotalAmount = document.getElementById('stat-total-amount');
    const statTotalTaxAmount = document.getElementById('stat-total-tax-amount');

    // 批量下载
    const downloadForm = document.getElementById('download-form');
    const selectAllCheckbox = document.getElementById('select-all');
    const downloadSelectedBtn = document.getElementById('download-selected');

    // 模态框
    const modal = document.getElementById('edit-modal');
    const closeModalBtn = document.querySelector('.close-modal');
    const editForm = document.getElementById('edit-form');
    const editIdDisplay = document.getElementById('edit-id-display');

    // --- (新) 核心数据加载函数 ---
    /**
     * @param {string} searchTerm 搜索关键词
     */
    async function loadInvoices(searchTerm = '') {
        // 1. 显示加载中
        invoiceTableBody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding: 20px;"><i class="fas fa-spinner fa-spin"></i> 正在加载...</td></tr>';
        noInvoicesMessage.style.display = 'none';

        try {
            // 2. 调用后端 API
            const response = await fetch(`${API_BASE_URL}/invoices?search=${encodeURIComponent(searchTerm)}`);

            if (!response.ok) {
                // (如果后端服务未运行，会在这里失败)
                let errorMsg = `HTTP 错误! 状态: ${response.status}`;
                try {
                    const errData = await response.json();
                    errorMsg = errData.error || errorMsg;
                } catch(e) {}
                throw new Error(errorMsg);
            }

            const data = await response.json();

            // 3. 渲染数据
            renderTable(data.invoices || []);
            updateStats(data.stats || {});

        } catch (error) {
            console.error('加载发票失败:', error);
            const msg = (error.message.includes("Failed to fetch"))
                ? "加载失败：无法连接到后端服务 (请确保 backend/run.py 正在运行)"
                : `加载失败: ${error.message}`;

            invoiceTableBody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 20px; color: red;">${msg}</td></tr>`;
            showNotification(msg, 'error');
            updateStats({}); // 清空统计
        }
    }

    // --- (新) 渲染函数 ---
    /**
     * @param {Array} invoices 发票数据数组
     */
    function renderTable(invoices) {
        invoiceTableBody.innerHTML = ''; // 清空

        if (!invoices || invoices.length === 0) {
            noInvoicesMessage.style.display = 'block'; // 显示 "未找到"
            return;
        }

        noInvoicesMessage.style.display = 'none'; // 隐藏 "未找到"

        invoices.forEach(inv => {
            // (格式化金额)
            const amount = (inv.amount !== null && inv.amount !== undefined) ? `¥${Number(inv.amount).toFixed(2)}` : 'N/A';
            const totalAmount = (inv.total_amount !== null && inv.total_amount !== undefined) ? `¥${Number(inv.total_amount).toFixed(2)}` : 'N/A';

            // (创建 HTML 字符串)
            const row = `
                <tr>
                    <td><input type="checkbox" name="selected_ids" value="${inv.id}" class="invoice-checkbox"></td>
                    <td>${inv.invoice_code || 'N/A'}</td>
                    <td><span class="invoice-number">${inv.invoice_number || 'N/A'}</span></td>
                    <td>${inv.issue_date || 'N/A'}</td>
                    <td class="invoice-amount">${amount}</td>
                    <td class="invoice-amount">${totalAmount}</td>
                    <td>${inv.buyer_name || 'N/A'}</td>
                    <td>${inv.seller_name || 'N/A'}</td>
                    <td>
                        <a href="${API_BASE_URL}/download/${inv.id}" class="action-btn download-link" title="下载" target="_blank">
                            <i class="fas fa-download"></i>
                        </a>

                        <button type="button" class="action-btn edit-btn" title="编辑"
                            data-id="${inv.id}"
                            data-code="${inv.invoice_code || ''}"
                            data-number="${inv.invoice_number || ''}"
                            data-date="${inv.issue_date || ''}"
                            data-amount="${inv.amount || 0.0}"
                            data-total_amount="${inv.total_amount || 0.0}"
                            data-buyer="${inv.buyer_name || ''}"
                            data-seller="${inv.seller_name || ''}">
                            <i class="fas fa-edit"></i>
                        </button>

                        <button type="button" class="action-btn delete-btn" title="删除" data-id="${inv.id}">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
            // (插入到 DOM)
            invoiceTableBody.insertAdjacentHTML('beforeend', row);
        });

        // (新) 渲染后必须重新附加事件监听器
        addDynamicEventListeners();
    }

    /**
     * @param {Object} stats 统计数据对象
     */
    function updateStats(stats) {
        statTotalCount.textContent = stats.total_count || 0;
        statTotalAmount.textContent = stats.total_amount || '¥0.00';
        statTotalTaxAmount.textContent = stats.total_tax_amount || '¥0.00';
    }

    // (新) Flash 消息 (弹窗)
    /**
     * @param {string} message 消息内容
     * @param {string} type 'success' 或 'error'
     */
    function showNotification(message, type = 'success') {
        const flashMessage = document.createElement('div');
        flashMessage.className = `flash-messages ${type === 'success' ? 'flash-success' : 'flash-error'}`;

        // (*** 新增: 支持 \n 换行 ***)
        flashMessage.style.whiteSpace = 'pre-line';
        flashMessage.textContent = message;

        flashContainer.appendChild(flashMessage);

        // 5 秒后自动移除
        setTimeout(() => {
            flashMessage.style.opacity = '0';
            setTimeout(() => flashMessage.remove(), 500); // 等待淡出动画完成
        }, 5000); // (失败消息可以持续更久，例如 8000)
    }

    // --- (新) 事件监听器 ---

    // (新) 搜索
    searchForm.addEventListener('submit', function(e) {
        e.preventDefault(); // 阻止表单默认提交
        const searchTerm = searchInput.value;
        loadInvoices(searchTerm);
    });


    // (*** //     *** 关键修改从这里开始 ***
    // ***)

    /**
     * (*** 新增函数: 轮询任务状态 ***)
     * @param {string} jobId 要查询的任务 ID
     * @param {string} filename 仅用于显示友好的消息
     */
    function pollJobStatus(jobId, filename) {
        // (定义一个函数来执行单次查询)
        const checkStatus = async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/upload/status/${jobId}`);
                const data = await response.json();

                // --- 步骤 3: 检查状态 ---

                // (*** 这是修复错误的关键逻辑 ***)

                if (data.status === 'finished') {
                    // --- 成功 ---
                    console.log("处理完成:", data.stats);

                    // 1. 恢复按钮
                    uploadBtn.disabled = false;
                    uploadBtn.innerHTML = '<i class="fas fa-upload"></i> 上传并处理';
                    uploadForm.reset();

                    // 2. 向用户显示成功信息 (*** 现在可以安全读取 stats ***)
                    const stats = data.stats; // `stats` 此时必定存在
                    const msg = `文件 "${filename}" 处理完成！\n找到 PDF: ${stats.pdf_found}\n处理: ${stats.processed}\n成功导入: ${stats.inserted}\n跳过(重复): ${stats.duplicates}`;
                    showNotification(msg, 'success');

                    // 3. (*** 解决“需要刷新”的问题 ***)
                    // 主动刷新列表
                    loadInvoices(searchInput.value); // (保持当前搜索)

                } else if (data.status === 'failed') {
                    // --- 失败 ---
                    console.error("处理失败:", data.error);

                    // 1. 恢复按钮
                    uploadBtn.disabled = false;
                    uploadBtn.innerHTML = '<i class="fas fa-upload"></i> 上传并处理';

                    // 2. 向用户显示错误信息
                    showNotification(`文件 "${filename}" 处理失败: \n${data.error}`, 'error');

                } else {
                    // --- 处理中 (queued 或 processing) ---
                    console.log("仍在处理中... 状态:", data.status);

                    // (更新按钮文本，让用户知道仍在处理)
                    uploadBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${data.status === 'queued' ? '排队中' : '解析中'}`;

                    // 2. 2秒后再次调用自己，继续轮询
                    setTimeout(checkStatus, 2000);
                }

            } catch (error) {
                // (处理轮询时的网络错误)
                console.error('轮询状态失败:', error);
                uploadBtn.disabled = false;
                uploadBtn.innerHTML = '<i class="fas fa-upload"></i> 上传并处理';
                showNotification(`查询处理状态时出错: ${error.message}`, 'error');
            }
        };

        // (立即开始第一次检查)
        checkStatus();
    }


    // (新) 上传 (*** 已重构为异步轮询 ***)
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault(); // 阻止表单默认提交

        if (!fileInput.files || fileInput.files.length === 0) {
            showNotification('未选择文件', 'error');
            return;
        }

        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('zip_file', file);

        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 上传中...';

        try {
            // --- 步骤 1: POST /upload ---
            const response = await fetch(`${API_BASE_URL}/upload`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json(); // (总是尝试解析 JSON)

            if (!response.ok) {
                // (显示后端返回的错误信息, e.g. 400 Bad Request)
                throw new Error(result.error || `服务器错误: ${response.status}`);
            }

            // --- 步骤 2: 检查 202 状态和 Job ID ---
            // (我们后端的代码返回 202 Accepted)
            if (response.status === 202 && result.job_id) {
                const jobId = result.job_id;

                // (更新 UI: "上传完成，正在后台处理...")
                showNotification(`文件 "${file.name}" 已上传，开始后台处理...`, 'success');

                // (*** 关键: 调用轮询器，而不是在这里刷新 ***)
                pollJobStatus(jobId, file.name);

                // (注意：按钮的恢复操作已移入 pollJobStatus 内部)

            } else {
                // (万一后端逻辑改了，没有返回 202 或 job_id)
                throw new Error(result.error || '上传失败，服务器未返回 Job ID。');
            }

        } catch (error) {
            // (这只捕获 /upload 这一步的失败)
            console.error('上传失败:', error);
            showNotification(`上传失败: ${error.message}`, 'error');
            // (在这里恢复按钮)
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="fas fa-upload"></i> 上传并处理';
        }

        // (*** 移除旧的 finally 块 ***)
    });

    // (*** //     *** 关键修改到此结束 ***
    // ***)


    // (新) 清空数据库 (此函数保持不变)
    clearDatabaseForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        if (!confirm('您确定要清空所有发票数据和PDF文件吗？此操作不可撤销。')) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/clear-all`, {
                method: 'POST'
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || '清空失败');

            showNotification('数据库和文件已清空', 'success');
            loadInvoices(); // 刷新

        } catch (error) {
            showNotification(`清空失败: ${error.message}`, 'error');
        }
    });


    // --- (新) 动态内容 (表格内) 的事件监听器 ---
    // (此函数保持不变)
    function addDynamicEventListeners() {

        // (新) 批量下载复选框逻辑
        const checkboxes = document.querySelectorAll('.invoice-checkbox');

        function updateDownloadButtonState() {
            const selectedCount = document.querySelectorAll('.invoice-checkbox:checked').length;
            downloadSelectedBtn.disabled = selectedCount === 0;
            downloadSelectedBtn.innerHTML = `<i class="fas fa-download"></i> 打包下载 (${selectedCount})`;
            // (更新全选框状态)
            selectAllCheckbox.checked = (checkboxes.length > 0 && selectedCount === checkboxes.length);
        }

        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', updateDownloadButtonState);
        });

        // (初始化按钮状态)
        updateDownloadButtonState();


        // (新) 编辑模态框逻辑
        document.querySelectorAll('.edit-btn').forEach(button => {
            button.addEventListener('click', function() {
                const data = this.dataset;

                // 1. 填充表单内容
                editIdDisplay.textContent = data.id;
                document.getElementById('edit-buyer_name').value = data.buyer;
                document.getElementById('edit-seller_name').value = data.seller;
                document.getElementById('edit-invoice_code').value = data.code;
                document.getElementById('edit-invoice_number').value = data.number;
                document.getElementById('edit-issue_date').value = data.date;
                document.getElementById('edit-amount').value = data.amount;
                document.getElementById('edit-total_amount').value = data.total_amount;

                // 2. 显示模态框
                modal.style.display = 'flex';
            });
        });

        // (新) 删除按钮逻辑
        document.querySelectorAll('.delete-btn').forEach(button => {
            button.addEventListener('click', async function() {
                const invoiceId = this.dataset.id;
                if (confirm(`您确定要删除发票 (ID: ${invoiceId}) 吗？`)) {
                    try {
                        const response = await fetch(`${API_BASE_URL}/invoices/${invoiceId}`, {
                            method: 'DELETE'
                        });
                        const result = await response.json();
                        if (!response.ok) throw new Error(result.error || '删除失败');

                        showNotification(`发票 ID ${invoiceId} 已删除。`, 'success');
                        loadInvoices(searchInput.value); // (刷新，并保持当前搜索)

                    } catch (error) {
                        showNotification(`删除失败: ${error.message}`, 'error');
                    }
                }
            });
        });
    }

    // (新) 全选框 (此函数保持不变)
    selectAllCheckbox.addEventListener('change', function() {
        const checkboxes = document.querySelectorAll('.invoice-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = this.checked;
        });
        // (触发一次更新)
        addDynamicEventListeners();
    });


    // (新) 批量下载提交 (此函数保持不变)
    downloadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const selectedCheckboxes = document.querySelectorAll('.invoice-checkbox:checked');
        const selectedIds = Array.from(selectedCheckboxes).map(cb => cb.value);

        if (selectedIds.length === 0) {
            showNotification('未选中任何发票', 'error');
            return;
        }

        downloadSelectedBtn.disabled = true;
        downloadSelectedBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> 打包中...`;

        try {
            const response = await fetch(`${API_BASE_URL}/download/zip`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ selected_ids: selectedIds })
            });

            if (!response.ok) {
                 const error = await response.json(); // (尝试读取 JSON 错误)
                 throw new Error(error.error || '打包失败');
            }

            // 将 blob 转换为可下载的文件
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = 'selected_invoices.zip';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

            // (取消全选)
            selectAllCheckbox.checked = false;
            addDynamicEventListeners();

        } catch(error) {
            showNotification(`打包下载失败: ${error.message}`, 'error');
        } finally {
            // (恢复按钮状态)
            addDynamicEventListeners();
        }
    });

    // (新) 模态框关闭按钮 (此函数保持不变)
    if(closeModalBtn) {
        closeModalBtn.addEventListener('click', () => modal.style.display = 'none');
    }
    window.addEventListener('click', (event) => {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    });

    // (新) 模态框保存 (提交) (此函数保持不变)
    editForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const invoiceId = editIdDisplay.textContent;

        // 从表单收集数据
        const data = {
            buyer_name: document.getElementById('edit-buyer_name').value,
            seller_name: document.getElementById('edit-seller_name').value,
            invoice_code: document.getElementById('edit-invoice_code').value,
            invoice_number: document.getElementById('edit-invoice_number').value,
            issue_date: document.getElementById('edit-issue_date').value,
            amount: document.getElementById('edit-amount').value,
            total_amount: document.getElementById('edit-total_amount').value
        };

        try {
            const response = await fetch(`${API_BASE_URL}/invoices/${invoiceId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || '更新失败');

            showNotification(`发票 ID ${invoiceId} 已更新。`, 'success');
            modal.style.display = 'none';
            loadInvoices(searchInput.value); // (刷新，并保持当前搜索)

        } catch (error) {
             showNotification(`更新失败: ${error.message}`, 'error');
        }
    });


    // --- (新) 初始加载 ---
    // (页面打开时，立即加载所有发票)
    loadInvoices();
});