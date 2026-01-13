"""
打包脚本
将项目打包为 zip 文件，方便分发
"""

import os
import zipfile
import shutil
from datetime import datetime

def package_project():
    # 当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 输出文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    output_filename = f"ReportGenerator_v2_{timestamp}.zip"
    output_path = os.path.join(current_dir, output_filename)
    
    print(f"正在打包到: {output_filename} ...")
    
    # 需要包含的文件和目录
    includes = [
        'app.py',
        'config.py',
        'requirements.txt',
        'run.bat',
        'README_PKG.txt',
        'static',
        'templates',
        'utils',
        'latex_template'
    ]
    
    # 需要排除的模式
    excludes = [
        '__pycache__',
        '*.pyc',
        '.DS_Store',
        'venv',
        '.git',
        '.idea',
        'uploads',  # 不包含用户数据
        'output'    # 不包含用户数据
    ]
    
    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for item in includes:
                item_path = os.path.join(current_dir, item)
                
                if not os.path.exists(item_path):
                    print(f"警告: 找不到 {item}")
                    continue
                
                if os.path.isfile(item_path):
                    zipf.write(item_path, arcname=item)
                    print(f"  添加文件: {item}")
                else:
                    for root, dirs, files in os.walk(item_path):
                        # 排除目录
                        dirs[:] = [d for d in dirs if d not in excludes and d != '__pycache__']
                        
                        for file in files:
                            # 排除文件
                            if file.endswith('.pyc') or file == '.DS_Store':
                                continue
                                
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, current_dir)
                            zipf.write(file_path, arcname=arcname)
            
            # 创建空的 uploads 和 output 目录结构
            zipinfo_uploads = zipfile.ZipInfo('uploads/')
            zipf.writestr(zipinfo_uploads, '')
            zipinfo_output = zipfile.ZipInfo('output/')
            zipf.writestr(zipinfo_output, '')
            
        print("\n打包完成！")
        print(f"文件大小: {os.path.getsize(output_path) / 1024 / 1024:.2f} MB")
        return output_path
        
    except Exception as e:
        print(f"打包失败: {e}")
        return None

if __name__ == "__main__":
    package_project()
