import csv
from contextlib import contextmanager
from datetime import date

from validation import ensure_nonnegative, integer, iso_date, text


class Warehouse:
    """All mutations use transactions; product locks serialize stock changes."""

    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def transaction(self):
        self.connection.start_transaction(isolation_level='READ COMMITTED')
        cursor = self.connection.cursor(dictionary=True)
        try:
            yield cursor
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def query(self, sql, params=()):
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            cursor.close()

    def reference(self, table):
        if table not in ('categories', 'suppliers', 'products'):
            raise ValueError('Неизвестный справочник.')
        return self.query(f'SELECT * FROM {table} ORDER BY name, id')

    def save_reference(self, table, values, record_id=None):
        if table == 'categories':
            data = {'name': text(values['name'], 'Название', 100)}
        elif table == 'suppliers':
            phone = str(values.get('phone', '')).strip()
            if len(phone) > 40:
                raise ValueError('Телефон: не более 40 символов.')
            data = {'name': text(values['name'], 'Название', 150), 'phone': phone}
        elif table == 'products':
            data = dict(sku=text(values['sku'], 'Артикул', 40),
                        name=text(values['name'], 'Название', 150),
                        category_id=integer(values['category_id'], 'Категория', 1),
                        unit=text(values['unit'], 'Единица измерения', 20),
                        min_stock=integer(values['min_stock'], 'Минимум'))
        else:
            raise ValueError('Неизвестный справочник.')
        with self.transaction() as cur:
            if record_id is None:
                cols = ', '.join(data)
                placeholders = ', '.join(['%s'] * len(data))
                cur.execute(f'INSERT INTO {table} ({cols}) VALUES ({placeholders})', tuple(data.values()))
                return cur.lastrowid
            assignments = ', '.join(f'{key}=%s' for key in data)
            cur.execute(f'UPDATE {table} SET {assignments} WHERE id=%s', (*data.values(), record_id))
            return record_id

    def delete_reference(self, table, record_id):
        if table not in ('categories', 'suppliers', 'products'):
            raise ValueError('Неизвестный справочник.')
        with self.transaction() as cur:
            cur.execute(f'DELETE FROM {table} WHERE id=%s', (record_id,))

    def products(self, search='', category_id=None, low=False):
        # INSTR treats user input as literal text, including % and _.
        sql = '''SELECT p.*, c.name AS category,
          COALESCE(SUM(CASE WHEN m.kind='IN' THEN m.quantity ELSE -m.quantity END),0) AS balance
          FROM products p JOIN categories c ON c.id=p.category_id
          LEFT JOIN stock_movements m ON m.product_id=p.id
          WHERE INSTR(LOWER(p.name), LOWER(%s))>0'''
        params = [search.strip()]
        if category_id is not None:
            sql += ' AND p.category_id=%s'
            params.append(category_id)
        sql += ' GROUP BY p.id, c.name'
        if low:
            sql += ' HAVING balance < p.min_stock'
        return self.query(sql + ' ORDER BY p.name, p.id', params)

    def movements(self, start='1000-01-01', end='9999-12-31'):
        start, end = iso_date(start), iso_date(end)
        if start > end:
            raise ValueError('Начало периода позже конца.')
        return self.query('''SELECT m.*, p.name AS product, p.unit,
            COALESCE(s.name,'—') AS supplier FROM stock_movements m
            JOIN products p ON p.id=m.product_id
            LEFT JOIN suppliers s ON s.id=m.supplier_id
            WHERE m.movement_date BETWEEN %s AND %s
            ORDER BY m.movement_date, m.id''', (start, end))

    def save_movement(self, values, record_id=None):
        pid = integer(values['product_id'], 'Товар', 1)
        kind = values['kind']
        if kind not in ('IN', 'OUT'):
            raise ValueError('Тип операции должен быть IN или OUT.')
        supplier = integer(values['supplier_id'], 'Поставщик', 1) if kind == 'IN' else None
        quantity = integer(values['quantity'], 'Количество', 1)
        day = iso_date(values['movement_date'])
        note = str(values.get('note', '')).strip()
        if len(note) > 250:
            raise ValueError('Примечание: не более 250 символов.')
        # Existing movements retain their product; this avoids cross-product lock cycles.
        with self.transaction() as cur:
            cur.execute('SELECT id FROM products WHERE id=%s FOR UPDATE', (pid,))
            if cur.fetchone() is None:
                raise ValueError('Товар не найден.')
            if record_id is None:
                cur.execute('''INSERT INTO stock_movements
                    (product_id,supplier_id,movement_date,kind,quantity,note)
                    VALUES (%s,%s,%s,%s,%s,%s)''', (pid,supplier,day,kind,quantity,note))
                record_id = cur.lastrowid
            else:
                cur.execute('SELECT product_id FROM stock_movements WHERE id=%s FOR UPDATE', (record_id,))
                existing = cur.fetchone()
                if not existing or existing['product_id'] != pid:
                    raise ValueError('При редактировании нельзя менять товар; создайте новую операцию.')
                cur.execute('''UPDATE stock_movements SET supplier_id=%s,
                    movement_date=%s,kind=%s,quantity=%s,note=%s WHERE id=%s''',
                    (supplier,day,kind,quantity,note,record_id))
            self._check_history(cur, pid)
            return record_id

    @staticmethod
    def _check_history(cur, pid):
        cur.execute('''SELECT quantity,kind FROM stock_movements
            WHERE product_id=%s ORDER BY movement_date,id''', (pid,))
        return ensure_nonnegative(cur.fetchall())

    def delete_movement(self, record_id):
        rows = self.query('SELECT product_id FROM stock_movements WHERE id=%s', (record_id,))
        if not rows:
            raise ValueError('Операция не найдена.')
        pid = rows[0]['product_id']
        with self.transaction() as cur:
            cur.execute('SELECT id FROM products WHERE id=%s FOR UPDATE', (pid,))
            cur.fetchone()
            cur.execute('DELETE FROM stock_movements WHERE id=%s', (record_id,))
            self._check_history(cur, pid)

    def report(self, start, end):
        start, end = iso_date(start), iso_date(end)
        if start > end:
            raise ValueError('Начало периода позже конца.')
        return self.query('''SELECT p.sku,p.name,p.unit,
          COALESCE(SUM(CASE WHEN m.movement_date < %s
            THEN IF(m.kind='IN',m.quantity,-m.quantity) ELSE 0 END),0) AS opening,
          COALESCE(SUM(CASE WHEN m.movement_date BETWEEN %s AND %s AND m.kind='IN'
            THEN m.quantity ELSE 0 END),0) AS incoming,
          COALESCE(SUM(CASE WHEN m.movement_date BETWEEN %s AND %s AND m.kind='OUT'
            THEN m.quantity ELSE 0 END),0) AS outgoing,
          COALESCE(SUM(CASE WHEN m.movement_date<=%s
            THEN IF(m.kind='IN',m.quantity,-m.quantity) ELSE 0 END),0) AS closing
          FROM products p LEFT JOIN stock_movements m ON m.product_id=p.id
          GROUP BY p.id ORDER BY p.name,p.id''', (start,start,end,start,end,end))


def export_csv(path, rows, columns):
    # Prefix spreadsheet formula starters in text cells before writing CSV.
    with open(path, 'w', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerow([label for key, label in columns])
        for row in rows:
            result = []
            for key, label in columns:
                value = row[key]
                if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
                    value = "'" + value
                result.append(value)
            writer.writerow(result)
