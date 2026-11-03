-- Synthetic training records, not real warehouse measurements.
INSERT INTO categories (id, name) VALUES
    (1, 'Канцтовары'), (2, 'Расходные материалы');
INSERT INTO suppliers (id, name, phone) VALUES
    (1, 'Учебный поставщик А', '+7 000 000-00-01'),
    (2, 'Учебный поставщик Б', '+7 000 000-00-02');
INSERT INTO products (id, sku, name, category_id, unit, min_stock) VALUES
    (1, 'P-001', 'Бумага А4', 1, 'пачка', 20),
    (2, 'P-002', 'Картридж 12A', 2, 'шт.', 5),
    (3, 'P-003', 'Маркер черный', 1, 'шт.', 10);
INSERT INTO stock_movements
    (product_id, supplier_id, movement_date, kind, quantity, note) VALUES
    (1, 1, '2026-10-19', 'IN', 150, 'Учебное поступление'),
    (1, NULL, '2026-10-20', 'OUT', 30, 'Учебное списание'),
    (2, 2, '2026-10-21', 'IN', 3, 'Учебное поступление'),
    (3, 1, '2026-10-22', 'IN', 40, 'Учебное поступление'),
    (3, NULL, '2026-10-23', 'OUT', 12, 'Учебное списание');
