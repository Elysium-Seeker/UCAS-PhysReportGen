import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import os

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'SimSun', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 模拟光电探测器实验数据
V = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0])
I = np.array([0.02, 0.45, 0.92, 1.38, 1.85, 2.30, 2.78, 3.25, 3.70, 4.15, 4.62])

def func(x, a, b):
    return a * x + b

popt, pcov = curve_fit(func, V, I)

plt.figure(figsize=(8, 6), dpi=150)
plt.scatter(V, I, color='red', label='原始数据')
plt.plot(V, func(V, *popt), color='blue', label=f'线性拟合: y={popt[0]:.4f}x+{popt[1]:.4f}')

plt.title('光电探测器伏安特性曲线', fontsize=14)
plt.xlabel('电压 U (V)', fontsize=12)
plt.ylabel('电流 I (mA)', fontsize=12)
plt.grid(True, linestyle='--', alpha=0.7)
plt.legend()

plt.savefig('sample_plot.png')
print("Sample plot generated: sample_plot.png")
