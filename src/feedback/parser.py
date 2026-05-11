"""
邮件反馈解析模块

通过 IMAP 轮询 QQ 邮箱，解析用户回复的反馈邮件。

支持格式:
  1. 批量: subject = feedback:batch:id1,id2,id3:good|bad
  2. 详细: subject = feedback:detail:id1,id2,... 
           body 包含 "好评 1,3,5" 或 "好评：1,3,5"（编号对应邮件中的商品顺序）
  3. 自由回复: subject 包含 "反馈" 关键词
           body 包含 "好评 1,2" "差评 3" 等
"""
import imaplib
import email
import json
from email.header import decode_header
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


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
                
                # 1. 尝试批量格式: feedback:batch:ids:good|bad
                parsed = self._parse_batch_subject(subject)
                if parsed:
                    feedbacks.append(parsed)
                    logger.info(f"解析到批量反馈: {parsed}")
                    self._processed_uids.add(msg_id)
                    continue
                
                # 2. 尝试详细格式: feedback:detail:ids + body
                parsed = self._parse_detail(subject, body)
                if parsed:
                    feedbacks.extend(parsed)
                    logger.info(f"解析到详细反馈: {len(parsed)} 条")
                    self._processed_uids.add(msg_id)
                    continue
                
                # 3. 自由回复: subject 包含"反馈" + body 解析编号
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
    
    def _parse_batch_subject(self, subject: str) -> Optional[Dict]:
        """解析批量反馈: feedback:batch:id1,id2,id3:good|bad"""
        pattern = r'feedback:batch:([^:]+):(good|bad)'
        match = re.search(pattern, subject, re.IGNORECASE)
        if not match:
            return None
        
        ids_str = match.group(1)
        feedback_type = match.group(2).lower()
        
        product_ids = [pid.strip() for pid in ids_str.split(',') if pid.strip()]
        if not product_ids:
            return None
        
        type_map = {'good': 'helpful', 'bad': 'not_helpful'}
        
        return {
            'product_ids': product_ids,
            'feedback_type': type_map.get(feedback_type, feedback_type),
            'timestamp': datetime.now().isoformat(),
        }
    
    def _parse_detail(self, subject: str, body: str) -> List[Dict]:
        """解析详细反馈: feedback:detail:id1,id2,... + body 中的编号"""
        pattern = r'feedback:detail:([^:\s]+)'
        match = re.search(pattern, subject, re.IGNORECASE)
        if not match:
            return []
        
        ids_str = match.group(1)
        all_ids = [pid.strip() for pid in ids_str.split(',') if pid.strip()]
        if not all_ids:
            return []
        
        return self._parse_numbered_feedback(body, all_ids)
    
    def _parse_free_reply(self, body: str) -> List[Dict]:
        """解析自由回复格式
        
        body 示例:
            好评 1,2 差评 3
            好评：1,3
            差评：2,4
        """
        # 加载最近一次发送的商品列表
        try:
            with open('./data/last_sent_products.json', 'r', encoding='utf-8') as f:
                last_sent = json.load(f)
            all_ids = [item['id'] for item in last_sent]
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning("无法加载最近发送的商品列表，跳过自由回复解析")
            return []
        
        return self._parse_numbered_feedback(body, all_ids)
    
    def _parse_numbered_feedback(self, body: str, all_ids: List[str]) -> List[Dict]:
        """从 body 中解析编号反馈
        
        支持格式:
            好评 1,3,5
            好评：1,3,5
            差评 2,4
            差评：2,4
        """
        # 支持有无冒号
        good_indices = self._extract_indices(body, r'好评[：: ]*\s*([\d,\s]+)')
        bad_indices = self._extract_indices(body, r'差评[：: ]*\s*([\d,\s]+)')
        
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
