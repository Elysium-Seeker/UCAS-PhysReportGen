"""
大物实验报告生成器 - Flask 应用主入口
支持 AI 报告生成、Python 自动画图、PDF 提取、历史记录
"""

import os
import uuid
import shutil
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename

import config
from utils.latex_compiler import compile_latex, LaTeXCompiler
from utils.template_processor import TemplateProcessor
from utils.report_generator import create_generator, OpenAIBackend, ReportGenerator
from utils.pdf_extractor import extract_text_from_pdf, extract_guide_content
from utils.python_executor import PythonExecutor, extract_python_code_from_ai_response, generate_figure_latex
from utils.history_manager import HistoryManager

# 创建 Flask 应用
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER

# 确保目录存在
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(config.OUTPUT_FOLDER, exist_ok=True)

# 存储会话数据
sessions = {}

# API 配置（运行时）
api_config = {
    'url': '',
    'key': '',
    'model': 'gpt-4o'
}

# 历史记录管理器
history_manager = HistoryManager(config.OUTPUT_FOLDER)

def log_debug(message):
    """记录调试信息到文件"""
    log_file = os.path.join(config.OUTPUT_FOLDER, "debug.log")
    with open(log_file, "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {message}\n")

log_debug("服务器启动/重启")


def allowed_file(filename, extensions=None):
    """检查文件扩展名是否允许"""
    if extensions is None:
        extensions = config.ALLOWED_EXTENSIONS
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions


@app.route('/')
def index():
    """主页"""
    return render_template('index.html', default_info=config.DEFAULT_STUDENT_INFO)


@app.route('/api/check-latex')
def check_latex():
    """检查 LaTeX 是否已安装"""
    compiler = LaTeXCompiler()
    installed, message = compiler.check_installation()
    return jsonify({
        'installed': installed,
        'message': message
    })


@app.route('/api/config', methods=['POST'])
def save_config():
    """保存 API 配置"""
    global api_config
    data = request.json
    
    api_config['url'] = data.get('url', '')
    api_config['key'] = data.get('key', '')
    api_config['model'] = data.get('model', 'gpt-4o')
    
    return jsonify({
        'success': True,
        'message': 'API 配置已保存'
    })


@app.route('/api/upload', methods=['POST'])
def upload_files():
    """上传文件"""
    if 'files' not in request.files:
        return jsonify({'success': False, 'message': '没有文件上传'}), 400
    
    files = request.files.getlist('files')
    file_type = request.form.get('type', 'other')  # guide, data_sheet, preview_report
    session_id = request.form.get('session_id')
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # 创建会话目录
    session_dir = os.path.join(config.UPLOAD_FOLDER, session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    uploaded_files = []
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            # 获取原始扩展名
            ext = os.path.splitext(file.filename)[1].lower()
            if not ext:
                # 如果没有扩展名 (虽然 allowed_file 应该过滤了)，尝试从 secure_filename 获取
                # 或者直接跳过
                continue

            # 使用 UUID 生成安全的文件名，保留原始扩展名
            safe_name = str(uuid.uuid4())
            filename = f"{file_type}_{safe_name}_{datetime.now().strftime('%H%M%S')}{ext}"
            filepath = os.path.join(session_dir, filename)
            
            file.save(filepath)
            uploaded_files.append({
                'name': file.filename, # 存储原始文件名供展示
                'saved_name': filename, # 存储保存的文件名
                'path': filepath,
                'type': file_type
            })
    
    # 更新会话数据
    if session_id not in sessions:
        sessions[session_id] = {'files': {}}
    
    if file_type not in sessions[session_id]['files']:
        sessions[session_id]['files'][file_type] = []
    sessions[session_id]['files'][file_type].extend(uploaded_files)
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'files': uploaded_files
    })


import threading
import time

# =====================================================
# 任务管理器 (简单内存版)
# =====================================================

