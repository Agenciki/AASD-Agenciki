import asyncio
import spade

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.sensor import SensorAgent 
from agents.analyzer import AnalyzerAgent
from agents.worker import WorkerAgent
from agents.defender import DefenderAgent

# sprawdzenie czy wykrywa workera
# imo jesli n a tych danych działa to na innych typach pewnie też

async def test_whitelisting():
    
    POZYCJA_TESTOWA = {"x": 50.0, "y": 50.0}

    
    worker = WorkerAgent("worker@localhost", "haslo", 
                         analyzer_jid="analyzer@localhost", 
                         forced_coords=POZYCJA_TESTOWA)
    
    
    sensor = SensorAgent("sensor_a@localhost", "haslo", 
                         analyzer_jid="analyzer@localhost", 
                         coords=POZYCJA_TESTOWA, 
                         test_mode=True) # Wymuszamy "human"

    
    analyzer = AnalyzerAgent("analyzer@localhost", "haslo", 
                         defender_jid="defender@localhost", 
                         worker_jid="worker@localhost")
    await analyzer.start()

    defender = DefenderAgent("defender@localhost", "haslo")
    await defender.start()
    
 
    await worker.start()
    await asyncio.sleep(2) 

    
    await sensor.start()

   
    await asyncio.sleep(10)



if __name__ == "__main__":
    spade.run(test_whitelisting())