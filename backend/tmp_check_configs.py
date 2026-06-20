import asyncio, httpx

async def main():
    async with httpx.AsyncClient(base_url='http://localhost:8000', timeout=5) as client:
        r = await client.get('/api/strategies')
        print(f'status={r.status_code}')
        print(f'headers={dict(r.headers)}')
        print(f'body={r.text[:500]}')

asyncio.run(main())