class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.lock = threading.Lock()
    
    def create_task(self):
        task_id = str(uuid.uuid4())
        with self.lock:
            self.tasks[task_id] = {
                'id': task_id,
                'status': 'pending', # pending, processing, completed, failed
                'progress': 0,
                'message': '任务已创建',
                'result': None,
                'error': None,
                'created_at': datetime.now()
            }
        return task_id
    
    def update_progress(self, task_id, progress, message=None):
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]['progress'] = progress
                self.tasks[task_id]['status'] = 'processing'
                if message:
                    self.tasks[task_id]['message'] = message
    
    def complete_task(self, task_id, result):
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]['status'] = 'completed'
                self.tasks[task_id]['progress'] = 100
                self.tasks[task_id]['message'] = '任务完成'
                self.tasks[task_id]['result'] = result
    
    def fail_task(self, task_id, error):
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]['status'] = 'failed'
                self.tasks[task_id]['message'] = str(error)
                self.tasks[task_id]['error'] = str(error)
                
    def get_task(self, task_id):
        with self.lock:
            return self.tasks.get(task_id)

task_manager = TaskManager()

def run_generation_task(task_id, session_id, student_info, experiment_info, additional_requirements, 
                       files_context, api_settings):
    """后台运行的生成任务"""
    try:
        task_manager.update_progress(task_id, 5, "正在初始化工作环境...")
        
        # 1. 准备工作目录
        work_dir = os.path.join(config.OUTPUT_FOLDER, session_id)
        os.makedirs(work_dir, exist_ok=True)
        fig_dir = os.path.join(work_dir, 'Fig')
        os.makedirs(fig_dir, exist_ok=True)
        
        # 2. 复制模板和字体
        task_manager.update_progress(task_id, 10, "正在准备模板文件...")
        template_src = os.path.join(config.TEMPLATE_FOLDER, 'template.tex')
        template_dst = os.path.join(work_dir, 'main.tex')
        shutil.copy2(template_src, template_dst)
        
        # 复制字体
        for font_file in os.listdir(config.FONTS_FOLDER):
            if font_file.endswith('.ttf'):
                shutil.copy2(
                    os.path.join(config.FONTS_FOLDER, font_file),
                    os.path.join(work_dir, font_file)
                )

        # 3. 处理输入文件
        task_manager.update_progress(task_id, 15, "正在处理上传文件...")
        guide_text = None
        data_sheet_images = []
        preview_report_images = []
        
        # 处理实验指导书 PDF
        if files_context.get('guide_path') and os.path.exists(files_context['guide_path']):
            print(f"DEBUG: 正在处理指导书: {files_context['guide_path']}")
            task_manager.update_progress(task_id, 20, "正在从指导书中提取文本...")
            guide_content = extract_guide_content(files_context['guide_path'])
            if guide_content and guide_content.get('full_text'):
                guide_text = guide_content['full_text'][:32768] # 再次增加限制到 32k
                print(f"DEBUG: 提取成功，文本长度: {len(guide_text)}")
            else:
                print(f"DEBUG: 提取失败或内容为空")
        else:
            print(f"DEBUG: 跳过指导书提取，路径: {files_context.get('guide_path')}")        
        # 复制图片并收集路径
        for img_path in files_context.get('data_sheets', []):
            if os.path.exists(img_path):
                filename = os.path.basename(img_path)
                shutil.copy2(img_path, os.path.join(work_dir, filename))
                data_sheet_images.append(os.path.join(work_dir, filename))
                
        for img_path in files_context.get('previews', []):
            if os.path.exists(img_path):
                filename = os.path.basename(img_path)
                shutil.copy2(img_path, os.path.join(work_dir, filename))
                preview_report_images.append(os.path.join(work_dir, filename))

        # 4. AI 生成内容
        task_manager.update_progress(task_id, 30, "AI 正在分析数据并生成报告内容 (Step 1/3)...")
        
        latex_content = None
        generated_figures = []
        
        if api_settings['url'] and api_settings['key']:
            backend = OpenAIBackend(
                api_key=api_settings['key'],
                api_url=api_settings['url'],
                model=api_settings['model']
            )
            generator = ReportGenerator(backend)
            
            # 生成 LaTeX 内容
            latex_content = generator.generate_report_content(
                experiment_guide=guide_text,
                data_sheet_images=data_sheet_images,
                additional_requirements=additional_requirements
            )
            
            # 生成图表
            log_debug(f"Step: 开始生成图表, session_id: {session_id}")
            task_manager.update_progress(task_id, 70, "AI 正在生成画图代码...")
            plot_prompt = build_plotting_prompt(
                experiment_info['experiment_name'],
                latex_content
            )
            
            plot_response = generator.backend.generate(plot_prompt, data_sheet_images[:2])
            log_debug(f"AI Plot Response: {plot_response[:500]}...") # 只记录开头
            
            python_data_code, python_plot_code = extract_python_code_from_ai_response(plot_response)
            log_debug(f"Extracted data_code: {bool(python_data_code)}, plot_code: {bool(python_plot_code)}")
            
            if python_plot_code:
                task_manager.update_progress(task_id, 80, "正在执行 Python 作图...")
                executor = PythonExecutor(work_dir)
                success, msg, generated_figures = executor.execute_plotting_code(
                    python_plot_code, 
                    python_data_code
                )
                log_debug(f"Plot Execution: success={success}, msg={msg}, figures={len(generated_figures)}")
            else:
                log_debug("未提取到 Python 画图代码")

        # 5. 整合模板
        task_manager.update_progress(task_id, 85, "正在整合报告内容...")
        processor = TemplateProcessor(template_dst)
        
        # 处理日期
        date_str = experiment_info['date']
        try:
            if '-' in date_str:
                parts = date_str.split('-')
                experiment_info['year'] = parts[0]
                experiment_info['month'] = parts[1].lstrip('0') or parts[1]
                experiment_info['day'] = parts[2].lstrip('0') or parts[2]
        except:
            pass # 保持默认

        template_data = {}
        template_data.update(student_info)
        template_data['experiment_name'] = experiment_info['experiment_name']
        template_data['supervisor'] = experiment_info['supervisor']
        template_data['year'] = experiment_info.get('year', str(datetime.now().year))
        template_data['month'] = experiment_info.get('month', str(datetime.now().month))
        template_data['day'] = experiment_info.get('day', str(datetime.now().day))
        template_data['room'] = experiment_info['room']
        template_data['is_makeup'] = '$\\square$\\hspace{-1em}$\\surd$' if experiment_info.get('is_makeup') else '$\\square$'
        
        # 基础模板处理
        content = processor.process(template_data)
        
        # 整合 AI 内容
        if latex_content:
            content = integrate_ai_content(content, latex_content)
            
        # 整合图表
        if generated_figures:
            figure_latex = generate_figure_latex(generated_figures, work_dir)
            content = add_figures_to_content(content, figure_latex)
            
        # 整合附录图片
        content = add_appendix_images(content, work_dir, data_sheet_images, preview_report_images)
        
        # 写入文件
        with open(template_dst, 'w', encoding='utf-8') as f:
            f.write(content)
            
        # 6. 编译 PDF
        task_manager.update_progress(task_id, 90, "正在编译 PDF...")
        success, message, pdf_path = compile_latex(
            template_dst,
            work_dir,
            config.FONTS_FOLDER
        )
        
        if success:
            # 保存会话信息
            sessions[session_id] = sessions.get(session_id, {})
            sessions[session_id].update({
                'work_dir': work_dir,
                'tex_file': template_dst,
                'pdf_file': pdf_path
            })
            
            # 添加历史记录
            history_manager.add_record(
                session_id=session_id,
                experiment_name=experiment_info['experiment_name'],
                student_name=student_info['name'],
                pdf_path=pdf_path,
                tex_path=template_dst,
                additional_info={
                    'supervisor': experiment_info['supervisor'],
                    'date': experiment_info['date'],
                    'has_figures': len(generated_figures) > 0
                }
            )
            
            task_manager.complete_task(task_id, {
                'success': True,
                'session_id': session_id,
                'pdf_url': f'/api/preview/{session_id}',
                'figures_generated': len(generated_figures)
            })
        else:
            task_manager.fail_task(task_id, f"PDF 编译失败: {message}")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        task_manager.fail_task(task_id, f"生成过程出错: {str(e)}")


