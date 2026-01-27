import pytest
import asyncio
import sys
import os
import json
import time


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from spade.message import Message
from agents.analyzer import AnalyzerAgent
from agents.defender import DefenderAgent
from tests.integration.integratoin import SpyWorker # z testów integracyjnych 

class FailDefender(DefenderAgent):
    """
    Defender, który ma pecha. Zawsze zwraca porażkę drona.
    Potrzebny, aby wymusić na Analyzerze wezwanie Workera (człowieka).
    """
    async def activate_drones(self, coords, target_type, target_jid=None):
        print(f"[FailDefender] DRON: Start lotu do {coords}... (SYMULACJA AWARII)")
        await asyncio.sleep(0.5)
        print(f"[FailDefender] DRON: AWARIA! Akcja zakończona porażką.")
        return False # Zawsze False


@pytest.mark.asyncio
async def test_mission_bison_rescue_full_loop():
    """
    SCENARIUSZ E2E: "Ucieczka Benka"
    Testujemy pełną ścieżkę: Wykrycie -> Dron (Porażka) -> Wezwanie Człowieka.
    """
    
    analyzer_jid = "analyzer_acc@localhost"
    defender_jid = "defender_acc@localhost"
    worker_jid = "worker_acc@localhost"
    passw = "password"

    # Używamy SpyWorkera (żeby czytać wiadomości) i FailDefendera (żeby dron spadł)
    worker = SpyWorker(worker_jid, passw, analyzer_jid, forced_coords={"x": 50, "y": 50})
    defender = FailDefender(defender_jid, passw)
    analyzer = AnalyzerAgent(analyzer_jid, passw, defender_jid, worker_jid)

    await defender.start()
    await worker.start()
    await analyzer.start()

    analyzer.workers_registry[worker_jid] = {"coords": {"x": 50, "y": 50}, "last_seen": time.time()}

    try:
        #  Żubr poza granicą
        print("\n[E2E] Żubr przekracza granicę!")
        bison_msg = Message(to=analyzer_jid)
        bison_msg.set_metadata("performative", "inform")
        bison_payload = {
            "name": "Benek_Uciekinier",
            "coords": {"x": 120, "y": 80},
            "health": "spokojny",
            "sender": "bison_real@localhost"
        }
        bison_msg.body = json.dumps(bison_payload)
        
        await analyzer.container.send(bison_msg, analyzer)

        # awaria drona  reakcja workera
        await asyncio.sleep(4)

        # Analyzer zapamiętał incydent?
        incident_key = "ESCAPE_Benek_Uciekinier"
        assert incident_key in analyzer.incident_memory, "Analyzer nie zarejestrował ucieczki!"
        
        # Czy Worker otrzymał wezwanie
        messages = worker.received_messages
        help_msgs = [m for m in messages if m.get("type") == "HELP_REQUIRED"]
        
        if not help_msgs:
            print(f"[DEBUG] Odebrane przez workera: {messages}")

        assert len(help_msgs) > 0, "Worker nie otrzymał wezwania pomocy (Mimo porażki drona)!"
        last_alert = help_msgs[-1]
        
        assert last_alert["is_bison"] is True
        assert last_alert["coords"]["x"] == 120
        
        print("[E2E] SUKCES: Dron zawiódł, Worker został wezwany.")

    finally:
        await analyzer.stop()
        await defender.stop()
        await worker.stop()


@pytest.mark.asyncio
async def test_stress_multiple_sensors():
    """
    STRESS TEST: "Zmasowany atak danych"
    """
    analyzer_jid = "analyzer_stress@localhost"
    #  Używamy poprawnych JIDów dla dependency injection, 
    # inaczej Analyzer wyrzuci błąd przy próbie wysłania raportu
    analyzer = AnalyzerAgent(analyzer_jid, "pass", "def_dummy@localhost", "work_dummy@localhost")
    await analyzer.start()

    try:
        print("\n[STRESS] Wysyłanie 50 zgłoszeń...")
        for i in range(50):
            msg = Message(to=analyzer_jid)
            msg.set_metadata("performative", "inform")
            # trzeba ustawić nadawcę, inaczej SPADE w logach krzyczy "from=None"
            msg.sender = f"sensor_{i}@localhost" 
            
            payload = {
                "sensor_id": f"sensor_{i}",
                "coords": {"x": i, "y": i},
                "type": "camera",
                "metadata": {"detected_object": "wolf"}
            }
            msg.body = json.dumps(payload)
            
            await analyzer.container.send(msg, analyzer)
            await asyncio.sleep(0.01)

        await asyncio.sleep(3)

        count = len(analyzer.incident_memory)
        print(f"[STRESS] Analyzer przetworzył {count}/50 incydentów.")
        
        assert count > 40, "System zgubił zbyt wiele wiadomości pod obciążeniem!"

    finally:
        await analyzer.stop()