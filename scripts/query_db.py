import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

# --- (新) 加载 .env 配置 ---
basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '../backend/.env')
load_dotenv(env_path)

db_config = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME', 'invoice_db')
}


# --- (结束) ---

# (逻辑来自您提供的 query_invoices.py)
def query_all_invoices():
    conn = None
    cursor = None
    if not db_config['password']:
        print("错误：未在 .env 文件中找到 DB_PASSWORD")
        return

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)  # 以字典形式返回结果
        query = "SELECT * FROM invoices ORDER BY id DESC"
        cursor.execute(query)
        results = cursor.fetchall()

        if not results:
            print(f"数据库 '{db_config['database']}' 中无发票记录。")
        else:
            print(f"数据库 '{db_config['database']}' 中的发票记录：")
            for row in results:
                print(f"- ID: {row['id']}")
                print(f"  类型: {row['type']}")
                print(f"  发票代码: {row['invoice_code']}")
                print(f"  发票号码: {row['invoice_number']}")
                print(f"  开票日期: {row['issue_date']}")
                print(f"  金额: {row['amount']}")
                print(f"  价税合计: {row['total_amount']}")
                print(f"  购买方: {row['buyer_name']}")
                print(f"  销售方: {row['seller_name']}")
                print(f"  文件路径: {row['file_path']}")
                print("---")
    except Error as e:
        print(f"查询错误: {e}")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# 执行查询
if __name__ == "__main__":
    print("正在查询数据库...")
    query_all_invoices()