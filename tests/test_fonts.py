"""
测试字体配置
验证 Python 画图和 Latex 编译的字体支持
"""

import os
import sys
import shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 添加父目录到 path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.python_executor import PythonExecutor
from utils.latex_compiler import compile_latex, LaTeXCompiler
import config

def test_python_plot():
    print("Testing Python Plotting...")
    work_dir = os.path.join(config.OUTPUT_FOLDER, 'test_fonts')
    os.makedirs(work_dir, exist_ok=True)
    
    # 手动配置字体 (模拟 python_executor)
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    try:
        x = np.linspace(0, 10, 100)
        y = np.sin(x)
        
        plt.figure()
        plt.plot(x, y, label='正弦曲线')
        plt.title('测试中文标题 Check Font')
        plt.xlabel('X轴')
        plt.ylabel('Y轴')
        plt.legend()
        
        save_path = os.path.join(work_dir, 'test_plot.png')
        plt.savefig(save_path)
        print(f"  Plot saved to: {save_path}")
        return True
    except Exception as e:
        print(f"  Plotting failed: {e}")
        return False

def test_latex_compile():
    print("Testing LaTeX Compilation...")
    work_dir = os.path.join(config.OUTPUT_FOLDER, 'test_fonts')
    os.makedirs(work_dir, exist_ok=True)
    
    # 复制模板
    template_src = os.path.join(config.TEMPLATE_FOLDER, 'template.tex')
    template_dst = os.path.join(work_dir, 'main.tex')
    shutil.copy2(template_src, template_dst)
    
    # 复制字体
    print("  Copying fonts...")
    for font_file in os.listdir(config.FONTS_FOLDER):
        if font_file.endswith('.ttf'):
            shutil.copy2(
                os.path.join(config.FONTS_FOLDER, font_file),
                os.path.join(work_dir, font_file)
            )
            print(f"    Copied {font_file}")
    
    # 尝试编译
    print("  Compiling...")
    success, msg, pdf_path = compile_latex(template_dst, work_dir, config.FONTS_FOLDER)
    
    if success:
        print(f"  Compilation success! PDF: {pdf_path}")
        return True
    else:
        print(f"  Compilation failed: {msg}")
        return False

if __name__ == "__main__":
    print("-" * 50)
    py_success = test_python_plot()
    print("-" * 50)
    tex_success = test_latex_compile()
    print("-" * 50)
    
    if py_success and tex_success:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
