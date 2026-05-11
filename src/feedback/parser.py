"""
邮件反馈解析模块

通过 IMAP 轮询 QQ 邮箱，解析用户回复的反馈邮件。

支持格式:
  1. 按钮反馈: subject = 反馈:batchId:good|bad
  2. 按钮详细: subject = 反馈:batchId:detail + body 编号
  3. 直接回复: subject = 回复：【SMZDM好价】... + body 编号
  4. 自由回复: subject 包含"反馈" + body 编号
"""
import imaplib
import email
import json
from email.header import decode_header
import logging
import re
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

DATA_DIR = './data'
BATCH_FILE = os.path.join(DATA_DIR, 'batch_history.json')


class FeedbackParser:
    """邮件反馈解析器"""
    
    def __init__(self, config: Dict, database=None):
        self.config = config
        self.db = database
        self._load_config()
    
    def _load_config(self):
        """加载邮件配置"""
        self.imap_server = self.config.get('imap_server', 'imap.qq.com')
        self.imap_port = self.config.get('imap_port', 993)
        self.username = self.config.get('username', '')
        self.password = self.config.get('password', '')
        self.folder = self.config.get('feedback_folder', 'INBOX')
        self._processed_uids = set()
    
    def check_and_parse(self) -> List[Dict]:
        """检查邮箱并解析反馈"""
        if not self.username or not self.password:
            logger.warning("邮件配置不完整，跳过反馈检查")
            return []
        
        feedbacks = []
        
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.username, self.password)
            mail.select(self.folder)
            
            since = (datetime.now() - timedelta(hours=1)).strftime('%d-%b-%Y')
            status, messages = mail.search(None, f'(SINCE "{since}")')
            
            if status != 'OK':
                logger.warning("搜索邮件失败")
                mail.logout()
                return []
            
            msg_ids = messages[0].split()
            logger.info(f"找到 {len(msg_ids)} 封最近邮件")
            
            for msg_id in msg_ids:
                if msg_id in self._processed_uids:
                    continue
                
                status, msg_data = mail.fetch(msg_id, '(RFC822)')
                if status != 'OK':
                    continue
                
                msg = email.message_from_bytes(msg_data[0][1])
                subject = self._decode_subject(msg.get('Subject', ''))
                body = self._get_body(msg)
                from_addr = msg.get('From', '')
                
                # 只处理来自自己邮箱的回复
                if self.username not in from_addr:
                    self._processed_uids.add(msg_id)
                    continue
                
                parsed = None
                
                # 1. 按钮批量: 反馈:batchId:good|bad
                parsed = self._parse_batch_feedback(subject, body)
                if parsed:
                    feedbacks.extend(parsed)
                    logger.info(f"解析到按钮批量反馈: {len(parsed)} 条")
                    self._processed_uids.add(msg_id)
                    continue
                
                # 2. 按钮详细: 反馈:batchId:detail
                parsed = self._parse_detail_feedback(subject, body)
                if parsed:
                    feedbacks.extend(parsed)
                    logger.info(f"解析到按钮详细反馈: {len(parsed)} 条")
                    self._processed_uids.add(msg_id)
                    continue
                
                # 3. 直接回复原邮件: 回复：【SMZDM好价】...
                parsed = self._parse_reply_feedback(subject, body)
                if parsed:
                    feedbacks.extend(parsed)
                    logger.info(f"解析到直接回复反馈: {len(parsed)} 条")
                    self._processed_uids.add(msg_id)
                    continue
                
                # 4. 自由回复: subject 包含"反馈"
                if '反馈' in subject:
                    parsed = self._parse_free_reply(body)
                    if parsed:
                        feedbacks.extend(parsed)
                        logger.info(f"解析到自由反馈: {len(parsed)} 条")
                        self._processed_uids.add(msg_id)
                        continue
                
                self._processed_uids.add(msg_id)
            
            mail.logout()
            
            # 写入数据库
            if self.db and feedbacks:
                for fb in feedbacks:
                    self.db.save_feedback(fb['product_id'], fb['feedback_type'])
                    logger.info(f"记录反馈: {fb['product_id']} -> {fb['feedback_type']}")
            
            return feedbacks
            
        except Exception as e:
            logger.error(f"检查邮件反馈失败: {e}")
            return []
    
    def _decode_subject(self, subject: str) -> str:
        """解码邮件主题"""
        if not subject:
            return ""
        decoded_parts = decode_header(subject)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or 'utf-8', errors='replace'))
            else:
                result.append(part)
        return ''.join(result)
    
    def _get_body(self, msg) -> str:
        """提取邮件正文"""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == 'text/plain':
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='replace')
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode('utf-8', errors='replace')
        return body
    
    def _load_batch(self, batch_id: str) -> List[str]:
        """加载批次对应的商品ID列表"""
        try:
            with open(BATCH_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
            batch = history.get(batch_id, [])
            return [item['id'] for item in batch]
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _load_latest_batch(self) -> List[str]:
        """加载最近一次发送的商品ID列表"""
        try:
            with open(BATCH_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
            if not history:
                return []
            latest_key = list(history.keys())[-1]
            return [item['id'] for item in history[latest_key]]
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _match_batch_by_subject(self, subject: str) -> List[str]:
        """通过主题中的关键词匹配批次
        
        回复的主题格式: 回复：【SMZDM好价】AirPods ,罗技 G913 ,小米 Buds  | 3件 - 05-11 09:38
        需要从 batch_history.json 中找到匹配的批次
        """
        # 提取商品关键词（去掉"回复：【SMZDM好价】"前缀和时间后缀）
        clean = re.sub(r'^回复[：:]?\s*【?SMZDM好价】?\s*', '', subject)
        clean = re.sub(r'\|\s*\d+件\s*-\s*\d{2}-\d{2}\s*\d{2}:\d{2}\s*$', '', clean)
        clean = clean.strip()
        
        if not clean:
            return []
        
        # 从 batch_history 中匹配
        try:
            with open(BATCH_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
        
        # 提取关键词（取前几个字符做匹配）
        keywords = [kw.strip() for kw in clean.split(',') if kw.strip()]
        
        best_match = None
        best_score = 0
        
        for batch_id, products in history.items():
            titles = [p.get('title', '') for p in products]
            score = 0
            for kw in keywords:
                for title in titles:
                    if kw[:6] in title:  # 用前6个字符匹配
                        score += 1
                        break
            if score > best_score:
                best_score = score
                best_match = batch_id
        
        if best_match and best_score > 0:
            return [item['id'] for item in history[best_match]]
        
        return []
    
    def _parse_batch_feedback(self, subject: str, body: str) -> List[Dict]:
        """解析按钮批量反馈: 反馈:batchId:good|bad"""
        pattern = r'反馈[:：]([\w\-]+)[:：](good|bad)'
        match = re.search(pattern, subject, re.IGNORECASE)
        if not match:
            return []
        
        batch_id = match.group(1)
        feedback_type = match.group(2).lower()
        
        all_ids = self._load_batch(batch_id)
        if not all_ids:
            logger.warning(f"找不到批次 {batch_id} 的商品列表")
            return []
        
        type_map = {'good': 'helpful', 'bad': 'not_helpful'}
        fb_type = type_map.get(feedback_type, feedback_type)
        
        return [{
            'product_id': pid,
            'feedback_type': fb_type,
            'timestamp': datetime.now().isoformat(),
        } for pid in all_ids]
    
    def _parse_detail_feedback(self, subject: str, body: str) -> List[Dict]:
        """解析按钮详细反馈: 反馈:batchId:detail"""
        pattern = r'反馈[:：]([\w\-]+)[:：]detail'
        match = re.search(pattern, subject, re.IGNORECASE)
        if not match:
            return []
        
        batch_id = match.group(1)
        all_ids = self._load_batch(batch_id)
        if not all_ids:
            logger.warning(f"找不到批次 {batch_id} 的商品列表")
            return []
        
        return self._parse_numbered_feedback(body, all_ids)
    
    def _parse_reply_feedback(self, subject: str, body: str) -> List[Dict]:
        """解析直接回复原邮件: 回复：【SMZDM好价】..."""
        if '回复' not in subject and 'Re:' not in subject and 'RE:' not in subject:
            return []
        
        # 通过主题匹配批次
        all_ids = self._match_batch_by_subject(subject)
        if not all_ids:
            logger.warning(f"无法通过主题匹配批次: {subject}")
            return []
        
        return self._parse_numbered_feedback(body, all_ids)
    
    def _parse_free_reply(self, body: str) -> List[Dict]:
        """解析自由回复"""
        all_ids = self._load_latest_batch()
        if not all_ids:
            return []
        
        return self._parse_numbered_feedback(body, all_ids)
    
    def _parse_numbered_feedback(self, body: str, all_ids: List[str]) -> List[Dict]:
        """从 body 中解析编号反馈
        
        支持: 好评 1,3 / 好评：1,3 / 差评 2,4
        """
        good_indices = self._extract_indices(body, r'好评[：: ]*\s*([\d,\s，]+)')
        bad_indices = self._extract_indices(body, r'差评[：: ]*\s*([\d,\s，]+)')
        
        if not good_indices and not bad_indices:
            return []
        
        results = []
        
        for idx in good_indices:
            if 0 < idx <= len(all_ids):
                results.append({
                    'product_id': all_ids[idx - 1],
                    'feedback_type': 'helpful',
                    'timestamp': datetime.now().isoformat(),
                })
        
        for idx in bad_indices:
            if 0 < idx <= len(all_ids):
                results.append({
                    'product_id': all_ids[idx - 1],
                    'feedback_type': 'not_helpful',
                    'timestamp': datetime.now().isoformat(),
                })
        
        return results
    
    def _extract_indices(self, text: str, pattern: str) -> List[int]:
        """从文本中提取编号列表"""
        match = re.search(pattern, text)
        if not match:
            return []
        
        nums_str = match.group(1)
        indices = []
        for n in re.findall(r'\d+', nums_str):
            try:
                indices.append(int(n))
            except ValueError:
                pass
        return indices


# 全局实例
_feedback_parser_instance = None

def get_feedback_parser(config: Dict, database=None) -> FeedbackParser:
    """获取全局反馈解析器"""
    global _feedback_parser_instance
    if _feedback_parser_instance is None:
        _feedback_parser_instance = FeedbackParser(config, database)
    return _feedback_parser_instance