@app.route('/api/generate', methods=['POST'])
def generate_report():
    """生成报告 (启动后台任务)"""
    data = request.json
    if not data:
        return jsonify({'error': '无数据提交'}), 400
        
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': '缺少会话 ID'}), 400
    
    # 提取信息
    student_info = {
        'name': data.get('name', ''),
        'student_id': data.get('student_id', ''),
        'class_num': data.get('class_num', '1'),
        'group_num': data.get('group_num', '01'),
        'seat_num': data.get('seat_num', '1')
    }
    
    experiment_info = {
        'experiment_name': data.get('experiment_name', ''),
        'supervisor': data.get('supervisor', ''),
        'date': data.get('date', datetime.now().strftime('%Y-%m-%d')),
        'room': data.get('room', ''),
        'is_makeup': data.get('is_makeup', False)
    }
    
    additional_requirements = data.get('additional_requirements', '')
    
    # API 设置
    api_settings = {
        'url': data.get('api_url') or api_config['url'],
        'key': data.get('api_key') or api_config['key'],
        'model': data.get('api_model') or api_config['model']
    }
    
    # 文件路径上下文
    files_context = {
        'guide_path': None,
        'data_sheets': [],
        'previews': []
    }
    
    if session_id in sessions and 'files' in sessions[session_id]:
        files = sessions[session_id]['files']
        # 指导书
        if 'guide' in files:
            for f in files['guide']:
                if f['path'].lower().endswith('.pdf'):
                    files_context['guide_path'] = f['path']
                    break
        # 数据表
        if 'data_sheet' in files:
            files_context['data_sheets'] = [f['path'] for f in files['data_sheet']]
        # 预习报告
        if 'preview_report' in files:
            files_context['previews'] = [f['path'] for f in files['preview_report']]

    # 创建并启动任务
    task_id = task_manager.create_task()
    
    thread = threading.Thread(
        target=run_generation_task,
        args=(
            task_id, 
            session_id, 
            student_info, 
            experiment_info, 
            additional_requirements,
            files_context,
            api_settings
        )
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': '任务已启动'
    })


