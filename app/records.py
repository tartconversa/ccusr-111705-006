"""公开目录收据，不把目录缺失解释为详情不存在。"""
import json
import sqlite3
from pathlib import Path

def save_catalog(path, items):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS catalog (id TEXT PRIMARY KEY, source TEXT NOT NULL, payload TEXT NOT NULL)')
        for item in items:
            db.execute('INSERT OR REPLACE INTO catalog VALUES (?, ?, ?)', (item['id'], item['source'], json.dumps(item, ensure_ascii=False)))
    return len(items)

def save_detail_entries(path, entries):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS detail_entries (visit_id INTEGER PRIMARY KEY, item_id TEXT NOT NULL, business_key TEXT NOT NULL, source TEXT NOT NULL, payload TEXT NOT NULL)')
        for entry in entries:
            if entry['catalog_fact']['identity'] != entry['id']:
                raise ValueError('catalog and detail identity mismatch')
            db.execute('INSERT INTO detail_entries (item_id, business_key, source, payload) VALUES (?, ?, ?, ?)',
                       (entry['id'], entry['detail_fact']['business_key'], entry['source'], json.dumps(entry, ensure_ascii=False)))
    return len(entries)

def read_detail_entries(path):
    with sqlite3.connect(path) as db:
        rows = db.execute('SELECT payload FROM detail_entries ORDER BY visit_id').fetchall()
    return [json.loads(row[0]) for row in rows]

def save_matrix_evidence(path, rows):
    """矩阵证据按（城市, 商户, 票根类别）业务键追加，任何一格都不去重。

    同一商户的不同票根类别是不同业务键；重跑同一格也保留为新的访问收据，
    便于客服核对页面结论是否发生变化。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS matrix_evidence ('
                   'visit_id INTEGER PRIMARY KEY, item_id TEXT NOT NULL, '
                   'business_key TEXT NOT NULL, requested_city TEXT NOT NULL, '
                   'requested_ticket TEXT NOT NULL, state TEXT NOT NULL, '
                   'source TEXT NOT NULL, payload TEXT NOT NULL)')
        for row in rows:
            detail = row['detail_fact']
            if row['catalog_fact']['identity'] != row['id']:
                raise ValueError('catalog and detail identity mismatch')
            if detail['business_key'] != f"{row['requested_city']}:{row['id']}:{row['requested_ticket']}":
                raise ValueError('business key must encode requested city and ticket category')
            if not row.get('evidence_only') or row.get('claim_submitted'):
                raise ValueError('matrix evidence must remain read-only')
            db.execute(
                'INSERT INTO matrix_evidence (item_id, business_key, requested_city, '
                'requested_ticket, state, source, payload) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (row['id'], detail['business_key'], row['requested_city'],
                 row['requested_ticket'], detail['state'], row['source'],
                 json.dumps(row, ensure_ascii=False)))
    return len(rows)

def read_matrix_evidence(path):
    with sqlite3.connect(path) as db:
        rows = db.execute('SELECT payload FROM matrix_evidence ORDER BY visit_id').fetchall()
    return [json.loads(row[0]) for row in rows]

def matrix_summary(path):
    """给客服的汇总计数：确认/未知分城市与票根类别列出，不掩盖未知。"""
    with sqlite3.connect(path) as db:
        totals = db.execute(
            'SELECT state, count(*) FROM matrix_evidence GROUP BY state').fetchall()
        unknown = db.execute(
            'SELECT item_id, requested_city, requested_ticket, payload '
            'FROM matrix_evidence WHERE state = ? ORDER BY visit_id', ('unknown',)).fetchall()
    unknown_rows = []
    for item_id, city, ticket, payload in unknown:
        reasons = json.loads(payload)['detail_fact']['reasons']
        unknown_rows.append({'item_id': item_id, 'city': city,
                             'ticket': ticket, 'reasons': reasons})
    return {'state_counts': dict(totals), 'unknown_cells': unknown_rows}
