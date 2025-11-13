# app/__init__.py
import os
from flask import Flask
from flask_cors import CORS
from .config import Config
from .database import create_db_and_table  # <-- 只需要导入这一个函数

def create_app():
    """
    应用工厂函数
    """
    app = Flask(__name__)

    # 1. 加载配置
    app.config.from_object(Config)

    # 2. 初始化 CORS (关键：允许前端从 file:// 或其他域访问)
    CORS(app, resources={r"/api/v1/*": {"origins": "*"}})

    # 3. 确保配置中定义的目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['EXTRACT_FOLDER'], exist_ok=True)

    # 4. 在应用上下文中创建数据库表
    # (确保在任何请求之前数据库已就绪)
    with app.app_context():
        create_db_and_table()  # <-- 此函数现在会创建 invoices 和 jobs 两个表

    # 5. 注册 API 蓝图 (Blueprint)
    from .api.routes import api_bp
    # 所有 API 路由都将以 /api/v1/ 开头
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    # 6. (可选) 添加一个根路由用于测试
    @app.route('/')
    def index():
        return "发票后端 API 正在运行。请访问 /api/v1/invoices 查看数据。"

    return app