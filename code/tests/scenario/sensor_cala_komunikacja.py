import asyncio
import spade

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.sensor import SensorAgent 
from agents.analyzer import AnalyzerAgent
from agents.worker import WorkerAgent
from agents.defender import DefenderAgent

#sprawdzenie eskalacji

async def test_escalation():
    print("\n--- TEST ESKALACJI: ŚWIATŁO -> DRON -> CZŁOWIEK ---")
    
    
    S_COORDS = {"x": 10.0, "y": 10.0}
   
    W_COORDS = {"x": 90.0, "y": 90.0}

   
    analyzer = AnalyzerAgent("analyzer@localhost", "haslo", 
                             defender_jid="defender@localhost", 
                             worker_jid="worker@localhost")
    await analyzer.start()
    
    defender = DefenderAgent("defender@localhost", "haslo")
    await defender.start()

    worker = WorkerAgent("worker@localhost", "haslo", 
                         analyzer_jid="analyzer@localhost", 
                         forced_coords=W_COORDS)
    await worker.start()
    await asyncio.sleep(2)

    
    sensor = SensorAgent("sensor_a@localhost", "haslo", 
                         analyzer_jid="analyzer@localhost", 
                         coords=S_COORDS, 
                         test_mode=True)
    await sensor.start()

    #  KROKI ESKALACJI:
    # 0s:  Analyzer wyśle "force_drone=False" 
    # 20s:  Analyzer wyśle "force_drone=True" (Dron)
    # 40s: > Analyzer zawoła Workera
    
    print("[Test] Obserwacja eskalacji przez 50 sekund...")
    await asyncio.sleep(50)

    await sensor.stop()
    await worker.stop()
    await defender.stop()
    await analyzer.stop()


if __name__ == "__main__":
    spade.run(test_escalation())