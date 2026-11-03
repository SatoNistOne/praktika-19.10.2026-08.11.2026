-- MySQL 8.0.16+; run in an empty database selected by the client.
CREATE TABLE categories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE suppliers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(150) NOT NULL UNIQUE,
    phone VARCHAR(40) NOT NULL DEFAULT ''
) ENGINE=InnoDB;

CREATE TABLE products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    sku VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    category_id INT NOT NULL,
    unit VARCHAR(20) NOT NULL DEFAULT 'шт.',
    min_stock INT NOT NULL DEFAULT 0 CHECK (min_stock >= 0),
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
    INDEX idx_products_name (name)
) ENGINE=InnoDB;

CREATE TABLE stock_movements (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    supplier_id INT NULL,
    movement_date DATE NOT NULL,
    kind ENUM('IN','OUT') NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    note VARCHAR(250) NOT NULL DEFAULT '',
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
    CHECK ((kind = 'IN' AND supplier_id IS NOT NULL)
        OR (kind = 'OUT' AND supplier_id IS NULL)),
    INDEX idx_movements_product_date (product_id, movement_date, id)
) ENGINE=InnoDB;
