# app/api/routes.py
import os
import io
import tempfile
import zipfile
import shutil
import urllib.parse
import threading  # <-- 使用 threading
import traceback  # <-- 用于捕获错误
from flask import (
    Blueprint, request, jsonify, send_file, make_response, current_app
)
from .. import database as db
from ..services import zip_handler, invoice_parser
from ..services.invoice_parser import _parse_date, _safe_float

# 创建一个 API 蓝图
api_bp = Blueprint('api', __name__)


# --- 辅助函数 (保持不变) ---
def calculate_stats(invoices):
    """根据查询结果计算统计数据"""
    total_count = len(invoices)
    total_amount = sum(inv['amount'] for inv in invoices if inv['amount'])
    total_tax_amount = sum(inv['total_amount'] for inv in invoices if inv['total_amount'])
    return {
        'total_count': total_count,
        'total_amount': f"¥{total_amount:,.2f}",
        'total_tax_amount': f"¥{total_tax_amount:,.2f}"
    }


# --- (修改后的后台处理函数) ---

def process_zip_in_background(app, zip_path, job_id):
    """
    这个函数在一个单独的线程中运行，负责所有耗时的 PDF 处理工作。
    它现在接受一个 job_id 来向数据库报告状态。
    """
    # 线程没有 Flask 的应用上下文，必须手动创建
    with app.app_context():
        temp_extract_dir = tempfile.mkdtemp()
        print(f"[后台 Job {job_id}] 创建临时目录: {temp_extract_dir}")

        try:
            # 1. 更新状态为 "处理中"
            db.update_job_status(job_id, 'processing')

            # 2. 解压
            print(f"[后台 Job {job_id}] 开始解压: {zip_path}")
            pdf_count = zip_handler.recursive_extract_all_pdfs(zip_path, temp_extract_dir)
            print(f"[后台 Job {job_id}] 解压完成，找到 {pdf_count} 个PDF。")

            # 3. 解析 (耗时操作)
            print(f"[后台 Job {job_id}] 开始解析目录: {temp_extract_dir}")
            stats = invoice_parser.process_extracted_pdfs(temp_extract_dir)
            stats['pdf_found'] = pdf_count  # 补充统计
            print(f"[后台 Job {job_id}] 解析完成。 统计: {stats}")

            # 4. 更新状态为 "已完成"，并保存 stats 结果
            db.update_job_status(job_id, 'finished', result=stats)

        except Exception as e:
            # 5. 捕获异常，更新状态为 "失败"
            error_msg = traceback.format_exc()
            print(f"[后台 Job {job_id}] 处理失败: {str(e)}")
            db.update_job_status(job_id, 'failed', result=error_msg)

        finally:
            # 6. 清理临时目录
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
                print(f"[后台 Job {job_id}] 清理临时目录: {temp_extract_dir}")

            # 7. (推荐) 清理原始 ZIP 文件
            if os.path.exists(zip_path):
                os.remove(zip_path)
                print(f"[后台 Job {job_id}] 清理原始 ZIP: {zip_path}")


# --- 发票 CRUD API (保持不变) ---

@api_bp.route('/invoices', methods=['GET'])
def get_invoices_api():
    """ (R)ead: 获取发票列表 (带搜索) """
    search_term = request.args.get('search', '')
    invoices = db.get_invoices(search_term)
    stats = calculate_stats(invoices)
    for inv in invoices:
        if inv.get('issue_date'):
            inv['issue_date'] = inv['issue_date'].strftime('%Y-%m-%d')
    return jsonify({'invoices': invoices, 'stats': stats})


@api_bp.route('/invoices/<int:invoice_id>', methods=['PUT'])  # <-- (*** 修复: api_py -> api_bp ***)
def update_invoice_api(invoice_id):
    """ (U)pdate: 更新单张发票 """
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的 JSON 数据'}), 400
    try:
        data['issue_date'] = _parse_date(data.get('issue_date'))
        data['amount'] = _safe_float(data.get('amount'))
        data['total_amount'] = _safe_float(data.get('total_amount'))
    except Exception as e:
        return jsonify({'error': f'数据格式解析错误: {e}'}), 400
    if db.update_invoice_record(invoice_id, data):
        return jsonify({'success': True, 'message': f'发票 {invoice_id} 已更新'})
    else:
        return jsonify({'error': '更新失败'}), 500


@api_bp.route('/invoices/<int:invoice_id>', methods=['DELETE'])  # <-- (*** 修复: api_py -> api_bp ***)
def delete_invoice_api(invoice_id):
    """ (D)elete: 删除单张发票 """
    if db.delete_invoice_record(invoice_id):
        return jsonify({'success': True, 'message': f'发票 {invoice_id} 已删除'})
    else:
        return jsonify({'error': '删除失败'}), 500


# --- 文件和批量操作 API ---