@app.route('/api/task/<task_id>')
def get_task_status(task_id):
    """获取任务状态"""
    task = task_manager.get_task(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
        
    return jsonify({
        'success': True,
        'task': task
    })


def build_generation_prompt(experiment_name, student_info, experiment_info, additional_requirements, guide_text=None):
    """构建 AI 生成提示"""
    guide_section = ""
    if guide_text:
        guide_section = f"""
## 实验指导书内容（已从 PDF 提取）
{guide_text[:6000]}
"""
    
    return f"""你是一个专业的物理实验报告撰写助手。请根据提供的数据记录表照片，为以下实验生成完整的 LaTeX 格式实验报告内容。

## 实验信息
- 实验名称: {experiment_name}
- 学生姓名: {student_info['name']}
- 实验日期: {experiment_info['date']}
{guide_section}
## 要求
1. 从数据记录表照片中准确识别并提取所有实验数据
2. 生成完整的实验报告，包括：
   - \\section{{实验目的}} - 用 enumerate 环境列出
   - \\section{{实验器材}} - 列出使用的仪器设备  
   - \\section{{实验原理}} - 详细说明原理，包含公式（使用 equation 或 align 环境）
   - \\section{{实验步骤}} - 用 enumerate 环境详细列出
   - \\section{{实验结果与数据处理}} - 包含所有数据表格（使用 table 和 tabular 环境）和分析计算
   - \\section{{思考题}} - 如果有思考题请回答
   - \\section{{总结}} - 总结实验收获和误差分析

3. 数据表格格式要求：
   - 使用 \\begin{{table}}[H] 环境
   - 表格要有标题 \\caption{{}}
   - 对于宽表格使用 adjustbox 包
   - 数值要精确到合适的小数位
   - 计算相关物理量并列出计算过程

4. 公式要求：
   - 重要公式使用 equation 环境并编号
   - 推导过程使用 align 环境
   - 使用正确的物理单位

{f'5. 额外要求: {additional_requirements}' if additional_requirements else ''}

请只返回 LaTeX 代码内容（从 \\section{{实验目的}} 开始），不要包含文档头部。
"""


def build_plotting_prompt(experiment_name, latex_content):
    """构建 Python 画图提示"""
    return f"""根据以下实验报告中的每个数据表格，分别生成 Python 绘图代码。

## 实验名称
{experiment_name}

## 报告内容
{latex_content[:8000]}

## 要求
1. **一表一图**：请仔细分析报告中的所有数据表格，为每一个独立的表格生成一个绘图代码块。
2. **命名规范**：每个绘图代码末尾，请使用 `plt.savefig('plot_1.png')`, `plt.savefig('plot_2.png')` 等，按表格顺序命名。
3. **代码细节**：包含数据定义、绘图逻辑（连线或拟合）、中文标签和标题（使用 SimHei 字体）。
4. **输出格式**：请返回多个 ```python ... ``` 代码块，每个块代表一个图表的完整生成逻辑。不要包含其他文字说明。
"""


def add_figures_to_content(content, figure_latex_list_str):
    """将生成的图表交替插入到对应的表格后面"""
    import re
    
    # 提取所有的 figure 环境
    figs = re.findall(r'\\begin\{figure\}.*?\\end\{figure\}', figure_latex_list_str, re.DOTALL)
    
    # 将所有 figure 里的 [htbp] 强制改为 [H]
    figs = [re.sub(r'\\begin\{figure\}\[[^\]]+\]', r'\\begin{figure}[H]', f) for f in figs]

    # 查找所有的 table 环境的结尾
    table_pattern = r'(\\end\{table\})'
    table_matches = list(re.finditer(table_pattern, content))
    
    if not table_matches or not figs:
        # 如果没找到表格或者没图像，回退到原始位置插入
        if figs:
            # 尝试在“思考题”前插入
            pattern = r'(\\section\{思考题\})|(\\section\{总结\})|(% BEGIN:appendix)'
            match = re.search(pattern, content)
            if match:
                insert_pos = match.start()
                figs_text = "\n\n\\subsection{数据分析图表}\n" + "\n\n".join(figs) + "\n"
                return content[:insert_pos] + figs_text + content[insert_pos:]
            return content + "\n\n" + "\n\n".join(figs)
        return content

    # 从后往前插入，避免序号偏移
    new_content = content
    # 尽可能一一对应，多出来的图插在最后一个表后面
    for i in range(len(table_matches) - 1, -1, -1):
        match = table_matches[i]
        insert_pos = match.end()
        
        # 如果这是最后一个表，且图比表多，把后面所有的图都插在这里
        if i == len(table_matches) - 1 and len(figs) > len(table_matches):
            remaining_figs = figs[i:]
            fig_text = f"\n\n" + "\n\n".join(remaining_figs) + "\n"
        elif i < len(figs):
            fig_text = f"\n\n{figs[i]}\n"
        else:
            continue
            
        new_content = new_content[:insert_pos] + fig_text + new_content[insert_pos:]
        
    return new_content


def integrate_ai_content(template_content, ai_content):
    """将 AI 生成的内容整合到模板中"""
    import re
    
    # AIBackend.clean_content 已经做了基础清理
    # 这里增加一些安全性检查
    ai_content = ai_content.strip()
    
    # 替换内容区块
    pattern = r'(% BEGIN:content)(.*?)(% END:content)'
    
    # 使用函数作为 replacement 可以避免复杂的转义问题
    def replacement_func(match):
        return f"{match.group(1)}\n{ai_content}\n{match.group(3)}"
        
    # 如果使用函数，就不需要手动转义反斜杠了，因为 Python 不会解释函数返回值的转义
    content = re.sub(pattern, replacement_func, template_content, flags=re.DOTALL)
    
    return content


def add_appendix_images(content, work_dir, data_sheet_images, preview_report_images):
    """添加附录图片到报告"""
    import re
    
    # 将 AI 生成内容中的所有 table 环境的 [htpb] 替换为 [H]
    content = re.sub(r'\\begin\{table\}\[[^\]]+\]', r'\\begin{table}[H]', content)
    
    appendix_content = []
    
    # 添加预习报告图片
    if preview_report_images:
        appendix_content.append("\\subsection{预习报告照片}")
        for img_path in preview_report_images:
            img_name = os.path.basename(img_path)
            appendix_content.append(f"""\\begin{{figure}}[H]
    \\centering
    \\includegraphics[width=0.8\\textwidth]{{{img_name}}}
    \\caption{{预习报告}}
\\end{{figure}}""")
    
    # 添加数据记录表图片
    if data_sheet_images:
        appendix_content.append("\\subsection{实验原始数据记录表照片}")
        for i, img_path in enumerate(data_sheet_images):
            img_name = os.path.basename(img_path)
            appendix_content.append(f"""\\begin{{figure}}[H]
    \\centering
    \\includegraphics[width=0.8\\textwidth]{{{img_name}}}
    \\caption{{原始数据记录表 - 第{i+1}页}}
\\end{{figure}}""")
    
    if appendix_content:
        appendix_text = '\n'.join(appendix_content)
        # 替换附录区块
        pattern = r'(% BEGIN:appendix)(.*?)(% END:appendix)'
        
        def replacement_func(match):
            return f"{match.group(1)}\n\\section{{附录}}\n{appendix_text}\n{match.group(3)}"
            
        content = re.sub(pattern, replacement_func, content, flags=re.DOTALL)
    
    return content


# =====================================================
# 历史记录 API
# =====================================================

@app.route('/api/history')
def get_history():
    """获取历史记录"""
    limit = request.args.get('limit', 20, type=int)
    records = history_manager.get_history(limit)
    
    # 格式化返回数据
    formatted = []
    for r in records:
        formatted.append({
            'id': r['id'],
            'experiment_name': r['experiment_name'],
            'student_name': r['student_name'],
            'created_at': r['created_at'],
            'info': r.get('info', {})
        })
    
    return jsonify({
        'success': True,
        'records': formatted
    })


@app.route('/api/history/<session_id>')
def get_history_detail(session_id):
    """获取历史记录详情"""
    record = history_manager.get_record(session_id)
    
    if not record:
        return jsonify({'success': False, 'message': '记录不存在'}), 404
    
    # 恢复会话
    if os.path.exists(record.get('pdf_path', '')):
        sessions[session_id] = {
            'work_dir': record['work_dir'],
            'tex_file': record['tex_path'],
            'pdf_file': record['pdf_path']
        }
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'pdf_url': f'/api/preview/{session_id}',
            'record': record
        })
    
    return jsonify({'success': False, 'message': 'PDF 文件不存在'}), 404


