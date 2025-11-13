import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

# --- (新) 加载 .env 配置 ---
# (假设此脚本在 scripts/ 目录下运行, .env 在上一级的 backend/ 目录中)
# (或者，更简单，我们假设 .env 在项目根目录)
basedir = os.path.abspath(os.path.dirname(__file__))
# (假设 .env 在 backend/ 目录中)
env_path = os.path.join(basedir, '../backend/.env')
# (如果 .env 在项目根目录)
# env_path = os.path.join(basedir, '../.env')

load_dotenv(env_path)

db_config = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME', 'invoice_db')
}


# --- (结束) ---

# (逻辑来自您提供的 clear_invoices.py)
def clear_invoices_table():
    conn = None
    cursor = None
    if not db_config['password']:
        print("错误：未在 .env 文件中找到 DB_PASSWORD")
        return

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        truncate_query = "TRUNCATE TABLE invoices"
        cursor.execute(truncate_query)
        conn.commit()
        print(f"数据库 '{db_config['database']}' 中的 'invoices' 表已清空。")

        # (我们也可以在这里添加清空 extracted_invoices 目录的逻辑)

    except Error as e:
        print(f"清空错误: {e}")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# 执行清空
if __name__ == "__main__":
    print("正在尝试清空数据库...")
    clear_invoices_table()