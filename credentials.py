import sqlite3

conn = sqlite3.connect("users.db")
cursor = conn.cursor()

#cursor.execute("drop table cattles")

cursor.execute('''
        CREATE TABLE IF NOT EXISTS cattles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cattle_type TEXT NOT NULL,
            cattle_name TEXT NOT NULL,
            breed TEXT NOT NULL,
            vet_visit TEXT,
            age INTEGER,
            health_notes TEXT
        )
    ''')

#cursor.execute("INSERT INTO cattles(cattle_type, cattle_name, breed, vet_visit, age, health_notes) VALUES('Cow','Sindhu','Jersey','2026-01-12',3,' ')")

cursor.execute(
    "select * from cattles"
)

result = cursor.fetchall()

print(result)

conn.commit()
conn.close()
