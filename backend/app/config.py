import os
from dotenv import load_dotenv

# .env 文件位于 backend/ 目录中，所以路径是 ../.env
# (如果 .env 在 backend/ 目录中，路径就是 .env)
# 我们假设 .env 在 backend 目录中
basedir = os.path.abspath(os.path.dirname(__file__))

# --- (重要) 修改这里的 .env 路径 ---
# 假设 .env 文件在 fapiao-project/backend/ 目录中
# (如果 .env 在 fapiao-project/ 根目录, 路径应为 os.path.join(basedir, '../.env'))
env_path = os.path.join(basedir, '../.env') # 假设 .env 在 fapiao-project 根目录
# 如果您把 .env 放在了 backend/ 目录中, 请使用下面这行:
# env_path = os.path.join(basedir, '.env')

load_dotenv(env_path)

class Config:
    """
    从环境变量加载配置
    """
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-default-secret-key'

    # 数据库配置 (从 .env 单独加载)
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_NAME = os.environ.get('DB_NAME', 'invoice_db')

    # 路径配置
    UPLOAD_FOLDER = os.path.abspath(os.environ.get('UPLOAD_FOLDER', os.path.join(basedir, '../../uploads')))
    EXTRACT_FOLDER = os.path.abspath(os.environ.get('EXTRACT_FOLDER', os.path.join(basedir, '../../extracted_invoices')))

    # --- (新添加) ---
    # 创建一个字典，供 database.py 使用
    # (这解决了 KeyError: 'DB_CONFIG' 问题)
    DB_CONFIG = {
        'host': DB_HOST,
        'user': DB_USER,
        'password': DB_PASSWORD,
        'database': DB_NAME
    }
    # --- (添加结束) ---


    @staticmethod
    def get_db_config():
        """获取用于 mysql.connector 的配置字典"""
        # (现在这个方法只是返回上面创建的字典)
        return Config.DB_CONFIG