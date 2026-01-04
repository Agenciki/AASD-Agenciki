import asyncio
import spade

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.bison import BisonAgent
from agents.analyzer import AnalyzerAgent
from agents.defender import DefenderAgent
from agents.worker import WorkerAgent

#sprawdzenie czy dron odstraszy żubra
async def main():
    
    B_JID = "bison@localhost"
    A_JID = "analyzer@localhost"
    D_JID = "defender@localhost"
    W_JID = "worker@localhost"
    PW = "haslo"


    worker = WorkerAgent(W_JID, PW, analyzer_jid=A_JID)
    defender = DefenderAgent(D_JID, PW)
    analyzer = AnalyzerAgent(A_JID, PW, defender_jid=D_JID, worker_jid=W_JID)
    
    await analyzer.start()
    await worker.start()
    await defender.start()
    

    #  Start Żubra w trybie "Ucieczka "
    # Podaje target_jid Defendera w Analyzerze, aby wiedział kogo ścigać
    bison = BisonAgent(B_JID, PW, name="Pukan", 
                       observers=[A_JID], 
                       forced_coords=[150, 150], 
                       ignore_drones=False)
    
    await bison.start()

    print("--- Symulacja uruchomiona: Żubr uciekł  ---")
    
    # cykl: Wykrycie -> Dron
    await asyncio.sleep(30)

    await bison.stop()
    await analyzer.stop()
    await defender.stop()
    await worker.stop()

if __name__ == "__main__":
    spade.run(main())