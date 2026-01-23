import mysql.connector

def get_db_connection():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="1234",
            database="FlyTau",
            autocommit=True
        )
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