@app.route('/api/history/<session_id>', methods=['DELETE'])
def delete_history(session_id):
    """删除历史记录"""
    success = history_manager.delete_record(session_id)
    
    if success:
        if session_id in sessions:
            del sessions[session_id]
        return jsonify({'success': True, 'message': '已删除'})
    
    return jsonify({'success': False, 'message': '删除失败'}), 400


@app.route('/api/history/search')
def search_history():
    """搜索历史记录"""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'success': False, 'message': '请提供搜索关键词'}), 400
    
    results = history_manager.search(query)
    return jsonify({
        'success': True,
        'results': results
    })


# =====================================================
# 其他 API
# =====================================================

@app.route('/api/preview/<session_id>')
def preview_pdf(session_id):
    """预览 PDF"""
    if session_id not in sessions or 'pdf_file' not in sessions[session_id]:
        # 尝试从历史记录恢复
        record = history_manager.get_record(session_id)
        if record and os.path.exists(record.get('pdf_path', '')):
            return send_file(record['pdf_path'], mimetype='application/pdf')
        return jsonify({'error': '找不到该报告'}), 404
    
    pdf_path = sessions[session_id]['pdf_file']
    if os.path.exists(pdf_path):
        return send_file(pdf_path, mimetype='application/pdf')
    
    return jsonify({'error': 'PDF 文件不存在'}), 404


