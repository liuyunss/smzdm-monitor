"""
邮件反馈解析模块

从回复邮件的主题和正文解析反馈和设置命令。

反馈格式:
  好评 1,2
  好评 1-5
  差评 3
  好评 1-3,5,8-10

设置格式:
  设置：母婴 -100
  设置：数码 +50
  设置：零食 0
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
            logger.error("邮件配置不完整，跳过反馈检查")
            return []
        
        feedbacks = []
        settings = []
        
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
            logger.debug(f"找到 {len(msg_ids)} 封最近邮件")
            
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
                
                if self.username not in from_addr:
                    self._processed_uids.add(msg_id)
                    continue
                
                # 解析设置命令
                parsed_settings = self._parse_settings(body)
                settings.extend(parsed_settings)
                
                # 解析商品反馈
                parsed = self._parse(subject, body)
                if parsed:
                    feedbacks.extend(parsed)
                    logger.info(f"解析到 {len(parsed)} 条反馈")
                
                if parsed_settings:
                    logger.info(f"解析到 {len(parsed_settings)} 条设置")
                
                self._processed_uids.add(msg_id)
            
            mail.logout()
            
            # 写入反馈
            if self.db and feedbacks:
                for fb in feedbacks:
                    # 从商品标题推断品类
                    category = None
                    product = self.db.get_product(fb['product_id'])
                    if product:
                        from src.scorer.category import tag_category
                        category = tag_category(product.get('title', ''))
                    self.db.save_feedback(fb['product_id'], fb['feedback_type'], category)
                    fb['category'] = category
                    logger.info(f"记录反馈: {fb['product_id']} -> {fb['feedback_type']} ({category})")
            
            # 写入设置
            if self.db and settings:
                for s in settings:
                    self.db.save_category_pref(s['category'], s['value'])
                    logger.info(f"更新偏好: {s['category']} = {s['value']}")
            
            return feedbacks
            
        except Exception as e:
            logger.error(f"检查邮件反馈失败: {e}")
            return []
    
    def _parse(self, subject: str, body: str) -> List[Dict]:
        """从主题提取编号→ID映射，从正文提取反馈"""
        id_map = self._extract_id_map(subject, body)
        if not id_map:
            return []
        
        # 从正文提取好评/差评编号（支持 1-5 范围写法）
        good_indices = self._extract_indices(body, r'好评[：: ]*\s*([\d,\s，\-]+)')
        bad_indices = self._extract_indices(body, r'差评[：: ]*\s*([\d,\s，\-]+)')
        
        # 批量模式
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
    
    def _parse_settings(self, body: str) -> List[Dict]:
        """解析设置命令
        
        格式: 设置：品类 值
        示例: 设置：母婴 -100
              设置：数码 +50
        """
        results = []
        # 匹配 设置：xxx +/-数字 或 设置：xxx 数字
        pattern = r'设置[：:]\s*(\S+)\s+([+-]?\d+)'
        for match in re.finditer(pattern, body):
            category = match.group(1)
            value = int(match.group(2))
            # 限制范围 -100 到 +100
            value = max(-100, min(100, value))
            results.append({
                'category': category,
                'value': value,
                'timestamp': datetime.now().isoformat(),
            })
        return results
    
    def _extract_id_map(self, subject: str, body: str = '') -> Dict[int, str]:
        """从主题或正文提取编号→商品ID映射"""
        # 方式1: 按钮格式
        btn_match = re.search(r'反馈[:：]([^:：\s]+)', subject)
        if btn_match:
            ids_str = btn_match.group(1)
            ids = [x.strip() for x in ids_str.split(',') if x.strip()]
            return {i+1: pid for i, pid in enumerate(ids)}
        
        # 方式2: 编号:商品ID(简称) 格式（兼容旧格式）
        pairs = re.findall(r'(\d+):(\d+)\([^)]*\)', subject)
        if pairs:
            return {int(num): pid for num, pid in pairs}
        
        # 方式3: 编号:商品ID 格式（新格式，无括号）
        pairs = re.findall(r'(\d+):(\d+)', subject)
        if pairs:
            return {int(num): pid for num, pid in pairs}
        
        # 方式4: 从正文查找映射行（回复时原文被引用）
        if body:
            mapping_match = re.search(r'商品编号[：:]\s*(.+)', body)
            if mapping_match:
                mapping_str = mapping_match.group(1)
                pairs = re.findall(r'(\d+):(\d+)', mapping_str)
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
        """从文本中提取编号，支持范围写法 1-5,1,3,8-10"""
        match = re.search(pattern, text)
        if not match:
            return []
        
        nums_str = match.group(1)
        indices = []
        
        # 先按逗号/空格分割
        parts = re.split(r'[,，\s]+', nums_str.strip())
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # 检查是否为范围 1-5
            range_match = re.match(r'(\d+)\s*-\s*(\d+)', part)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2))
                indices.extend(range(start, end + 1))
            elif re.match(r'^\d+$', part):
                indices.append(int(part))
        
        return indices


# 全局实例
_feedback_parser_instance = None

def get_feedback_parser(config: Dict, database=None) -> FeedbackParser:
    global _feedback_parser_instance
    if _feedback_parser_instance is None:
        _feedback_parser_instance = FeedbackParser(config, database)
    return _feedback_parser_instance
