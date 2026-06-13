import mysql.connector

try:
    mydb = mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="password",
        port="3306",
        database='satilite'
    )
    mycursor = mydb.cursor()

    create_table_query = """
    CREATE TABLE IF NOT EXISTS predictions (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_email VARCHAR(50),
        image_name VARCHAR(255),
        predicted_image VARCHAR(255),
        detected_classes TEXT,
        recommended_crop TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    mycursor.execute(create_table_query)
    mydb.commit()
    print("Successfully created the 'predictions' table!")
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'mydb' in locals() and mydb.is_connected():
        mycursor.close()
        mydb.close()
