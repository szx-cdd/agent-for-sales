"""
数据库模块 - 客户管理和历史记录存储
使用SQLite数据库
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# 数据库文件路径
DB_PATH = Path(__file__).parent / "sales_agent.db"


class Database:
    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()

    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 客户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                company TEXT,
                industry TEXT,
                phone TEXT,
                email TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 客户画像历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                profile_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
            )
        """)

        # 聊天记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_histories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                source_type TEXT DEFAULT 'manual',
                source_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
            )
        """)

        # 分析历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_histories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                analysis_type TEXT NOT NULL,
                result TEXT NOT NULL,
                chat_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_company ON customers(company)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_histories_customer ON chat_histories(customer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analysis_histories_customer ON analysis_histories(customer_id)")

        conn.commit()
        conn.close()

    # ========== 客户管理 ==========

    def create_customer(self, name: str, company: str = None, industry: str = None,
                       phone: str = None, email: str = None, notes: str = None) -> int:
        """创建新客户，返回客户ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO customers (name, company, industry, phone, email, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, company, industry, phone, email, notes)
        )
        customer_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return customer_id

    def get_customer(self, customer_id: int) -> Optional[Dict]:
        """获取客户详情"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_customers(self, search: str = None, industry: str = None) -> List[Dict]:
        """获取客户列表，支持搜索"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM customers WHERE 1=1"
        params = []

        if search:
            query += " AND (name LIKE ? OR company LIKE ? OR phone LIKE ?)"
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern, search_pattern])

        if industry:
            query += " AND industry = ?"
            params.append(industry)

        query += " ORDER BY updated_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_customer(self, customer_id: int, **kwargs) -> bool:
        """更新客户信息"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 构建更新语句
        fields = []
        values = []
        for key, value in kwargs.items():
            if value is not None:
                fields.append(f"{key} = ?")
                values.append(value)

        if not fields:
            return False

        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(customer_id)

        cursor.execute(
            f"UPDATE customers SET {', '.join(fields)} WHERE id = ?",
            values
        )
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def delete_customer(self, customer_id: int) -> bool:
        """删除客户"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    # ========== 聊天记录管理 ==========

    def add_chat_history(self, customer_id: int, content: str,
                        source_type: str = 'manual', source_file: str = None) -> int:
        """添加聊天记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO chat_histories (customer_id, content, source_type, source_file)
               VALUES (?, ?, ?, ?)""",
            (customer_id, content, source_type, source_file)
        )
        chat_id = cursor.lastrowid

        # 更新客户更新时间
        cursor.execute(
            "UPDATE customers SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (customer_id,)
        )

        conn.commit()
        conn.close()
        return chat_id

    def get_chat_histories(self, customer_id: int, limit: int = None) -> List[Dict]:
        """获取客户的聊天记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """SELECT * FROM chat_histories
                   WHERE customer_id = ?
                   ORDER BY created_at DESC"""
        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, (customer_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_all_chat_content(self, customer_id: int) -> str:
        """获取客户所有聊天记录的合并内容"""
        histories = self.get_chat_histories(customer_id)
        if not histories:
            return ""

        contents = []
        for h in reversed(histories):  # 按时间正序
            time_str = h['created_at']
            contents.append(f"=== {time_str} ===\n{h['content']}")

        return "\n\n".join(contents)

    # ========== 分析历史管理 ==========

    def save_analysis(self, customer_id: int, analysis_type: str,
                     result: dict, chat_summary: str = None) -> int:
        """保存分析结果"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO analysis_histories (customer_id, analysis_type, result, chat_summary)
               VALUES (?, ?, ?, ?)""",
            (customer_id, analysis_type, json.dumps(result, ensure_ascii=False), chat_summary)
        )
        analysis_id = cursor.lastrowid

        # 更新客户更新时间
        cursor.execute(
            "UPDATE customers SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (customer_id,)
        )

        conn.commit()
        conn.close()
        return analysis_id

    def get_analysis_histories(self, customer_id: int, analysis_type: str = None) -> List[Dict]:
        """获取分析历史"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM analysis_histories WHERE customer_id = ?"
        params = [customer_id]

        if analysis_type:
            query += " AND analysis_type = ?"
            params.append(analysis_type)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # 解析JSON结果
        results = []
        for row in rows:
            row_dict = dict(row)
            try:
                row_dict['result'] = json.loads(row_dict['result'])
            except:
                pass
            results.append(row_dict)

        conn.close()
        return results

    def get_latest_analysis(self, customer_id: int, analysis_type: str = None) -> Optional[Dict]:
        """获取最新的分析结果"""
        histories = self.get_analysis_histories(customer_id, analysis_type)
        return histories[0] if histories else None

    # ========== 客户画像管理 ==========

    def save_profile(self, customer_id: int, profile_data: dict) -> int:
        """保存客户画像"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO customer_profiles (customer_id, profile_data)
               VALUES (?, ?)""",
            (customer_id, json.dumps(profile_data, ensure_ascii=False))
        )
        profile_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return profile_id

    def get_latest_profile(self, customer_id: int) -> Optional[Dict]:
        """获取最新的客户画像"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM customer_profiles
               WHERE customer_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (customer_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        row_dict = dict(row)
        try:
            row_dict['profile_data'] = json.loads(row_dict['profile_data'])
        except:
            pass
        return row_dict

    def get_statistics(self) -> Dict:
        """获取统计数据"""
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        # 客户总数
        cursor.execute("SELECT COUNT(*) as count FROM customers")
        stats['total_customers'] = cursor.fetchone()['count']

        # 今日新增
        cursor.execute("""
            SELECT COUNT(*) as count FROM customers
            WHERE DATE(created_at) = DATE('now')
        """)
        stats['today_new'] = cursor.fetchone()['count']

        # 本周活跃（有聊天记录或分析的）
        cursor.execute("""
            SELECT COUNT(DISTINCT customer_id) as count FROM (
                SELECT customer_id FROM chat_histories
                WHERE DATE(created_at) >= DATE('now', '-7 days')
                UNION
                SELECT customer_id FROM analysis_histories
                WHERE DATE(created_at) >= DATE('now', '-7 days')
            )
        """)
        stats['weekly_active'] = cursor.fetchone()['count']

        # 按行业统计
        cursor.execute("""
            SELECT industry, COUNT(*) as count FROM customers
            WHERE industry IS NOT NULL
            GROUP BY industry
            ORDER BY count DESC
        """)
        stats['by_industry'] = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return stats


# 全局数据库实例
db = Database()
