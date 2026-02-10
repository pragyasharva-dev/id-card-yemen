import asyncio
from sqlalchemy import select, func
from services.db import engine, AsyncSessionLocal
from models.sql_models import Document, Verification

async def check_data():
    async with AsyncSessionLocal() as session:
        print("--- Checking Database Content ---")
        
        # Check Documents
        result = await session.execute(select(func.count(Document.id)))
        doc_count = result.scalar()
        print(f"Documents Count: {doc_count}")
        
        if doc_count > 0:
            result = await session.execute(select(Document).limit(5))
            docs = result.scalars().all()
            for doc in docs:
                print(f" - Doc ID: {doc.id}, Number: {doc.document_number}, Name: {doc.full_name_english}")

        # Check Verifications
        result = await session.execute(select(func.count(Verification.id)))
        ver_count = result.scalar()
        print(f"Verifications Count: {ver_count}")

        if ver_count > 0:
            result = await session.execute(select(Verification).limit(5))
            vers = result.scalars().all()
            for ver in vers:
                print(f" - Ver ID: {ver.id}, DocID: {ver.document_id}, Status: {ver.status}")
                
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_data())
