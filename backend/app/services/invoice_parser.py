import re
import os
import shutil
import pdfplumber
from datetime import datetime
from flask import current_app
from .. import database as db


# --- 辅助函数 (保持不变) ---

def _parse_date(date_str):
    """
    一个辅助函数，用于将不同格式的日期字符串（如 "2020年12月23日" 或 "2020-12-23"）
    统一解析为 Python 的 date 对象。
    如果解析失败或输入为空，返回一个默认日期（1900-01-01）。
    """
    if not date_str:
        return datetime.strptime('1900-01-01', '%Y-%m-%d').date()
    try:
        if '年' in date_str:
            return datetime.strptime(date_str, '%Y年%m月%d日').date()
        else:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        # 如果格式不匹配
        print(f"日期格式错误: {date_str}，使用默认日期。")
        return datetime.strptime('1900-01-01', '%Y-%m-%d').date()


def _safe_float(float_str):
    """
    一个辅助函数，用于安全地将字符串转换为浮点数。
    它会清理掉货币符号 (¥, ￥), 空格, 和逗号, 然后再转换。
    如果转换失败，返回 0.0。
    """
    if not float_str:
        return 0.0
    try:
        # 将输入统一转为字符串，并移除首尾空格
        cleaned_str = str(float_str).strip()
        # 使用正则表达式移除所有 ¥, ￥, 空格, 和逗号
        cleaned_str = re.sub(r'[¥￥\s,]', '', cleaned_str)
        return float(cleaned_str)
    except (ValueError, TypeError):
        return 0.0


# --- 提取器 (*** 此处为关键修改 ***) ---

def _extract_fapiao_info(page, full_text, pdf_path):
    """
    【标准发票提取器】
    使用区域裁剪 (Bounding Box) 提取除 "价税合计" 之外的所有字段。
    "价税合计" (total_amount) 使用全局 full_text 搜索，这是最健壮的方法。
    """
    # 1. 获取页面尺寸
    width, height = page.width, page.height

    # 2. 定义 Bounding Box
    buyer_box = (width * 0.05, height * 0.20, width * 0.48, height * 0.40)
    meta_box = (width * 0.45, height * 0.05, width * 0.95, height * 0.30)
    amount_box = (width * 0.05, height * 0.40, width * 0.95, height * 0.70)
    seller_box = (width * 0.05, height * 0.70, width * 0.95, height * 0.95)

    try:
        # 3. 从每个区域提取文本
        buyer_text = page.crop(buyer_box).extract_text() or ""
        meta_text = page.crop(meta_box).extract_text() or ""
        amount_text = page.crop(amount_box).extract_text() or ""
        seller_text = page.crop(seller_box).extract_text() or ""  # 只用于提取销售方

    except Exception as e:
        print(f"页面裁剪失败 {pdf_path}: {e}")
        return []

    # 4. 从各自的文本块中提取信息 (保持不变)

    # 区域 1 (buyer_text):
    buyer_name_match = re.search(r'名\s*称\s*[:：]?\s*([^\n]+)', buyer_text, re.IGNORECASE)
    buyer_name = buyer_name_match.group(1).strip() if buyer_name_match else 'Unknown'
    buyer_tax_id_match = re.search(r'纳税人识别号\s*[:：]?\s*([A-Z0-9]+)', buyer_text, re.IGNORECASE)
    buyer_tax_id = buyer_tax_id_match.group(1).strip() if buyer_tax_id_match else ''

    # 区域 2 (meta_text):
    invoice_code_match = re.search(r'发票代码\s*[:：]?\s*(\w+)', meta_text)
    invoice_code = invoice_code_match.group(1) if invoice_code_match else 'Unknown'
    invoice_number_match = re.search(r'发票号码\s*[:：]?\s*(\w+)', meta_text)
    invoice_number = invoice_number_match.group(1) if invoice_number_match else 'Unknown'
    issue_date_match = re.search(r'开票日期\s*[:：]?\s*(\d{4}年\d{2}月\d{2}日|\d{4}-\d{2}-\d{2})', meta_text)
    issue_date = _parse_date(issue_date_match.group(1) if issue_date_match else None)

    # 区域 3 (amount_text):
    # "金额" (Amount) - 这是表格的 "合计"
    amount_match = re.search(r'合\s*计\s+[¥￥\s]*([\d\.]+)[\s\d\.]*', amount_text, re.IGNORECASE)
    amount = _safe_float(amount_match.group(1) if amount_match else None)

    # 区域 4 (seller_text):
    # "销售方名称"
    seller_name_match = re.search(r'名\s*称\s*[:：]?\s*([^\n]+)', seller_text, re.IGNORECASE)
    seller_name = seller_name_match.group(1).strip() if seller_name_match else 'Unknown'
    seller_tax_id_match = re.search(r'纳税人识别号\s*[:：]?\s*([A-Z0-9]+)', seller_text, re.IGNORECASE)
    seller_tax_id = seller_tax_id_match.group(1).strip() if seller_tax_id_match else ''

    # --- (*** 关键修复 (价税合计) - 新的多策略逻辑 ***) ---

    # "价税合计" (total_amount) 的提取是最不稳定的，因为它依赖于 OCR 文本流的顺序。
    # 我们尝试多种正则表达式策略，从最精确到最宽松。
    # 捕获组 r'([¥￥\s]*[\d,]+\.?\d*)' 用于捕获带或不带货币符号、逗号、小数的金额字符串
    # _safe_float 会负责清理这些捕获到的字符串

    total_amount_match = None
    total_amount_str = None

    # 策略 1: 查找 "价税合计(小写)" 或 "合 计(小写)"
    # 这是最强的模式，因为它同时包含了 "合计" 和 "(小写)"。
    # (改进：处理 "合 计" (带空格) 的情况)
    if not total_amount_match:
        total_amount_match = re.search(
            r'(?:价税合计\(小写\)|合\s*计\(小写\))\s*.*?([¥￥\s]*[\d,]+\.?\d*)',
            full_text,
            re.IGNORECASE | re.DOTALL
        )

    # 策略 2: 查找 "(小写)"，并抓取它后面的第一个数字
    # (这是原代码的逻辑，但使用了更健壮的数字捕获)
    if not total_amount_match:
        total_amount_match = re.search(
            r'\((?:小写)\)\s*.*?([¥￥\s]*[\d,]+\.?\d*)',
            full_text,
            re.IGNORECASE | re.DOTALL
        )

    # 策略 3: 查找 "价税合计" (不带小写)，并抓取它后面的数字
    # 适用于某些不规范的发票，使用 [^] 来跳过中间的非数字文本
    if not total_amount_match:
        total_amount_match = re.search(
            r'价税合计\s*[^¥￥\d]*([¥￥\s]*[\d,]+\.?\d*)',
            full_text,
            re.IGNORECASE | re.DOTALL
        )

    # --- 提取匹配结果 ---
    if total_amount_match:
        # 无论哪个策略成功，都从 group(1) 提取
        total_amount_str = total_amount_match.group(1)

    total_amount = _safe_float(total_amount_str)  # _safe_float(None) 会返回 0.0

    # --- (*** 修正结束 ***) ---

    summary_id = None  # 标准发票没有 summary_id

    # 5. 返回结果 (保持不变)
    return [
        ('invoice', summary_id, invoice_code, invoice_number, issue_date, amount, total_amount, buyer_name, buyer_tax_id, seller_name, seller_tax_id,
         pdf_path)]


