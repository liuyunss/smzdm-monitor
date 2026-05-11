"""
什么值得买好价监控系统 - 主入口

用法:
  python3 main.py              # 单次运行
  python3 main.py --daemon     # 守护进程模式（持续运行）
"""
import os
import sys
import time
import signal
import logging
import argparse
import json
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config.loader import get_config, reload_config
from src.storage.database import _db_instance as _db_ref, Database
from src.scorer.algorithm import _scorer_instance as _scorer_ref, Scorer
from src.scorer.preference import _pref_instance as _pref_ref, CategoryPreference
from src.notifier.email import EmailNotifier
from src.feedback.parser import _feedback_parser_instance as _parser_ref, FeedbackParser
from src.proxy.manager import _proxy_manager as _proxy_ref, ProxyManager
from src.storage.database import get_db
from src.proxy.manager import get_proxy_manager
from src.crawler.smzdm import get_crawler
from src.scorer.algorithm import get_scorer
from src.scorer.category import tag_categories_batch, tag_category
from src.scorer.preference import get_category_pref
from src.notifier.email import EmailNotifier
from src.feedback.parser import get_feedback_parser

# 日志
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/smzdm.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def is_quiet_hours(config) -> bool:
    """检查当前是否在免打扰时段（北京时间）"""
    quiet = config.get('monitor', 'quiet_hours', default=None) or {}
    if not quiet.get('enabled', False):
        return False
    now = datetime.now(ZoneInfo('Asia/Shanghai'))
    current = now.strftime('%H:%M')
    start = quiet.get('start', '00:30')
    end = quiet.get('end', '07:30')
    if start <= end:
        return start <= current <= end
    else:  # 跨午夜，如 23:00 ~ 06:00
        return current >= start or current <= end

# 优雅退出
_running = True
_QUIET_BUFFER_FILE = './data/quiet_buffer.json'

