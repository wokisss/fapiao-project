# app/tasks.py
import os
import tempfile
import shutil
from . import create_app  # 导入您的 app 工厂
from .services import zip_handler, invoice_parser


def process_zip_task(zip_path, app_config_dict):
    """
    【后台任务】这是在 RQ Worker 进程中执行的函数。
    它负责所有耗时的 PDF 处理工作。

    这个函数的内容 = 您之前在 routes.py 中定义的 process_zip_in_background
    """

    # 1. 【关键】在 Worker 中重建 App 上下文
    # 因为 Worker 是一个独立进程，它没有 Flask 的 Web 上下文。
    # 我们必须创建一个新的 App 实例并推入上下文。
    app = create_app()
    # (如果 create_app 需要配置, 您可能需要: app = create_app(app_config_dict))

    with app.app_context():
        # 现在 `invoice_parser` 内部的 `current_app.config['EXTRACT_FOLDER']`
        # 和 `db` 模块都可以正常工作了。

        temp_extract_dir = tempfile.mkdtemp()
        print(f"[RQ Task] 开始处理: {zip_path}")
        print(f"[RQ Task] 临时目录: {temp_extract_dir}")

        try:
            # 2. 解压 (调用您已有的服务)
            pdf_count = zip_handler.recursive_extract_all_pdfs(zip_path, temp_extract_dir)
            print(f"[RQ Task] 解压完成, 找到 {pdf_count} 个PDF。")

            # 3. 解析 (耗时操作)
            # (此函数已在上一轮修复，可以安全地关闭文件)
            stats = invoice_parser.process_extracted_pdfs(temp_extract_dir)
            stats['pdf_found'] = pdf_count  # 补充解压统计

            print(f"[RQ Task] 解析完成。 统计: {stats}")

            # 4. 【关键】返回结果
            # 这个 'stats' 对象将被 RQ 序列化并存入 Redis，
            # 供 /upload/status 接口查询。
            return stats

        except Exception as e:
            print(f"[RQ Task] 任务失败: {e}")
            import traceback
            traceback.print_exc()
            # 抛出异常, RQ 会将任务标记为 'failed' 并存储异常信息
            raise e

        finally:
            # 5. 清理临时目录
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
                print(f"[RQ Task] 清理临时目录: {temp_extract_dir}")

            # 6. (推荐) 清理原始的 ZIP 文件
            if os.path.exists(zip_path):
                os.remove(zip_path)
                print(f"[RQ Task] 清理原始 ZIP: {zip_path}")