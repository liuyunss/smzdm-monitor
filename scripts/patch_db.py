"""Patch database.py to fix history dedup and cascade cleanup."""

with open('src/storage/database.py', 'r') as f:
    content = f.read()

# 1. Fix _upsert_product: dedup history records
old = '''    def _upsert_product(self, cursor, product: Dict):
        """单条商品 UPSERT + 价格历史 + 互动快照"""
        cursor.execute(\'\'\'
            INSERT INTO products
            (id, title, price, mall, url, channel_type, comments, collection, worthy, unworthy, score, category, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, price=excluded.price, mall=excluded.mall,
                url=excluded.url, channel_type=excluded.channel_type,
                comments=excluded.comments, collection=excluded.collection,
                worthy=excluded.worthy, unworthy=excluded.unworthy,
                score=excluded.score, category=excluded.category,
                updated_at=CURRENT_TIMESTAMP
        \'\'\', (
            product[\'id\'], product[\'title\'], product.get(\'price\', \'\'),
            product.get(\'mall\', \'\'), product.get(\'url\', \'\'),
            product.get(\'channel_type\', \'\'), product.get(\'comments\', 0),
            product.get(\'collection\', 0), product.get(\'worthy\', 0),
            product.get(\'unworthy\', 0), product.get(\'score\', 0),
            product.get(\'category\', \'\')
        ))
        if product.get(\'price\'):
            cursor.execute(\'\'\'
                INSERT INTO price_history (product_id, price)
                VALUES (?, ?)
            \'\'\', (product[\'id\'], product[\'price\']))
        cursor.execute(\'\'\'
            INSERT INTO engagement_history
            (product_id, comments, collection, worthy, unworthy)
            VALUES (?, ?, ?, ?, ?)
        \'\'\', (
            product[\'id\'], product.get(\'comments\', 0),
            product.get(\'collection\', 0), product.get(\'worthy\', 0),
            product.get(\'unworthy\', 0)
        ))'''

new = '''    def _upsert_product(self, cursor, product: Dict):
        """单条商品 UPSERT + 变化时记录历史"""
        cursor.execute(\'\'\'
            INSERT INTO products
            (id, title, price, mall, url, channel_type, comments, collection, worthy, unworthy, score, category, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, price=excluded.price, mall=excluded.mall,
                url=excluded.url, channel_type=excluded.channel_type,
                comments=excluded.comments, collection=excluded.collection,
                worthy=excluded.worthy, unworthy=excluded.unworthy,
                score=excluded.score, category=excluded.category,
                updated_at=CURRENT_TIMESTAMP
        \'\'\', (
            product[\'id\'], product[\'title\'], product.get(\'price\', \'\'),
            product.get(\'mall\', \'\'), product.get(\'url\', \'\'),
            product.get(\'channel_type\', \'\'), product.get(\'comments\', 0),
            product.get(\'collection\', 0), product.get(\'worthy\', 0),
            product.get(\'unworthy\', 0), product.get(\'score\', 0),
            product.get(\'category\', \'\')
        ))

        # 价格变化时才记录历史
        if product.get(\'price\'):
            cursor.execute(\'SELECT price FROM price_history WHERE product_id = ? ORDER BY recorded_at DESC LIMIT 1\', (product[\'id\'],))
            last = cursor.fetchone()
            if not last or last[0] != product[\'price\']:
                cursor.execute(\'INSERT INTO price_history (product_id, price) VALUES (?, ?)\',
                    (product[\'id\'], product[\'price\']))

        # 互动变化时才记录历史
        cursor.execute(\'SELECT comments, collection, worthy, unworthy FROM engagement_history WHERE product_id = ? ORDER BY recorded_at DESC LIMIT 1\', (product[\'id\'],))
        last = cursor.fetchone()
        new_vals = (product.get(\'comments\', 0), product.get(\'collection\', 0),
                    product.get(\'worthy\', 0), product.get(\'unworthy\', 0))
        if not last or (last[0], last[1], last[2], last[3]) != new_vals:
            cursor.execute(\'INSERT INTO engagement_history (product_id, comments, collection, worthy, unworthy) VALUES (?, ?, ?, ?, ?)\',
                (product[\'id\'],) + new_vals)'''

assert old in content, "Could not find old _upsert_product"
content = content.replace(old, new)
print("1. _upsert_product 历史去重已修复")

# 2. Fix cleanup_old_data: cascade delete
old_cleanup = '''    def cleanup_old_data(self, days: int = 30):
        """清理旧数据"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            since = datetime.now() - timedelta(days=days)
            
            # 清理旧价格历史
            cursor.execute(\'\'\'
                DELETE FROM price_history 
                WHERE recorded_at < ?
            \'\'\', (since,))
            
            # 清理旧互动历史
            cursor.execute(\'\'\'
                DELETE FROM engagement_history 
                WHERE recorded_at < ?
            \'\'\', (since,))
            
            # 注意：不清理 notifications，避免重置推送计数
            
            # 清理旧代理使用记录
            cursor.execute(\'\'\'
                DELETE FROM proxy_usage 
                WHERE used_at < ?
            \'\'\', (since,))'''

new_cleanup = '''    def cleanup_old_data(self, days: int = 30):
        """清理旧数据（级联删除关联表）"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            since = datetime.now() - timedelta(days=days)

            # 找到要删除的旧商品ID
            cursor.execute(\'SELECT id FROM products WHERE updated_at < ?\', (since,))
            old_ids = [r[0] for r in cursor.fetchall()]

            if old_ids:
                ph = ','.join('?' * len(old_ids))
                cursor.execute(f'DELETE FROM price_history WHERE product_id IN ({ph})', old_ids)
                cursor.execute(f'DELETE FROM engagement_history WHERE product_id IN ({ph})', old_ids)
                cursor.execute(f'DELETE FROM notifications WHERE product_id IN ({ph})', old_ids)
                cursor.execute(f'DELETE FROM feedback WHERE product_id IN ({ph})', old_ids)
                cursor.execute(f'DELETE FROM products WHERE id IN ({ph})', old_ids)
                logger.info(f"清理了 {len(old_ids)} 个过期商品及关联数据")'''

assert old_cleanup in content, "Could not find old cleanup_old_data"
content = content.replace(old_cleanup, new_cleanup)
print("2. cleanup_old_data 级联删除已修复")

with open('src/storage/database.py', 'w') as f:
    f.write(content)

print("done")
