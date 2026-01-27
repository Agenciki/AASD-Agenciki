import pytest
import asyncio
import sys
import os
import json
import time


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from spade.message import Message
from spade.behaviour import CyclicBehaviour
from agents.analyzer import AnalyzerAgent
from agents.worker import WorkerAgent
from agents.defender import DefenderAgent
from agents.config import RESERVE_CONFIG



class SpyWorker(WorkerAgent):
    """
    Specjalna wersja Workera do testów. 
    Zapisalem odebrane wiadomości na liście, by sprawdzić w asercjach.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.received_messages = []

    class SpyReceiver(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=1)
            if msg:
                content = json.loads(msg.body)
                self.agent.received_messages.append(content)

    async def setup(self):
        await super().setup()
        self.add_behaviour(self.SpyReceiver())




@pytest.mark.asyncio
async def test_full_chain_sensor_to_analyzer():
    """
    SCENARIUSZ: Sensor wykrywa człowieka -> Analyzer zakłada kartotekę incydentu.
    Sprawdzamy: Czy Analyzer utworzył wpis w pamięci (incident_memory).
    """
    
    analyzer = AnalyzerAgent("analyzer_int1@localhost", "password", "defender@localhost", "worker@localhost")
    await analyzer.start()

    try:
        # 2. Symulujemy wiadomość od Sensora
        # Nie trzeba stawiać całego agenta Sensor, trzeba wyslac poprawny JSON
        fake_sensor_jid = "sensor_fake@localhost"
        sensor_msg = Message(to="analyzer_int1@localhost")
        sensor_msg.set_metadata("performative", "inform")
        sensor_msg.sender = fake_sensor_jid
        
        payload = {
            "sensor_id": fake_sensor_jid,
            "coords": {"x": 50, "y": 50},
            "type": "camera",
            "metadata": {"detected_object": "human"} 
        }
        sensor_msg.body = json.dumps(payload)

        
        await analyzer.container.send(sensor_msg, analyzer)

        
        await asyncio.sleep(2)

        
        assert fake_sensor_jid in analyzer.incident_memory
        incident = analyzer.incident_memory[fake_sensor_jid]
        assert incident["escalated"] is False 
    finally:
        await analyzer.stop()


@pytest.mark.asyncio
async def test_analyzer_dispatches_worker_on_alarm():
    """
    SCENARIUSZ: Analyzer ma krytyczny alarm -> Wzywa najbliższego Workera.
    Sprawdzamy: Czy Worker otrzymał wiadomość typu "HELP_REQUIRED".
    """
    
    analyzer = AnalyzerAgent("analyzer_int2@localhost", "password", "def@localhost", "work@localhost")
    
    worker = SpyWorker(
        "worker_spy@localhost", 
        "password", 
        analyzer_jid="analyzer_int2@localhost",
        forced_coords={"x": 10, "y": 10} 
    )

    await analyzer.start()
    await worker.start()

    # Ręczna rejestracja workera 
    analyzer.workers_registry["worker_spy@localhost"] = {
        "coords": {"x": 10, "y": 10},
        "last_seen": time.time()
    }

    try:
       
        danger_coords = {"x": 12, "y": 12} 
       
        await analyzer.dispatch_nearest_worker(danger_coords)
        await asyncio.sleep(2)
        # co odebrał Worker
        assert len(worker.received_messages) > 0
        last_msg = worker.received_messages[-1]
        
        assert last_msg["type"] == "HELP_REQUIRED"
        assert last_msg["coords"]["x"] == 12

    finally:
        await analyzer.stop()
        await worker.stop()


@pytest.mark.asyncio
async def test_bison_escape_integration():
    """
    SCENARIUSZ: Żubr wysyła pozycję poza rezerwatem -> Analyzer wysyła drona i raport.
    Sprawdzamy: Czy Analyzer wykrył ucieczkę i zareagował (wpis w pamięci + log).
    """
    analyzer = AnalyzerAgent("analyzer_int3@localhost", "password", "def@localhost", "work@localhost")
    await analyzer.start()

    try:
        bison_jid = "bison_escapee@localhost"
        msg = Message(to="analyzer_int3@localhost")
        msg.body = json.dumps({
            "name": "Uciekinier",
            "coords": {"x": 150, "y": 150}, 
            "health": "spokojny",
            "sender": bison_jid
        })
        
        
        await analyzer.container.send(msg, analyzer)

        await asyncio.sleep(2)

        
        #  analyzer zapamiętał incydent ucieczki
        incident_key = "ESCAPE_Uciekinier"
        assert incident_key in analyzer.incident_memory
        
        #czas zdarzenia jest świeży?
        assert time.time() - analyzer.incident_memory[incident_key]["last_time"] < 5

    finally:
        await analyzer.stop()