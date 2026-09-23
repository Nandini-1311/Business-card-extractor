import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "mysql-1bcd42e5-singh-2386.d.aivencloud.com"),
        port=int(os.getenv("DB_PORT", 11331)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


def save_card(data: dict, image_path: str = None, raw_text: str = None) -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO business_cards
                (first_name, last_name, designation, email, phone, location, image_path, raw_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data.get("first_name"),
                data.get("last_name"),
                data.get("designation"),
                data.get("email"),
                data.get("phone"),
                data.get("location"),
                image_path,
                raw_text,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_all_cards():
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, first_name, last_name, designation, email, phone, location, created_at
            FROM business_cards
            ORDER BY id DESC
            """
        )
        return cursor.fetchall()
    finally:
        conn.close()


def delete_card_row(row_id: int) -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM business_cards WHERE id = %s", (row_id,))
        conn.commit()
    finally:
        conn.close()