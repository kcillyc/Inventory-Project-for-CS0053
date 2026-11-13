#importing SQLite library
import sqlite3
#import date time libary 
from datetime import datetime

#declaration of database name
DB = "inventory.db"

#creation of the database
def create_database(db_path=None, *, announce=True):
    """Initialize the team's original schema at the requested database path."""
    connection = sqlite3.connect(DB if db_path is None else db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    #creation of cursor
    cursor = connection.cursor()

    #Products Table
    cursor.execute("""CREATE TABLE IF NOT EXISTS products(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    unit_costs_cents INTEGER NOT NULL CHECK (unit_costs_cents >= 0),
    reorder_level INTEGER NOT NULL CHECK (reorder_level >= 0),
    version INTEGER NOT NULL DEFAULT 1,
    archived INTEGER NOT NULL DEFAULT 0)""")

    #Movements Table
    cursor.execute("""CREATE TABLE IF NOT EXISTS movements(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    delta INTEGER NOT NULL,
    balance INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id))""")

    #save changes
    connection.commit()
    #close tables
    connection.close() 
    if announce:
        print("Database has been Created")
     

#function to add products
def addprod(sku, name, category, quantity, unit_costs_cents, reorder_level):
    connection = sqlite3.connect(DB)

    cursor = connection.cursor()

    cursor.execute("""INSERT INTO products
        (sku, name, category, quantity, unit_costs_cents, reorder_level )
        VALUES (?, ?, ?, ?, ?, ?)""",
        (sku, name, category, quantity, unit_costs_cents, reorder_level))

    #saves changes
    connection.commit()
    #closes
    connection.close()
    print("Product Added Successfully")

#shows selected products
def showprod():
    connection = sqlite3.connect(DB)

    cursor = connection.cursor()

    cursor.execute("""SELECT
        id, sku, name, category, quantity, unit_costs_cents
        FROM products WHERE archived = 0""")

    # collects all matching products
    products = cursor.fetchall()

    # prints each product
    for product in products:
        print(product)

    connection.close()

#records product movement
def recmove(product_id, amount, reason):
    connection = sqlite3.connect(DB)
    connection.execute("PRAGMA foreign_keys = ON")

    cursor = connection.cursor()

    #find product
    cursor.execute("""SELECT
        sku, name, quantity FROM products
        WHERE id = ? AND archived = 0""", (product_id,))
    product =  cursor.fetchone()

    #if product is not found or not in system
    if product is None:
        print("Product not found")
        connection.close()
        return

    sku, name, current_quantity = product
    new_quantity = current_quantity + amount

    #prevent negative quantity
    if new_quantity < 0:
        print("Error: No Stock Available")
        connection.close()
        return

    #update product quantity
    cursor.execute("""UPDATE products
        SET quantity = quantity +?, version = version + 1 WHERE id = ?""",
        (amount, product_id))

    #saves movement history
    cursor.execute("""INSERT INTO movements
        (product_id, sku, name, delta, balance, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""", 
        (product_id, sku, name, amount, new_quantity, reason,
        datetime.now().isoformat(timespec="seconds")))
    connection.commit()
    connection.close()

    print("Stock movement successfully recorded")

if __name__ == "__main__":
    # Keep the original teammate demonstration available when run explicitly.
    # Importing this module to reuse its schema must never seed or change stock.
    create_database()
    addprod("NB001", "Notebook", "School Supplies", 20, 5000, 5)
    recmove(1, 10, "Supplier delivery")
    recmove(1, -5, "Issued to classroom")
    showprod()
