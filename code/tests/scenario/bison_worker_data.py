import asyncio
import spade
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.bison import BisonAgent
from agents.worker import WorkerAgent


# sprawdzam czy żubr przesyla dane workerowi
async def main():
    
    B_JID = "bison@localhost"
    A_JID = "analyzer@localhost"
    W_JID = "worker@localhost"
    PW = "haslo"


    worker = WorkerAgent(W_JID, PW, analyzer_jid=A_JID)
    await worker.start()
    
    bison = BisonAgent(B_JID, PW, name="Pukan", observers=[W_JID])
    await bison.start()

    
    
    print("--- Symulacja uruchomiona: przepływ danych pomiędzy żubrem a  workerem ---")
    
    await asyncio.sleep(60)
    
    await bison.stop()
    await worker.stop()

if __name__ == "__main__":
    spade.run(main())