import asyncio
from trade_alpha.dao import init_db
from trade_alpha.predict import training_service

async def get_trainings():
    await init_db()
    trainings = await training_service.list_trainings()
    for t in trainings:
        print(f'{t.id} - {t.name}')

asyncio.run(get_trainings())
