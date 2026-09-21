import mysql.connector

user = input("MySQL user: ")
pw = input("Password: ")
c = mysql.connector.connect(host="localhost", port=3306, user=user, password=pw, database="qwen_vlm")
print("connected")
c.close()