def _extract_summary_info(full_text, tables, pdf_path):
    """
    【汇总单提取器】
    (此函数逻辑正确，保持不变)
    """
    infos = []
    summary_id_match = re.search(r'汇总单号\s*:\s*(\d+)', full_text, re.IGNORECASE | re.DOTALL)
    summary_id = summary_id_match.group(1) if summary_id_match else None
    buyer_name_match = re.search(r'购\s*买\s*方\s*名\s*称\s*[:：]?\s*([^\n]+)', full_text, re.IGNORECASE)
    buyer_name = buyer_name_match.group(1).strip() if buyer_name_match else 'Unknown'
    buyer_tax_id_match = re.search(r'纳税人识别号\s*[:：]?\s*([A-Z0-9]+)', full_text, re.IGNORECASE)
    buyer_tax_id = buyer_tax_id_match.group(1).strip() if buyer_tax_id_match else ''
    seller_name_match = re.search(r'销\s*售\s*方\s*名\s*称\s*[:：]?\s*([^\n]+)', full_text, re.IGNORECASE)
    seller_name = seller_name_match.group(1).strip() if seller_name_match else '收费公路管理方'
    seller_tax_id = '' # Summary invoices don't have seller tax id
    issue_date_match = re.search(r'(开票申请日期|开票日期)\s*[:：]?\s*(\d{4}-\d{2}-\d{2}|\d{4}年\d{2}月\d{2}日)',
                                 full_text, re.IGNORECASE | re.DOTALL)
    issue_date_str = issue_date_match.group(2) if issue_date_match else None
    issue_date = _parse_date(issue_date_str)

    total_amount_match = re.search(r'\(小写\)\s*￥?([0-9.]+)|交易金额\s*￥?([0-9.]+)', full_text,
                                   re.IGNORECASE | re.DOTALL)
    total_amount_str = total_amount_match.group(1) or total_amount_match.group(2) if total_amount_match else None
    total_amount = _safe_float(total_amount_str)

    for table in tables:
        if table and len(table) > 1:
            header = [cell.strip() for cell in table[0] if cell]
            if '票据代码' in ''.join(header) or '票据号码' in ''.join(header):
                for row in table[1:]:
                    clean_row = [cell.strip() for cell in row if cell]
                    if len(clean_row) >= 5:
                        invoice_code = clean_row[1] if len(clean_row) > 1 else 'Unknown'
                        invoice_number = clean_row[2] if len(clean_row) > 2 else 'Unknown'
                        amount_str = clean_row[3].replace('￥', '') if len(clean_row) > 3 else '0.0'
                        amount = _safe_float(amount_str)  # 汇总单的 amount 是行总计
                        infos.append((
                            'summary', summary_id, invoice_code, invoice_number,
                            issue_date, amount, total_amount,  # total_amount 是单据总计
                            buyer_name, buyer_tax_id, seller_name, seller_tax_id, pdf_path
                        ))
    return infos


