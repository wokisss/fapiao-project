import os
import zipfile
import shutil
import tempfile
from collections import deque


def recursive_extract_all_pdfs(zip_path, final_output_dir):
    """
    递归解压ZIP包。
    它会解压 `zip_path` 到 `final_output_dir`。
    如果解压出的文件还是ZIP包，它会再次解压它们（使用队列）。
    返回找到的PDF文件总数。
    (逻辑来自 app.py / jieyasuo.py)
    """
    pdf_files_found_count = 0

    # 使用一个临时目录来处理所有中间解压文件
    # (注意：我们是在一个 *已经* 是临时的目录 'temp_extract_dir' 中操作)
    # (为了安全，我们再创建一个临时的子目录)
    with tempfile.TemporaryDirectory() as processing_temp_dir:

        # 队列用于存储待解压的ZIP包
        zip_queue = deque([(zip_path, 0)])  # (压缩包路径, 嵌套层级)
        extraction_count = 0
        max_extractions = 20  # 防止无限递归或恶意ZIP炸弹

        while zip_queue and extraction_count < max_extractions:
            current_zip, current_level = zip_queue.popleft()
            extraction_count += 1

            # 为本次解压创建一个唯一的子目录
            current_extract_dir = os.path.join(processing_temp_dir, f"extract_{extraction_count}")
            os.makedirs(current_extract_dir, exist_ok=True)

            print(f"正在解压 (层级 {current_level}): {os.path.basename(current_zip)}")

            try:
                # 1. 解压
                with zipfile.ZipFile(current_zip, 'r') as zip_ref:
                    zip_ref.extractall(current_extract_dir)
            except Exception as e:
                print(f"解压失败: {e}")
                continue  # 跳过这个损坏的ZIP

            # 2. 遍历解压后的文件
            for root, dirs, files in os.walk(current_extract_dir):
                for file in files:
                    file_path = os.path.join(root, file)

                    if file.lower().endswith('.pdf'):
                        # 3. 如果是PDF，复制到 *最终* 输出目录
                        # (final_output_dir 是我们上传流程中的 'temp_extract_dir')

                        # 处理文件名冲突 (虽然在临时目录中不太可能，但保险起见)
                        target_path = os.path.join(final_output_dir, file)
                        counter = 1
                        while os.path.exists(target_path):
                            name, ext = os.path.splitext(file)
                            target_path = os.path.join(final_output_dir, f"{name}_{counter}{ext}")
                            counter += 1

                        shutil.copy2(file_path, target_path)
                        pdf_files_found_count += 1

                    elif file.lower().endswith(('.zip', '.rar', '.7z')):
                        # 4. 如果是嵌套的ZIP，加入队列
                        # (注意: .rar 和 .7z 需要额外库 (unrar, py7zr)，这里只处理 .zip)
                        if file.lower().endswith('.zip'):
                            print(f"  发现嵌套ZIP: {file} (加入队列)")
                            zip_queue.append((file_path, current_level + 1))

    print(f"解压完成，共找到 {pdf_files_found_count} 个PDF文件。")
    return pdf_files_found_count