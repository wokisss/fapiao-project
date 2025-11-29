# app/database.py
import sqlite3
import json
import os
from flask import current_app, g


def get_db():
    """
    (*** 解决 "未解析的引用 'get_db'" ***)
    连接到数据库。
    如果 g.db 不存在，则创建一个新的连接。
    """
    if 'db' not in g:
        db_path = current_app.config.get('DATABASE_PATH', 'instance/invoices.db')

        # 确保数据库所在的目录 (instance) 存在
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row  # 允许通过列名访问数据
    return g.db


def close_db(e=None):
    """
    (标准 Flask 函数)
    关闭数据库连接。
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_app(app):
    """
    (标准 Flask 函数)
    在 app 上注册 close_db 函数，以便在 app 上下文销毁时自动关闭连接。
    """
    app.teardown_appcontext(close_db)
    # (您还可以在这里添加一个 CLI 命令来初始化数据库)
    # app.cli.add_command(init_db_command)


def create_db_and_table():
    """
    (*** 修改 ***)
    初始化数据库表。
    现在此函数会同时创建 'invoices' 和 'jobs' 两个表。
    """
    db = get_db()

    # 1. 创建发票表
    db.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            summary_id TEXT,
            invoice_code TEXT,
            invoice_number TEXT,
            issue_date DATE,
            amount REAL,
            total_amount REAL,
            buyer_name TEXT,
            buyer_tax_id TEXT,
            seller_name TEXT,
            seller_tax_id TEXT,
            file_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            -- 添加唯一约束防止重复 (发票代码 + 发票号码)
            UNIQUE(invoice_code, invoice_number)
        )
    ''')

    # 2. (*** 新增 ***) 创建后台任务表
    db.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            result TEXT,  -- 用于存储 JSON 格式的 stats 或错误信息
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    db.commit()


# --- 发票 (Invoices) 相关函数 ---

def add_invoice_record(info, permanent_path):
    """
    (由 invoice_parser.py 调用)
    向数据库中添加一条发票记录。
    """
    (type, summary_id, invoice_code, invoice_number, issue_date, amount, total_amount, buyer_name, buyer_tax_id, seller_name, seller_tax_id,
     pdf_path) = info

    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO invoices 
            (type, summary_id, invoice_code, invoice_number, issue_date, amount, total_amount, buyer_name, buyer_tax_id, seller_name, seller_tax_id, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (type, summary_id, invoice_code, invoice_number, issue_date, amount, total_amount, buyer_name, buyer_tax_id, seller_name, seller_tax_id,
             permanent_path)
        )
        db.commit()
        return True, "插入成功"
    except sqlite3.IntegrityError:
        # 触发了 UNIQUE 约束 (发票代码 + 发票号码)
        return False, "插入失败：发票已存在。"
    except Exception as e:
        db.rollback()
        return False, f"插入失败：{str(e)}"


def get_invoices(search_term=''):
    """
    (由 routes.py 调用)
    获取所有发票，支持模糊搜索。
    """
    db = get_db()
    query = "SELECT * FROM invoices"
    params = []
    if search_term:
        # 搜索多个字段
        like_term = f"%{search_term}%"
        query += """
            WHERE buyer_name LIKE ? 
            OR seller_name LIKE ? 
            OR invoice_number LIKE ? 
            OR summary_id LIKE ? 
            OR file_path LIKE ?
            OR buyer_tax_id LIKE ?
            OR seller_tax_id LIKE ?
        """
        params = [like_term] * 7

    query += " ORDER BY issue_date DESC, id DESC"

    cursor = db.execute(query, params)
    # 将 sqlite3.Row 转换为字典列表
    invoices = [dict(row) for row in cursor.fetchall()]
    return invoices


def get_invoice_by_id(invoice_id):
    """
    (由 routes.py 调用)
    根据 ID 获取单张发票。
    """
    db = get_db()
    cursor = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def update_invoice_record(invoice_id, data):
    """
    (由 routes.py 调用)
    更新发票信息。
    """
    db = get_db()
    try:
        db.execute(
            """
            UPDATE invoices SET 
            buyer_name = ?, seller_name = ?, issue_date = ?, amount = ?, total_amount = ?,
            buyer_tax_id = ?, seller_tax_id = ?
            WHERE id = ?
            """,
            (data.get('buyer_name'), data.get('seller_name'), data.get('issue_date'),
             data.get('amount'), data.get('total_amount'), data.get('buyer_tax_id'),
             data.get('seller_tax_id'), invoice_id)
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"更新失败: {e}")
        return False


def delete_invoice_record(invoice_id):
    """
    (由 routes.py 调用)
    删除发票记录 (并尝试删除关联文件)。
    """
    db = get_db()
    try:
        # 1. 先获取文件路径
        invoice = get_invoice_by_id(invoice_id)

        # 2. 从数据库删除
        db.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        db.commit()

        # 3. 尝试删除文件
        if invoice and invoice.get('file_path') and os.path.exists(invoice['file_path']):
            os.remove(invoice['file_path'])

        return True
    except Exception as e:
        db.rollback()
        print(f"删除失败: {e}")
        return False


def clear_all_invoices():
    """
    (由 routes.py 调用)
    清空所有发票和文件。
    """
    db = get_db()
    try:
        # 1. 获取所有文件路径
        cursor = db.execute("SELECT file_path FROM invoices")
        file_paths = [row['file_path'] for row in cursor.fetchall()]

        # 2. 清空数据库表
        db.execute("DELETE FROM invoices")
        db.execute("DELETE FROM jobs")  # (也清空 jobs 历史)
        db.commit()

        # 3. 遍历删除文件
        extract_folder = current_app.config['EXTRACT_FOLDER']
        for path in file_paths:
            if path and os.path.exists(path) and os.path.dirname(path) == extract_folder:
                os.remove(path)

        return True
    except Exception as e:
        db.rollback()
        print(f"清空失败: {e}")
        return False


# --- 任务 (Jobs) 相关函数 ---

def create_job(filename):
    """
    (由 routes.py 调用)
    在数据库中创建一个新任务，并返回 job_id。
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO jobs (filename, status) VALUES (?, 'queued')",
        (filename,)
    )
    db.commit()
    return cursor.lastrowid  # 返回新创建的任务 ID (int)


def update_job_status(job_id, status, result=None):
    """
    (由 routes.py 调用)
    更新任务的状态和结果。
    result 应该是一个字典 (stats) 或字符串 (error)。
    """
    db = get_db()
    # 如果 result 是一个字典 (stats)，将其转换为 JSON 字符串
    result_str = json.dumps(result) if isinstance(result, dict) else result

    db.execute(
        "UPDATE jobs SET status = ?, result = ? WHERE id = ?",
        (status, result_str, job_id)
    )
    db.commit()


def get_job_status(job_id):
    """
    (由 routes.py 调用)
    根据 ID 查询任务状态。
    """
    db = get_db()
    cursor = db.execute(
        "SELECT * FROM jobs WHERE id = ?",
        (job_id,)
    )
    job = cursor.fetchone()

    if job:
        # 将数据库行 (sqlite3.Row) 转换为字典，以便 jsonify
        job_dict = dict(job)
        # 尝试将 result 字段从 JSON 字符串解析回字典
        try:
            job_dict['result'] = json.loads(job_dict['result']) if job_dict['result'] else None
        except json.JSONDecodeError:
            pass  # 如果不是 JSON (例如纯错误字符串)，则保持原样
        return job_dict

    return None