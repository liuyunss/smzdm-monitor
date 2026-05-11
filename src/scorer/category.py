"""
品类标签模块

从商品标题自动提取品类标签，用于偏好学习和评分加权。
"""
import re
from typing import Dict, List, Optional


# 品类关键词映射（优先级从高到低）
CATEGORY_KEYWORDS = {
    '母婴': ['母婴', '童装', '婴儿', '宝宝', '儿童', '奶瓶', '纸尿裤', '辅食', '玩具', '早教', '孕妇'],
    '数码': ['手机', '耳机', '蓝牙', '键盘', '鼠标', '显示器', '平板', '笔记本', '电脑', '充电', '数据线', 'U盘', '硬盘', 'SSD', '内存'],
    '家电': ['空调', '冰箱', '洗衣机', '电视', '风扇', '吸尘', '扫地', '烤箱', '微波炉', '电饭', '热水器', '净化器'],
    '食品': ['零食', '坚果', '牛奶', '咖啡', '茶叶', '饼干', '糖果', '饮料', '方便面', '速食', '蜂蜜', '水果'],
    '服饰': ['衣服', '裤子', '鞋', '袜', '帽', '外套', 'T恤', '卫衣', '运动鞋', '拖鞋', '羽绒'],
    '美妆': ['护肤', '面膜', '口红', '粉底', '防晒', '洗面', '精华', '乳液', '化妆', '香水'],
    '图书': ['书', '教材', '绘本', '小说', '杂志', '课程'],
    '运动': ['运动', '健身', '瑜伽', '跑步', '自行车', '游泳', '户外', '露营', '帐篷'],
    '家居': ['床', '沙发', '桌', '椅', '灯', '窗帘', '地毯', '收纳', '置物架', '衣架'],
    '宠物': ['猫粮', '狗粮', '猫砂', '宠物', '猫窝', '狗窝'],
    '汽车': ['车', '车载', '行车记录仪', '轮胎', '机油', '坐垫'],
    '酒水': ['酒', '白酒', '红酒', '啤酒', '洋酒'],
}


def tag_category(title: str) -> str:
    """从标题提取品类标签
    
    Args:
        商品标题
        
    Returns:
        品类名称，未匹配返回'其他'
    """
    if not title:
        return '其他'
    
    title_lower = title.lower()
    
    # 按品类逐个匹配
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in title_lower:
                return category
    
    return '其他'


def tag_categories_batch(products: List[Dict]) -> List[Dict]:
    """批量给商品打品类标签
    
    Args:
        products: 商品列表，每个商品需要有 'title' 字段
        
    Returns:
        添加了 'category' 字段的商品列表
    """
    for product in products:
        if 'category' not in product:
            product['category'] = tag_category(product.get('title', ''))
    return products


def get_all_categories() -> List[str]:
    """获取所有支持的品类名称"""
    return list(CATEGORY_KEYWORDS.keys()) + ['其他']