@api_bp.route('/upload', methods=['POST'])
def upload_zip_api():
    """
    (C)reate: 上传 ZIP 文件
    (使用 数据库 + 线程 方案)
    """
    if 'zip_file' not in request.files:
        return jsonify({'error': '未找到 "zip_file" 字段'}), 400

    file = request.files['zip_file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    if not (file and file.filename.lower().endswith('.zip')):
        return jsonify({'error': '文件类型错误，请上传 ZIP 压缩包'}), 400

    # 1. 保存 ZIP 到 UPLOAD_FOLDER
    filename = file.filename
    zip_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    try:
        file.save(zip_path)
    except Exception as e:
        return jsonify({'error': f'保存 ZIP 文件失败: {e}'}), 500

    # 2. 在数据库中创建 Job 记录
    try:
        job_id = db.create_job(filename)
    except Exception as e:
        return jsonify({'error': f'创建任务失败: {e}'}), 500

    # 3. 启动后台线程，并传入 job_id
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=process_zip_in_background,
        args=(app, zip_path, job_id)  # <-- 传入 job_id
    )
    thread.start()

    # 4. 立即返回响应，包含 job_id
    return jsonify({
        'success': True,
        'message': '文件已上传，正在后台处理...',
        'job_id': job_id  # <-- 返回 job_id
    }), 202  # 202 Accepted 状态码


@api_bp.route('/upload/status/<int:job_id>', methods=['GET'])
def get_upload_status_api(job_id):
    """
    (*** 新增 API ***)
    (R)ead: 轮询此 API 以检查后台任务的状态
    GET /api/v1/upload/status/<job_id>
    """
    # 1. 从数据库中根据 ID 获取任务
    job = db.get_job_status(job_id)

    if job is None:
        return jsonify({'status': 'not_found', 'message': '未找到该任务'}), 404

    # 2. 根据状态返回不同信息
    status = job.get('status')
    result = job.get('result')

    if status == 'finished':
        return jsonify({
            'status': 'finished',
            'message': '处理完成',
            'stats': result  # <-- result 字段包含 stats 字典
        })
    elif status == 'failed':
        return jsonify({
            'status': 'failed',
            'message': '处理失败',
            'error': result  # <-- result 字段包含错误信息
        })
    else:
        # 'queued' 或 'processing'
        return jsonify({
            'status': status,
            'message': '正在处理中，请稍候...'
        })


# --- (其他下载和清空 API 保持不变) ---

@api_bp.route('/download/<int:invoice_id>', methods=['GET'])
def download_file_api(invoice_id):
    """ (R)ead: 下载单个 PDF """
    invoice = db.get_invoice_by_id(invoice_id)
    if not (invoice and invoice.get('file_path') and os.path.exists(invoice['file_path'])):
        return jsonify({'error': '文件未找到或路径无效'}), 404
    file_path = invoice['file_path']
    download_name = os.path.basename(file_path)
    if not download_name.lower().endswith(('.pdf', '.zip', '.jpg', '.png')):
        new_name = invoice.get('invoice_number') or invoice.get('summary_id') or f"invoice_{invoice_id}"
        download_name = f"{new_name}.pdf"
    try:
        response = make_response(send_file(file_path, as_attachment=True, download_name=download_name))
        encoded_filename = urllib.parse.quote(download_name, safe='')
        response.headers["Content-Disposition"] = (
            f"attachment; filename=\"{download_name}\"; filename*=UTF-8''{encoded_filename}"
        )
        return response
    except Exception as e:
        return jsonify({'error': f'发送文件时出错: {e}'}), 500


@api_bp.route('/download/zip', methods=['POST'])
def download_selected_zip_api():
    """ (R)ead: 批量下载 ZIP """
    data = request.get_json()
    if not data or 'selected_ids' not in data:
        return jsonify({'error': '无效的 JSON 数据, 需要 "selected_ids" 列表'}), 400
    selected_ids = data.get('selected_ids')
    if not isinstance(selected_ids, list) or len(selected_ids) == 0:
        return jsonify({'error': '"selected_ids" 必须是一个非空列表'}), 400
    file_paths = []
    for invoice_id in selected_ids:
        try:
            invoice = db.get_invoice_by_id(int(invoice_id))
            if invoice and invoice.get('file_path') and os.path.exists(invoice['file_path']):
                file_paths.append(invoice['file_path'])
        except ValueError:
            pass
    if not file_paths:
        return jsonify({'error': '未找到所选 ID 对应的任何有效文件'}), 404
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in file_paths:
            filename = os.path.basename(file_path)
            if not filename.lower().endswith('.pdf'):
                filename = f"{filename}.pdf"
            zf.write(file_path, filename)
    memory_file.seek(0)
    download_name = "selected_invoices.zip"
    response = make_response(memory_file.read())
    response.headers['Content-Type'] = 'application/zip'
    encoded_filename = urllib.parse.quote(download_name, safe='')
    response.headers["Content-Disposition"] = (
        f"attachment; filename=\"{download_name}\"; filename*=UTF-8''{encoded_filename}"
    )
    return response


@api_bp.route('/clear-all', methods=['POST'])
def clear_all_api():
    """ (D)elete: 清空所有数据 """
    if db.clear_all_invoices():
        return jsonify({'success': True, 'message': '数据库和 PDF 文件已清空'})
    else:
        return jsonify({'error': '清空数据库失败'}), 500