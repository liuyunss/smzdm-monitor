"""
邮件反馈解析模块

通过 IMAP 轮询 QQ 邮箱，解析用户回复的反馈邮件。
格式: subject = feedback:batch:id1,id2,id3:good|bad|mixed
"""
import imaplib
import email
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
        # 已处理的邮件 ID
        self._processed_uids = set()
    
    def check_and_parse(self) -> List[Dict]:
        """检查邮箱并解析反馈
        
        Returns:
            解析出的反馈列表: [{product_id, feedback_type, timestamp}]
        """
        if not self.username or not self.password:
            logger.warning("邮件配置不完整，跳过反馈检查")
            return []
        
        feedbacks = []
        
        try:
            # 连接 IMAP
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.username, self.password)
            mail.select(self.folder)
            
            # 搜索最近 1 小时内的邮件（避免重复处理）
            since = (datetime.now() - timedelta(hours=1)).strftime('%d-%b-%Y')
            status, messages = mail.search(None, f'(SINCE "{since}")')
            
            if status != 'OK':
                logger.warning("搜索邮件失败")
                mail.logout()
                return []
            
            msg_ids = messages[0].split()
            logger.info(f"找到 {len(msg_ids)} 封最近邮件")
            
            for msg_id in msg_ids:
                # 跳过已处理的
                if msg_id in self._processed_uids:
                    continue
                
                status, msg_data = mail.fetch(msg_id, '(RFC822)')
                if status != 'OK':
                    continue
                
                msg = email.message_from_bytes(msg_data[0][1])
                subject = self._decode_subject(msg.get('Subject', ''))
                
                # 解析反馈格式: feedback:batch:id1,id2,id3:good|bad|mixed
                parsed = self._parse_subject(subject)
                if parsed:
                    feedbacks.append(parsed)
                    logger.info(f"解析到反馈: {parsed}")
                
                self._processed_uids.add(msg_id)
            
            mail.logout()
            
            # 写入数据库
            if self.db and feedbacks:
                for fb in feedbacks:
                    product_ids = fb['product_ids']
                    for pid in product_ids:
                        self.db.save_feedback(pid, fb['feedback_type'])
                        logger.info(f"记录反馈: {pid} -> {fb['feedback_type']}")
            
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
    
    def _parse_subject(self, subject: str) -> Optional[Dict]:
        """解析反馈邮件主题
        
        支持格式:
        - feedback:batch:id1,id2,id3:good
        - feedback:batch:id1,id2,id3:bad
        - feedback:batch:id1,id2,id3:mixed
        """
        # 匹配 feedback:batch:xxx:good/bad/mixed
        pattern = r'feedback:batch:([^:]+):(good|bad|mixed)'
        match = re.search(pattern, subject, re.IGNORECASE)
        
        if not match:
            return None
        
        ids_str = match.group(1)
        feedback_type = match.group(2).lower()
        
        # 解析商品 ID 列表
        product_ids = [pid.strip() for pid in ids_str.split(',') if pid.strip()]
        
        if not product_ids:
            return None
        
        # 标准化反馈类型
        type_map = {
            'good': 'helpful',
            'bad': 'not_helpful',
            'mixed': 'mixed',
        }
        
        return {
            'product_ids': product_ids,
            'feedback_type': type_map.get(feedback_type, feedback_type),
            'timestamp': datetime.now().isoformat(),
        }


# 全局实例
_feedback_parser_instance = None

def get_feedback_parser(config: Dict, database=None) -> FeedbackParser:
    """获取全局反馈解析器"""
    global _feedback_parser_instance
    if _feedback_parser_instance is None:
        _feedback_parser_instance = FeedbackParser(config, database)
    return _feedback_parser_instance
