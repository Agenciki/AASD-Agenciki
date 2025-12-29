import asyncio
import spade
from agents.bison import BisonAgent
from agents.analyzer import AnalyzerAgent
from agents.defender import DefenderAgent
from agents.worker import WorkerAgent
from agents.config import RESERVE_CONFIG

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
    

    # 2. Start Żubra w trybie "Ucieczka + Upór"
    # Podajemy target_jid Defendera w Analyzerze, aby wiedział kogo ścigać
    bison = BisonAgent(B_JID, PW, name="UpartyZubr", 
                       observers=[A_JID], 
                       forced_coords=[150, 150], 
                       ignore_drones=True)
    
    await bison.start()

    print("--- Symulacja uruchomiona: Żubr uciekł i ignoruje drony ---")
    
    # Czekamy na cykl: Wykrycie -> Dron -> Porażka -> Wezwanie Workera
    await asyncio.sleep(30)

    await bison.stop()
    await analyzer.stop()
    await defender.stop()
    await worker.stop()

if __name__ == "__main__":
    spade.run(main())