@app.route('/api/download/<session_id>')
def download_pdf(session_id):
    """下载 PDF"""
    if session_id not in sessions or 'pdf_file' not in sessions[session_id]:
        record = history_manager.get_record(session_id)
        if record and os.path.exists(record.get('pdf_path', '')):
            return send_file(
                record['pdf_path'],
                as_attachment=True,
                download_name='实验报告.pdf'
            )
        return jsonify({'error': '找不到该报告'}), 404
    
    pdf_path = sessions[session_id]['pdf_file']
    if os.path.exists(pdf_path):
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name='实验报告.pdf'
        )
    
    return jsonify({'error': 'PDF 文件不存在'}), 404


@app.route('/api/download-tex/<session_id>')
def download_tex(session_id):
    """下载 LaTeX 源码"""
    if session_id not in sessions or 'tex_file' not in sessions[session_id]:
        record = history_manager.get_record(session_id)
        if record and os.path.exists(record.get('tex_path', '')):
            return send_file(
                record['tex_path'],
                as_attachment=True,
                download_name='实验报告.tex'
            )
        return jsonify({'error': '找不到该报告'}), 404
    
    tex_path = sessions[session_id]['tex_file']
    if os.path.exists(tex_path):
        return send_file(
            tex_path,
            as_attachment=True,
            download_name='实验报告.tex'
        )
    
    return jsonify({'error': 'LaTeX 文件不存在'}), 404


