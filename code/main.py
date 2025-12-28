import asyncio
from bison import *
from worker import *

WORKER_JID = "worker@localhost"
BISON_JID = "bison@localhost"




async def main():
 #haslo dowolne
    worker = WorkerAgent("worker@localhost", "haslo",analyzer_jid="analyzer@localhost")
    bison = BisonAgent("bison@localhost", "haslo",observers=["worker@localhost"])

    await worker.start()
    await bison.start()

    print("Test wystartował. Czekam na komunikację (Ctrl+C aby przerwać)...")
    
    while True:
        try:
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            break

    await worker.stop()
    await bison.stop()

if __name__ == "__main__":
    spade.run(main())