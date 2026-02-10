"""Check if images are stored in the database."""
import asyncio
from services.db import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as session:
        # Check documents table
        result = await session.execute(text(
            "SELECT id, document_number, LENGTH(front_image_data) as front_len, LENGTH(back_image_data) as back_len FROM documents LIMIT 5"
        ))
        rows = result.fetchall()
        print("=== Documents ===")
        for row in rows:
            print(f"  ID: {row[0]}, Doc#: {row[1]}, Front: {row[2]} bytes, Back: {row[3]} bytes")
        
        # Check verifications table
        result2 = await session.execute(text(
            "SELECT id, document_id, LENGTH(selfie_image_data) as selfie_len FROM verifications LIMIT 5"
        ))
        rows2 = result2.fetchall()
        print("\n=== Verifications ===")
        for row in rows2:
            print(f"  ID: {row[0]}, DocID: {row[1]}, Selfie: {row[2]} bytes")

if __name__ == "__main__":
    asyncio.run(check())