def extract_invoice_info(pdf_path):
    """
    【主提取路由函数】
    (此函数逻辑正确，保持不变)
    使用 try...finally 块确保 pdf.close() 被显式调用，防止 PermissionError。
    """
    pdf = None  # (1) 在 try 之外定义
    try:
        # (2) 在 try 块中打开。如果 pdfplumber.open 失败, pdf 保持为 None
        pdf = pdfplumber.open(pdf_path)

        if not pdf.pages:
            print(f"PDF {pdf_path} 没有页面。")
            return []  # (finally 块会运行)

        page = pdf.pages[0]
        full_text = page.extract_text() or ""

        # --- 路由逻辑 ---
        if '收费公路通行费电子票据汇总单' in full_text:
            tables = page.extract_tables() or []
            return _extract_summary_info(full_text, tables, pdf_path)

        elif '电子普通发票' in full_text or '电子专用发票' in full_text:
            # *** 此处将调用更新后的函数 ***
            return _extract_fapiao_info(page, full_text, pdf_path)

        else:
            # (这是 apply.pdf 会进入的路径, 导致它被跳过)
            print(f"文件 {os.path.basename(pdf_path)} 类型未知，跳过。")
            return []

    except Exception as e:
        # (如果 pdfplumber.open 失败, e.g. 文件损坏, 会进入这里)
        print(f"提取 {pdf_path} 失败 (可能是损坏的文件或非PDF): {e}")
        return []

    finally:
        # (3) 无论 try 块如何退出 (return, except, or 正常结束),
        # 只要 pdf 不是 None (即 open 成功了), 就关闭文件。
        if pdf:
            pdf.close()
            # print(f"DEBUG: 显式关闭 {os.path.basename(pdf_path)}") # (调试时取消注释)


# --- 主服务函数 (保持不变) ---
def process_extracted_pdfs(temp_extract_dir):
    """
    (此函数逻辑正确，保持不变)
    处理临时目录中的所有PDF，将其解析并存入数据库
    """
    stats = {"processed": 0, "inserted": 0, "skipped": 0, "duplicates": 0}

    for filename in os.listdir(temp_extract_dir):
        if not filename.lower().endswith('.pdf'):
            continue

        temp_pdf_path = os.path.abspath(os.path.join(temp_extract_dir, filename))

        # 1. 提取信息 (infos 是一个列表)
        #    (现在 extract_invoice_info 已经修复了文件占用问题)
        infos = extract_invoice_info(temp_pdf_path)

        if not infos:
            # (如果 infos 为空, 意味着它是 'apply.pdf' 或其他非发票文件)
            stats["skipped"] += 1
            continue

        stats["processed"] += 1

        for info in infos:
            # 2. 确定永久路径 (防止文件名冲突)

            # --- (文件名逻辑已在您提供的代码中修复) ---
            permanent_filename = os.path.basename(temp_pdf_path)
            # --- (修复结束) ---

            permanent_path = os.path.join(current_app.config['EXTRACT_FOLDER'], permanent_filename)
            counter = 1
            while os.path.exists(permanent_path):
                name, ext = os.path.splitext(permanent_filename)
                new_name = f"{name}_{counter}{ext}"
                permanent_path = os.path.join(current_app.config['EXTRACT_FOLDER'], new_name)
                counter += 1

            # 3. 尝试插入数据库
            success, message = db.add_invoice_record(info, permanent_path)

            if success:
                # 4. 插入成功后，才复制文件
                try:
                    shutil.copy2(temp_pdf_path, permanent_path)
                    stats["inserted"] += 1
                except Exception as e:
                    print(f"文件复制失败 (但数据库已插入!): {e}")
            else:
                # 插入失败 (重复)
                if "已存在" in message:
                    stats["duplicates"] += 1
                else:
                    stats["skipped"] += 1  # 记为跳过（其他错误）

    return stats