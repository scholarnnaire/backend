import pymysql

connection = pymysql.connect(host='localhost',
                             user='root',
                             password='africa222',
                             database='quiz_cart',
                             cursorclass=pymysql.cursors.DictCursor)

with connection:
    with connection.cursor() as cursor:
        columns_to_add = [
            "ADD COLUMN `role` VARCHAR(255) DEFAULT 'Member'",
            "ADD COLUMN subject VARCHAR(255) DEFAULT 'General Science'",
            "ADD COLUMN status VARCHAR(255) DEFAULT 'Active'",
            "ADD COLUMN matches INT DEFAULT 0"
        ]
        for col in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE team_members {col}")
                print(f"Executed: {col}")
            except Exception as e:
                print(f"Error executing {col}: {e}")
    connection.commit()
print("Migration done")