def _load_quiet_buffer():
    """从文件加载免打扰缓冲"""
    try:
        if os.path.exists(_QUIET_BUFFER_FILE):
            with open(_QUIET_BUFFER_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _save_quiet_buffer(buf):
    """保存免打扰缓冲到文件"""
    os.makedirs(os.path.dirname(_QUIET_BUFFER_FILE), exist_ok=True)
    with open(_QUIET_BUFFER_FILE, 'w') as f:
        json.dump(buf, f)

def _clear_quiet_buffer():
    """清空免打扰缓冲文件"""
    try:
        os.remove(_QUIET_BUFFER_FILE)
    except FileNotFoundError:
        pass
def _signal_handler(sig, frame):
    global _running
    logger.info("收到退出信号，正在停止...")
    _running = False

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def run_monitor():
    """运行一轮监控，返回发送了通知的商品数"""
    logger.info("=" * 50)
    logger.info("开始什么值得买好价监控")
    logger.info("=" * 50)

    notified = 0
    try:
        config = get_config()

        db_path = config.get('storage', 'db_path', default='./data/smzdm.db')
        db = get_db(db_path)

        category_pref = get_category_pref(db)

        # 检查邮件反馈
        logger.info("检查邮件反馈...")
        parser = get_feedback_parser(config.get('notifier', 'email', default=None) or {}, db)
        feedbacks = parser.check_and_parse()
        if feedbacks:
            logger.info(f"收到 {len(feedbacks)} 条反馈")
            for fb in feedbacks:
                product = db.get_product(fb['product_id'])
                if product:
                    category = tag_category(product.get('title', ''))
                    category_pref.record_feedback(category, fb['feedback_type'])

        # 代理
        proxy_config = config.get('proxy', default=None) or {}
        proxy_manager = get_proxy_manager(proxy_config)

        # 爬虫
        crawler_config = {
            'items_per_page': config.get('monitor', 'items_per_page', default=20),
            'max_pages': config.get('monitor', 'max_pages', default=50),
            'target_minutes': config.get('monitor', 'target_minutes', default=30),
        }
        crawler = get_crawler(crawler_config, proxy_manager)

        # 评分器
        scorer_config = config.get('scorer', default=None) or {}
        scorer = get_scorer(scorer_config, category_pref)

        # 通知器
        notifier_config = config.get('notifier', 'email', default=None) or {}
        notifier = EmailNotifier(notifier_config)

        # 过滤配置
        filter_config = config.get('filter', default=None) or {}

        # 抓取
        target_minutes = config.get('monitor', 'target_minutes', default=30)
        max_pages = config.get('monitor', 'max_pages', default=50)
        products = crawler.fetch_multiple_pages(target_minutes=target_minutes, max_pages=max_pages)
        logger.info(f"抓取完成，共 {len(products)} 个商品")

        if not products:
            logger.warning("未抓取到任何商品")
            return 0

        # 打品类标签
        products = tag_categories_batch(products)

        # 过滤
        filtered_products = scorer.filter_products(products, filter_config)
        logger.info(f"过滤后剩余 {len(filtered_products)} 个商品")

        # 评分（基于绝对互动量，不再需要增长数据）
        scored_products = []
        to_save = []

        quiet = is_quiet_hours(config)

        # 批量查询价格历史（避免 N+1）
        product_ids = [p['id'] for p in filtered_products]
        price_history_map = db.get_price_history_batch(product_ids)
        
        for product in filtered_products:
            price_history = price_history_map.get(product['id'], [])
            score = scorer.calculate_score(product, price_history)
            product['score'] = score
            to_save.append(product)

            min_score = config.get('scorer', 'min_composite_score', default=35)
            if score >= min_score:
                if quiet:
                    # 免打扰：先不标记已通知，攒起来
                    quiet_buffer.append(product)
                else:
                    if db.save_notification(product['id'], current_score=score):
                        scored_products.append(product)

        # 批量保存
        if to_save:
            db.save_products_batch(to_save)

        # 免打扰结束时，把攒的一起发
        # 保存 quiet buffer
        if quiet and quiet_buffer:
            _save_quiet_buffer(quiet_buffer)
        
        if not quiet and quiet_buffer:
            logger.info(f"免打扰结束，推送攒的 {len(quiet_buffer)} 件商品")
            for product in quiet_buffer:
                if db.save_notification(product['id'], current_score=product.get('score', 0)):
                    scored_products.append(product)
            _clear_quiet_buffer()

        logger.info(f"筛选出 {len(scored_products)} 个高分商品")

        # 发送通知
        if scored_products:
            scored_products.sort(key=lambda x: x.get('score', 0), reverse=True)
            max_items = config.get('notifier', 'limits', 'max_items_per_batch', default=20)
            scored_products = scored_products[:max_items]

            success = notifier.send_notification(scored_products)
            if success:
                logger.info("通知发送成功")
                notified = len(scored_products)
            else:
                logger.warning("通知发送失败")

        # 清理旧数据
        if config.get('storage', 'auto_cleanup', default=True):
            retention_days = config.get('storage', 'retention_days', default=30)
            db.cleanup_old_data(retention_days)

        logger.info("监控完成")

    except Exception as e:
        logger.error(f"监控过程出错: {e}", exc_info=True)

    return notified


def main():
    parser = argparse.ArgumentParser(description='什么值得买好价监控系统')
    parser.add_argument('--daemon', action='store_true', help='守护进程模式，持续运行')
    parser.add_argument('--config', type=str, help='配置文件路径')
    args = parser.parse_args()

    if args.config:
        reload_config(args.config)

    if args.daemon:
        logger.info("启动守护进程模式")
        global _running
        while _running:
            try:
                # 每轮重新加载配置（支持热更新）
                if args.config:
                    reload_config(args.config)
                else:
                    reload_config()

                notified = run_monitor()

                # 获取间隔（秒）
                config = get_config()
                interval = config.get('monitor', 'interval', default=300)
                logger.info(f"本轮结束，{notified} 件商品通知，{interval}s 后执行下一轮")

                # 分段 sleep，便于快速响应退出信号
                for _ in range(interval):
                    if not _running:
                        break
                    time.sleep(1)

            except Exception as e:
                logger.error(f"守护进程异常: {e}", exc_info=True)
                time.sleep(30)  # 异常后短暂等待
    else:
        run_monitor()


if __name__ == '__main__':
    main()
