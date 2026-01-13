"""
历史记录管理模块
保存和管理生成的报告历史
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional
import shutil


class HistoryManager:
    """历史记录管理器"""
    
    def __init__(self, base_dir: str):
        """
        初始化管理器
        
        Args:
            base_dir: 基础目录（通常是 output 目录）
        """
        self.base_dir = base_dir
        self.history_file = os.path.join(base_dir, 'history.json')
        self.history = self._load_history()
    
    def _load_history(self) -> List[Dict]:
        """加载历史记录"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_history(self):
        """保存历史记录"""
        os.makedirs(self.base_dir, exist_ok=True)
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
    
    def add_record(self, session_id: str, experiment_name: str, 
                   student_name: str, pdf_path: str, tex_path: str,
                   additional_info: Dict = None) -> Dict:
        """
        添加历史记录
        
        Args:
            session_id: 会话 ID
            experiment_name: 实验名称
            student_name: 学生姓名
            pdf_path: PDF 文件路径
            tex_path: LaTeX 文件路径
            additional_info: 额外信息
            
        Returns:
            创建的记录
        """
        record = {
            'id': session_id,
            'experiment_name': experiment_name,
            'student_name': student_name,
            'created_at': datetime.now().isoformat(),
            'pdf_path': pdf_path,
            'tex_path': tex_path,
            'work_dir': os.path.dirname(tex_path),
            'info': additional_info or {}
        }
        
        # 检查是否已存在，存在则更新
        existing_idx = None
        for i, r in enumerate(self.history):
            if r['id'] == session_id:
                existing_idx = i
                break
        
        if existing_idx is not None:
            record['created_at'] = self.history[existing_idx].get('created_at', record['created_at'])
            record['updated_at'] = datetime.now().isoformat()
            self.history[existing_idx] = record
        else:
            self.history.insert(0, record)  # 新记录放在开头
        
        # 限制历史记录数量
        if len(self.history) > 100:
            # 删除旧记录及其文件
            for old_record in self.history[100:]:
                self._cleanup_record(old_record)
            self.history = self.history[:100]
        
        self._save_history()
        return record
    
    def get_history(self, limit: int = 20) -> List[Dict]:
        """
        获取历史记录
        
        Args:
            limit: 返回数量限制
            
        Returns:
            历史记录列表
        """
        # 过滤掉已删除文件的记录
        valid_records = []
        for record in self.history:
            pdf_path = record.get('pdf_path', '')
            if os.path.exists(pdf_path):
                valid_records.append(record)
        
        return valid_records[:limit]
    
    def get_record(self, session_id: str) -> Optional[Dict]:
        """
        获取单条记录
        
        Args:
            session_id: 会话 ID
            
        Returns:
            记录或 None
        """
        for record in self.history:
            if record['id'] == session_id:
                return record
        return None
    
    def delete_record(self, session_id: str) -> bool:
        """
        删除记录
        
        Args:
            session_id: 会话 ID
            
        Returns:
            是否成功
        """
        for i, record in enumerate(self.history):
            if record['id'] == session_id:
                self._cleanup_record(record)
                self.history.pop(i)
                self._save_history()
                return True
        return False
    
    def _cleanup_record(self, record: Dict):
        """清理记录的相关文件"""
        work_dir = record.get('work_dir')
        if work_dir and os.path.exists(work_dir):
            try:
                shutil.rmtree(work_dir)
            except:
                pass
    
    def search(self, query: str) -> List[Dict]:
        """
        搜索历史记录
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的记录列表
        """
        query = query.lower()
        results = []
        
        for record in self.history:
            if (query in record.get('experiment_name', '').lower() or
                query in record.get('student_name', '').lower()):
                if os.path.exists(record.get('pdf_path', '')):
                    results.append(record)
        
        return results
    
    def get_stats(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            统计数据
        """
        valid_count = sum(1 for r in self.history if os.path.exists(r.get('pdf_path', '')))
        
        experiments = {}
        for record in self.history:
            name = record.get('experiment_name', '未知')
            experiments[name] = experiments.get(name, 0) + 1
        
        return {
            'total_records': len(self.history),
            'valid_records': valid_count,
            'experiments': experiments
        }