@app.route('/api/modify', methods=['POST'])
def modify_report():
    """修改报告"""
    data = request.json
    session_id = data.get('session_id')
    modification = data.get('modification', '')
    
    if not session_id or session_id not in sessions:
        return jsonify({'success': False, 'message': '会话不存在'}), 400
    
    tex_file = sessions[session_id].get('tex_file')
    if not tex_file or not os.path.exists(tex_file):
        return jsonify({'success': False, 'message': 'LaTeX 文件不存在'}), 400
    
    try:
        # 读取当前内容
        with open(tex_file, 'r', encoding='utf-8') as f:
            current_content = f.read()
        
        # 如果有修改要求且有 API 配置，使用 AI 修改
        if modification.strip():
            use_api_url = data.get('api_url') or api_config['url']
            use_api_key = data.get('api_key') or api_config['key']
            use_api_model = data.get('api_model') or api_config['model']
            
            if use_api_url and use_api_key:
                try:
                    backend = OpenAIBackend(
                        api_key=use_api_key,
                        api_url=use_api_url,
                        model=use_api_model
                    )
                    
                    prompt = f"""请根据以下要求修改 LaTeX 实验报告：

## 当前报告内容：
```latex
{current_content[:15000]}
```

## 修改要求：
{modification}

请返回修改后的完整 LaTeX 代码。只返回代码，不要其他说明。
"""
                    
                    modified_content_raw = backend.generate(prompt)
                    modified_content = backend.clean_content(modified_content_raw)
                    
                    # 保存修改后的内容
                    with open(tex_file, 'w', encoding='utf-8') as f:
                        f.write(modified_content)
                    
                    # 重新编译
                    work_dir = sessions[session_id].get('work_dir')
                    success, message, pdf_path = compile_latex(
                        tex_file,
                        work_dir,
                        config.FONTS_FOLDER
                    )
                    
                    if success:
                        sessions[session_id]['pdf_file'] = pdf_path
                        return jsonify({
                            'success': True,
                            'pdf_url': f'/api/preview/{session_id}',
                            'message': '修改成功！'
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'message': f'编译失败: {message}',
                            'tex_content': modified_content
                        })
                        
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'message': f'AI 修改失败: {str(e)}',
                        'tex_content': current_content
                    })
        
        # 返回当前内容供手动编辑
        return jsonify({
            'success': True,
            'message': '请在编辑器中手动修改',
            'tex_content': current_content
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'修改失败: {str(e)}'
        }), 500


@app.route('/api/update-tex', methods=['POST'])
def update_tex():
    """更新 LaTeX 内容并重新编译"""
    data = request.json
    session_id = data.get('session_id')
    tex_content = data.get('tex_content', '')
    
    if not session_id or session_id not in sessions:
        return jsonify({'success': False, 'message': '会话不存在'}), 400
    
    tex_file = sessions[session_id].get('tex_file')
    work_dir = sessions[session_id].get('work_dir')
    
    if not tex_file or not work_dir:
        return jsonify({'success': False, 'message': '工作目录不存在'}), 400
    
    try:
        # 保存新内容
        with open(tex_file, 'w', encoding='utf-8') as f:
            f.write(tex_content)
        
        # 重新编译
        success, message, pdf_path = compile_latex(
            tex_file,
            work_dir,
            config.FONTS_FOLDER
        )
        
        if success:
            sessions[session_id]['pdf_file'] = pdf_path
            return jsonify({
                'success': True,
                'pdf_url': f'/api/preview/{session_id}',
                'message': '更新成功！'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'编译失败: {message}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'更新失败: {str(e)}'
        }), 500


if __name__ == '__main__':
    print("=" * 50)
    print("大物实验报告生成器 v2.0")
    print("=" * 50)
    
    # 检查 LaTeX 安装
    compiler = LaTeXCompiler()
    installed, msg = compiler.check_installation()
    if installed:
        print(f"✓ {msg}")
    else:
        print(f"✗ {msg}")
        print("  请安装 TeX Live 或 MikTeX 以支持 PDF 编译")
    
    # 显示历史记录统计
    stats = history_manager.get_stats()
    print(f"✓ 历史记录: {stats['valid_records']} 份报告")
    
    print()
    print("新功能:")
    print("  • PDF 文本提取 - 自动从指导书中提取内容")
    print("  • Python 自动画图 - AI 生成代码并执行")
    print("  • 历史记录 - 保存和管理生成的报告")
    print()
    print("启动服务器...")
    print("请在浏览器中访问: http://localhost:5000")
    print("=" * 50)
    
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
