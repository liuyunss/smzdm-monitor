"""
什么值得买好价监控系统 - 主入口
"""
import os
import sys
import logging
import argparse
import threading
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config.loader import get_config, reload_config
from src.storage.database import get_db
from src.proxy.manager import get_proxy_manager
from src.crawler.smzdm import get_crawler
from src.scorer.algorithm import get_scorer
from src.notifier.email import get_notifier
from src.feedback.service import get_feedback_service

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/smzdm.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def run_monitor():
    """运行监控主流程"""
    logger.info("=" * 50)
    logger.info("开始什么值得买好价监控")
    logger.info("=" * 50)
    
    try:
        # 1. 加载配置
        config = get_config()
        logger.info("配置加载完成")
        
        # 2. 初始化数据库
        db_path = config.get('storage', 'db_path', default='./data/smzdm.db')
        db = get_db(db_path)
        logger.info("数据库初始化完成")
        
        # 3. 初始化代理管理器
        proxy_config = config.get('proxy', default={})
        proxy_manager = get_proxy_manager(proxy_config)
        logger.info(f"代理管理器初始化完成，可用代理: {len(proxy_manager.proxies)} 个")
        
        # 4. 初始化爬虫
        crawler_config = {
            'items_per_page': config.get('monitor', 'items_per_page', default=20),
            'max_pages': config.get('monitor', 'max_pages', default=50),
            'max_history_hours': config.get('monitor', 'max_history_hours', default=24),
        }
        crawler = get_crawler(crawler_config, proxy_manager)
        logger.info("爬虫初始化完成")
        
        # 5. 初始化评分器
        scorer_config = config.get('scorer', default={})
        scorer = get_scorer(scorer_config)
        logger.info("评分器初始化完成")
        
        # 6. 初始化通知器
        notifier_config = config.get('notifier', 'email', default={})
        notifier = get_notifier(notifier_config)
        logger.info("通知器初始化完成")
        
        # 7. 获取过滤配置
        filter_config = config.get('filter', default={})
        
        # 8. 抓取商品
        logger.info("开始抓取商品...")
        max_pages = config.get('monitor', 'max_pages', default=50)
        max_hours = config.get('monitor', 'max_history_hours', default=24)
        products = crawler.fetch_multiple_pages(max_pages=max_pages, max_hours=max_hours)
        logger.info(f"抓取完成，共 {len(products)} 个商品")
        
        if not products:
            logger.warning("未抓取到任何商品")
            return
        
        # 9. 过滤商品
        logger.info("开始过滤商品...")
        filtered_products = scorer.filter_products(products, filter_config)
        logger.info(f"过滤后剩余 {len(filtered_products)} 个商品")
        
        # 10. 计算评分
        logger.info("开始计算评分...")
        scored_products = []
        for product in filtered_products:
            # 获取价格历史
            price_history = db.get_price_history(product['id'])
            
            # 计算评分
            score = scorer.calculate_score(product, price_history)
            product['score'] = score
            
            # 保存到数据库
            db.save_product(product)
            
            # 筛选高分商品
            min_score = config.get('scorer', 'min_composite_score', default=45)
            if score >= min_score:
                # 检查通知次数
                notification_count = db.get_notification_count(product['id'])
                max_notifications = config.get('notifier', 'limits', 'max_notifications_per_item', default=2)
                
                if notification_count < max_notifications:
                    scored_products.append(product)
                    db.save_notification(product['id'])
        
        logger.info(f"筛选出 {len(scored_products)} 个高分商品")
        
        # 11. 发送通知
        if scored_products:
            # 按评分排序
            scored_products.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            # 限制数量
            max_items = config.get('notifier', 'limits', 'max_items_per_batch', default=20)
            scored_products = scored_products[:max_items]
            
            # 获取反馈URL
            feedback_config = config.get('feedback', default={})
            feedback_url = feedback_config.get('base_url', '')
            
            # 发送邮件
            success = notifier.send_notification(scored_products, feedback_url)
            if success:
                logger.info("通知发送成功")
            else:
                logger.warning("通知发送失败")
        else:
            logger.info("没有需要通知的商品")
        
        # 12. 清理旧数据
        if config.get('storage', 'auto_cleanup', default=True):
            retention_days = config.get('storage', 'retention_days', default=30)
            db.cleanup_old_data(retention_days)
            logger.info(f"已清理 {retention_days} 天前的旧数据")
        
        logger.info("=" * 50)
        logger.info("监控完成")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"监控过程出错: {e}", exc_info=True)

def run_feedback_server():
    """运行反馈服务"""
    config = get_config()
    db_path = config.get('storage', 'db_path', default='./data/smzdm.db')
    db = get_db(db_path)
    
    feedback_config = config.get('feedback', default={})
    port = feedback_config.get('port', 5000)
    
    service = get_feedback_service(feedback_config, db)
    service.start(port=port)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='什么值得买好价监控系统')
    parser.add_argument('--monitor', action='store_true', help='运行监控')
    parser.add_argument('--feedback', action='store_true', help='运行反馈服务')
    parser.add_argument('--config', type=str, help='配置文件路径')
    
    args = parser.parse_args()
    
    # 重新加载配置
    if args.config:
        reload_config(args.config)
    
    if args.feedback:
        # 运行反馈服务
        run_feedback_server()
    else:
        # 运行监控
        run_monitor()

if __name__ == '__main__':
    main()
