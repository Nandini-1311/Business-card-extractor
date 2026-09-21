import mysql.connector

user = input("MySQL user: ")
pw = input("Password: ")

for host in ["localhost", "127.0.0.1", "::1"]:
    try:
        c = mysql.connector.connect(host=host, port=3306, user=user, password=pw, connection_timeout=5)
        cur = c.cursor()
        cur.execute("SELECT @@hostname, @@port, @@version, CURRENT_USER()")
        print(host, "-> CONNECTED:", cur.fetchone())
        c.close()
    except Exception as e:
        print(host, "-> FAILED:", e)
