#!/usr/bin/env python3
"""
导出品类偏好数据为 JSON，供其他项目使用。

用法:
    python3 export_prefs.py                    # 导出到 stdout
    python3 export_prefs.py -o prefs.json      # 导出到文件
    python3 export_prefs.py --feedback         # 导出原始反馈记录
"""
import sqlite3
import json
import sys
import argparse

DB_PATH = './data/smzdm.db'


def export_preferences():
    """导出品类偏好"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute(
        'SELECT category, good_count, bad_count, manual_value, updated_at FROM category_pref'
    ).fetchall()
    
    result = {}
    for row in rows:
        good = row['good_count']
        bad = row['bad_count']
        manual = row['manual_value']
        
        # 计算权重
        if manual != 0:
            weight = max(0.1, min(2.0, 1.0 + manual / 100.0))
        elif good + bad > 0:
            weight = max(0.3, min(1.5, 0.3 + (good / (good + bad)) * 1.2))
        else:
            weight = 1.0
        
        result[row['category']] = {
            'good': good,
            'bad': bad,
            'manual': manual,
            'weight': round(weight, 2),
        }
    
    conn.close()
    return result


def export_feedback():
    """导出原始反馈记录"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute(
        'SELECT product_id, feedback_type, category, created_at FROM feedback ORDER BY created_at'
    ).fetchall()
    
    conn.close()
    return [dict(r) for r in rows]


def main():
    parser = argparse.ArgumentParser(description='导出偏好数据')
    parser.add_argument('-o', '--output', help='输出文件路径（默认 stdout）')
    parser.add_argument('--feedback', action='store_true', help='导出原始反馈记录')
    args = parser.parse_args()
    
    if args.feedback:
        data = export_feedback()
    else:
        data = export_preferences()
    
    output = json.dumps(data, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f'已导出到 {args.output}')
    else:
        print(output)


if __name__ == '__main__':
    main()
