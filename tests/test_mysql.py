import json
from pathlib import Path
import unittest
import uuid

import mysql.connector
from database import Warehouse


@unittest.skipUnless(Path('test-config.json').exists(), 'No dedicated test connection config')
class MySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config=json.loads(Path('test-config.json').read_text())
        config.pop('database',None)
        cls.connection=mysql.connector.connect(**config,autocommit=True)
        cls.name='warehouse_test_'+uuid.uuid4().hex[:12]
        cur=cls.connection.cursor()
        cur.execute(f'CREATE DATABASE {cls.name} CHARACTER SET utf8mb4')
        cur.execute(f'USE {cls.name}')
        try:
            for file in ('schema.sql','seed.sql'):
                sql='\n'.join(s for s in Path(file).read_text().splitlines() if not s.strip().startswith('--'))
                for statement in sql.split(';'):
                    if statement.strip(): cur.execute(statement)
        except Exception:
            cur.execute(f'DROP DATABASE {cls.name}'); cls.connection.close(); raise
        finally: cur.close()
        cls.db=Warehouse(cls.connection)

    @classmethod
    def tearDownClass(cls):
        cur=cls.connection.cursor(); cur.execute(f'DROP DATABASE {cls.name}')
        cur.close(); cls.connection.close()

    def test_balances_and_search(self):
        self.assertEqual(int(self.db.products('Бумага')[0]['balance']),120)
        self.assertEqual(len(self.db.products(category_id=1)),2)
        self.assertEqual(self.db.products(low=True)[0]['sku'],'P-002')

    def test_reject_negative_stock(self):
        with self.assertRaises(ValueError):
            self.db.save_movement(dict(product_id=1,supplier_id=None,
                movement_date='2026-10-25',kind='OUT',quantity=121))
        self.assertEqual(int(self.db.products('Бумага')[0]['balance']),120)

    def test_report(self):
        row=next(r for r in self.db.report('2026-10-20','2026-10-23') if r['sku']=='P-001')
        self.assertEqual(tuple(int(row[k]) for k in ('opening','incoming','outgoing','closing')),(150,0,30,120))

    def test_crud(self):
        cid=self.db.save_reference('categories',{'name':'Временная'})
        self.db.save_reference('categories',{'name':'Измененная'},cid)
        self.assertTrue(any(r['name']=='Измененная' for r in self.db.reference('categories')))
        self.db.delete_reference('categories',cid)
        self.assertFalse(any(r['id']==cid for r in self.db.reference('categories')))


if __name__=='__main__': unittest.main(verbosity=2)
