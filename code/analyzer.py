import spade
import json
import asyncio
import random
import time
from spade.message import Message
from spade.behaviour import CyclicBehaviour
import math
import config

RESERVE_CONFIG = config.RESERVE_CONFIG

class AnalyzerAgent(spade.agent.Agent):
    def __init__(self, jid, password, defender_jid, worker_jid, *args, **kwargs):
        super().__init__(jid, password, *args, **kwargs)
        self.defender_jid = defender_jid
        self.worker_jid = worker_jid
        # Pamięć: {sensor_id: {"last_time": timestamp, "escalated": bool}} wazne
        self.incident_memory = {}
        self.workers_registry = {} 

    # ---Logika agenta

    async def report_to_worker(self, report_type, details):
        msg = Message(to=self.worker_jid)
        msg.set_metadata("performative", "inform")
        msg.set_metadata("protocol", "fipa-query")
        payload = {
            "report_type": report_type,
            "timestamp": time.time(),
            "data": details
        }
        msg.body = json.dumps(payload)
        await self.send(msg)
        print(f"[Analyzer] Raport ({report_type}) wysłany do głównego Workera.")

    async def handle_defender_feedback(self, msg):
        data = json.loads(msg.body)
        if data.get("critical_alarm"):
            print("[Analyzer] !!! ALARM KRYTYCZNY !!! Szukam najbliższego pracownika...")
            await self.dispatch_nearest_worker(data.get("coords"))
        elif data.get("success"):
            print("[Analyzer] Akcja zakończona sukcesem.")

    async def dispatch_nearest_worker(self, danger_coords):
        if not self.workers_registry:
            print("[Analyzer] Brak dostępnych pracowników w rejestrze!")
            return

        best_worker = None
        min_dist = float('inf')
        #matematyka coś spróbowałem wykminić
        for w_jid, info in self.workers_registry.items():
            w_coords = info["coords"]
            dist = math.sqrt((w_coords['x'] - danger_coords['x'])**2 + 
                             (w_coords['y'] - danger_coords['y'])**2)
            if dist < min_dist:
                min_dist = dist
                best_worker = w_jid

        if best_worker:
            print(f"[Analyzer] WEZWANIE: {best_worker} jest najbliżej ({round(min_dist,1)}m).")
            msg = Message(to=best_worker)
            msg.set_metadata("performative", "request")
            msg.body = json.dumps({"type": "HELP_REQUIRED", "coords": danger_coords})
            await self.send(msg)

    async def check_bison_safety(self, data):
        coords = data.get("coords")
        name = data.get("name", "Unknown Bison")
        if (coords["x"] < RESERVE_CONFIG["X_MIN"] or coords["x"] > RESERVE_CONFIG["X_MAX"] or 
            coords["y"] < RESERVE_CONFIG["Y_MIN"] or coords["y"] > RESERVE_CONFIG["Y_MAX"]): # to globalnie
            details = {"name": name, "coords": coords, "reason": "out_of_bounds"}
            print(f"[Analyzer] ALERT: Żubr {name} poza rezerwatem!")
            await self.report_to_worker("BISON_ESCAPE", details)
            await self.send_to_defender("bison_escape", coords, None, force_drone=True)

    async def process_incident(self, s_id, danger, coords):

        if danger == "human":
            is_worker = False
            for w_jid, info in self.workers_registry.items():
                w_coords = info["coords"]
                
                dist = math.sqrt((w_coords['x'] - coords['x'])**2 + 
                                 (w_coords['y'] - coords['y'])**2)
                
                
                if dist < 15.0:
                    print(f"[Analyzer] Wykryto człowieka w {s_id}, ale to nasz pracownik {w_jid}. Ignoruję.")
                    is_worker = True
                    break
            
            if is_worker:
                return
        now = time.time()
        incident = self.incident_memory.get(s_id)

        # eskalacja to samo zagrozenie w ciągu 20 s
        if incident and (now - incident["last_time"] < 20):
            if not incident["escalated"]:
                print(f"[Analyzer] ESKALACJA: {danger} nadal w {s_id}. Ślemy drona.")
                await self.report_to_worker("ESCALATION_STARTED", {"danger": danger, "sensor": s_id})
                await self.send_to_defender(danger, coords, s_id, force_drone=True)
                self.incident_memory[s_id]["escalated"] = True
        else:
            print(f"[Analyzer] Wykryto {danger} w {s_id}. Próba stacjonarna.")
            self.incident_memory[s_id] = {"last_time": now, "escalated": False}
            await self.report_to_worker("NEW_INCIDENT", {"danger": danger, "location": coords})
            await self.send_to_defender(danger, coords, s_id, force_drone=False)

    async def send_to_defender(self, danger, coords, s_id, force_drone):
        msg = Message(to=self.defender_jid)
        msg.set_metadata("performative", "request")
        msg.body = json.dumps({
            "danger_type": danger,
            "sensor_jid": str(s_id) if s_id else None,
            "coords": coords,
            "force_drone": force_drone
        })
        await self.send(msg)
        print(f"[Analyzer] Zadanie dla Defendera: {danger} (Wymuś drona: {force_drone})")

    # -- behav

    class ReceiveDataBehav(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                # Defender
                if str(msg.sender) == str(self.agent.defender_jid):
                    await self.agent.handle_defender_feedback(msg)
                    return

                content = json.loads(msg.body)
                sender_jid = str(msg.sender)

                #  pozycja workera
                if "worker_name" in content:
                    self.agent.workers_registry[sender_jid] = {
                        "coords": content.get("coords"),
                        "last_seen": time.time()
                    }
                    return

                # Żubr też poprawić i sprawdzać pozycje
                if "health" in content:
                    await self.agent.check_bison_safety(content)
                    return

                #   Sensor
                s_id = content.get("sensor_id")
                if s_id:
                    coords = content.get("coords")
                    meta = content.get("metadata", {})
                    detected = meta.get("detected_object") or meta.get("audio_type")

                    if detected and detected not in ["none"]:
                        await self.agent.process_incident(s_id, detected, coords)
                    else:
                        if s_id in self.agent.incident_memory:
                            print(f"[Analyzer] Sektor {s_id} bezpieczny. Czyszczę pamięć.")
                            del self.agent.incident_memory[s_id]

    async def setup(self):
        print(f"AnalyzerAgent {self.jid} (Centrum Decyzyjne) wystartował.")
        self.add_behaviour(self.ReceiveDataBehav())