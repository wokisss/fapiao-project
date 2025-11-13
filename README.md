# 发票管理系统 (前后端分离版)

这是一个重构后的发票管理系统，采用前后端分离架构。

-   **Backend**: Flask API 服务器，负责数据处理、PDF 解析和数据库操作。
-   **Frontend**: 静态 HTML/CSS/JS 界面，通过 API 与后端通信。

---

## 运行项目

### 1. 准备

1.  确保您已安装 Python 3 和 MySQL。
2.  在 MySQL 中创建一个数据库，例如：`CREATE DATABASE invoice_db;`

### 2. 运行后端 (Backend)

1.  **进入后端目录:**
    ```bash
    cd backend
    ```

2.  **创建并激活虚拟环境:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # (Windows: venv\Scripts\activate)
    ```

3.  **安装依赖:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **配置环境变量:**
    复制 `.env.example` (见下方) 为 `.env`，并填入您的 MySQL 凭证。
    ```
    DB_HOST=localhost
    DB_USER=root
    DB_PASSWORD=your_password
    DB_NAME=invoice_db
    UPLOAD_FOLDER=../uploads
    EXTRACT_FOLDER=../extracted_invoices
    ```

5.  **启动后端服务器:**
    ```bash
    python run.py
    ```
    服务器将在 `http://127.0.0.1:5000` 运行。

### 3. 运行前端 (Frontend)

1.  **无需服务器**。
2.  直接在您的浏览器中打开 `frontend/index.html` 文件。
3.  前端页面将自动连接到 `http://127.0.0.1:5000` 上的后端 API。