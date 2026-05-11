"""
邮件反馈解析模块

从回复邮件的主题和正文解析反馈。

主题格式（自动继承）:
  回复：【SMZDM好价】1:商品A,2:商品B,3:商品C - 05-11 09:38

正文格式:
  好评 1,2
  差评 3
"""
import imaplib
import email
from email.header import decode_header
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)


class FeedbackParser:
    """邮件反馈解析器"""
    
    def __init__(self, config: Dict, database=None):
        self.config = config
        self.db = database
        self._load_config()
    
    def _load_config(self):
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
                
                parsed = self._parse(subject, body)
                if parsed:
                    feedbacks.extend(parsed)
                    logger.info(f"解析到 {len(parsed)} 条反馈")
                
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
    
    def _parse(self, subject: str, body: str) -> List[Dict]:
        """从主题提取编号→ID映射，从正文提取反馈"""
        
        # 1. 从主题提取编号→ID映射
        # 匹配: 1:商品名,2:商品名 或 反馈:id1,id2:good
        id_map = self._extract_id_map(subject)
        if not id_map:
            return []
        
        # 2. 从正文提取好评/差评编号
        good_indices = self._extract_indices(body, r'好评[：: ]*\s*([\d,\s，]+)')
        bad_indices = self._extract_indices(body, r'差评[：: ]*\s*([\d,\s，]+)')
        
        # 3. 批量模式（都不错/都不行）
        if not good_indices and not bad_indices:
            if '反馈' in subject:
                if ':good' in subject:
                    good_indices = list(id_map.keys())
                elif ':bad' in subject:
                    bad_indices = list(id_map.keys())
        
        if not good_indices and not bad_indices:
            return []
        
        results = []
        for idx in good_indices:
            if idx in id_map:
                results.append({
                    'product_id': id_map[idx],
                    'feedback_type': 'helpful',
                    'timestamp': datetime.now().isoformat(),
                })
        for idx in bad_indices:
            if idx in id_map:
                results.append({
                    'product_id': id_map[idx],
                    'feedback_type': 'not_helpful',
                    'timestamp': datetime.now().isoformat(),
                })
        
        return results
    
    def _extract_id_map(self, subject: str) -> Dict[int, str]:
        """从主题提取编号→商品ID映射
        
        主题格式: 回复：【SMZDM好价】1:300001(AirPod),2:300002(键盘) - 05-11 09:38
        或: 反馈:300001,300002,300003:good
        
        返回: {1: '300001', 2: '300002', ...}
        """
        # 方式1: 按钮格式 反馈:id1,id2,id3:good/bad/detail
        btn_match = re.search(r'反馈[:：]([^:：\s]+)', subject)
        if btn_match:
            ids_str = btn_match.group(1)
            ids = [x.strip() for x in ids_str.split(',') if x.strip()]
            return {i+1: pid for i, pid in enumerate(ids)}
        
        # 方式2: 编号:商品ID(简称) 格式
        # 匹配 1:300001(AirPod),2:300002(键盘)
        pairs = re.findall(r'(\d+):(\d+)\([^)]*\)', subject)
        if pairs:
            return {int(num): pid for num, pid in pairs}
        
        return {}
    
    def _decode_subject(self, subject: str) -> str:
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
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='replace')
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode('utf-8', errors='replace')
        return body
    
    def _extract_indices(self, text: str, pattern: str) -> List[int]:
        match = re.search(pattern, text)
        if not match:
            return []
        return [int(n) for n in re.findall(r'\d+', match.group(1)) if n]


# 全局实例
_feedback_parser_instance = None

def get_feedback_parser(config: Dict, database=None) -> FeedbackParser:
    global _feedback_parser_instance
    if _feedback_parser_instance is None:
        _feedback_parser_instance = FeedbackParser(config, database)
    return _feedback_parser_instance
