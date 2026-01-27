import spade
import json
import asyncio
import random
import time
from spade.message import Message
from spade.behaviour import CyclicBehaviour
import math
from . import config

RESERVE_CONFIG = config.RESERVE_CONFIG

class AnalyzerAgent(spade.agent.Agent):
    def __init__(self, jid, password, defender_jid, worker_jid, *args, **kwargs):
        super().__init__(jid, password, *args, **kwargs)
        self.defender_jid = defender_jid
        self.worker_jid = worker_jid
        # Pamięć: {sensor_id: {"last_time": timestamp, "escalated": bool}}
        self.incident_memory = {}
        self.workers_registry = {} 

    # --- Logika agenta (Teraz przyjmuje argument 'behaviour' do wysyłania) ---

    async def report_to_worker(self, report_type, details, behaviour):
        msg = Message(to=self.worker_jid)
        msg.set_metadata("performative", "inform")
        msg.set_metadata("protocol", "fipa-query")
        payload = {
            "report_type": report_type,
            "timestamp": time.time(),
            "data": details
        }
        msg.body = json.dumps(payload)
        
        await behaviour.send(msg)
        print(f"[Analyzer] Raport ({report_type}) wysłany do głównego Workera.")

    async def handle_defender_feedback(self, msg, behaviour):
        data = json.loads(msg.body)
        if data.get("critical_alarm"):
            print("[Analyzer] !!! ALARM KRYTYCZNY !!! Szukam najbliższego pracownika...")
            
            # --- POPRAWKA TUTAJ ---
            # Sprawdzamy, czy ten alarm dotyczył żubra
            danger_type = data.get("danger_type")
            is_bison_alert = (danger_type == "bison_escape")
            
            await self.dispatch_nearest_worker(
                data.get("coords"), 
                behaviour=behaviour, 
                is_bison=is_bison_alert
            )
            # ----------------------
            
        elif data.get("success"):
            print("[Analyzer] Akcja zakończona sukcesem.")

    async def dispatch_nearest_worker(self, danger_coords, behaviour, is_bison=False, target_jid=None):
        if not self.workers_registry:
            print("[Analyzer] Brak dostępnych pracowników w rejestrze!")
            return

        best_worker = None
        min_dist = float('inf')
        
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
            msg.body = json.dumps({
                "type": "HELP_REQUIRED", 
                "coords": danger_coords,
                "is_bison": is_bison,
                "target_jid": target_jid
            })
            
            await behaviour.send(msg)

    async def check_bison_safety(self, data, sender_jid, behaviour):
            coords = data.get("coords")
            name = data.get("name", "Unknown Bison")
            
            # Sprawdzenie granic
            if (coords["x"] < RESERVE_CONFIG["X_MIN"] or coords["x"] > RESERVE_CONFIG["X_MAX"] or 
                coords["y"] < RESERVE_CONFIG["Y_MIN"] or coords["y"] > RESERVE_CONFIG["Y_MAX"]):
                
                now = time.time()
                incident_key = f"ESCAPE_{name}"
                incident = self.incident_memory.get(incident_key)

                if incident and (now - incident["last_time"] > 15):
                    print(f"[Analyzer] !!! ŻUBR {name} IGNORUJE DRONY !!! Wzywam najbliższego pracownika.")
                    await self.dispatch_nearest_worker(coords, behaviour, is_bison=True, target_jid=sender_jid)
                    del self.incident_memory[incident_key]
                elif not incident:
                    print(f"[Analyzer] ALERT: Żubr {name} poza rezerwatem! Wysyłam drona.")
                    self.incident_memory[incident_key] = {"last_time": now, "escalated": False}
                    
                    await self.report_to_worker("BISON_ESCAPE", {"name": name, "coords": coords}, behaviour)
                    # Tutaj wysyłamy "bison_escape" jako danger_type
                    await self.send_to_defender("bison_escape", coords, None, force_drone=True, behaviour=behaviour)
        
    async def process_incident(self, s_id, danger, coords, behaviour):
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

        if not incident:
            print(f"[Analyzer] Wykryto {danger} w {s_id}. Próba stacjonarna.")
            self.incident_memory[s_id] = {
                "last_time": now, 
                "start_time": now,
                "escalated": False,
                "worker_called": False
            }
            await self.report_to_worker("NEW_INCIDENT", {"danger": danger, "location": coords}, behaviour)
            await self.send_to_defender(danger, coords, s_id, force_drone=False, behaviour=behaviour)
        
        else:
            duration = now - incident["start_time"]

            # 40 sekund -> człowiek
            if duration > 40:
                if not incident.get("worker_called"):
                    print(f"[Analyzer] !!! KRYTYCZNE !!! {danger} w {s_id} trwa {round(duration)}s. Wzywam PRACOWNIKA!")
                    await self.dispatch_nearest_worker(coords, behaviour, is_bison=False)
                    incident["worker_called"] = True
                return

            # 20 sekund -> dron
            elif duration > 20:
                if not incident["escalated"]:
                    print(f"[Analyzer] ESKALACJA: {danger} nadal w {s_id} ({round(duration)}s). Ślemy drona.")
                    await self.report_to_worker("ESCALATION_STARTED", {"danger": danger, "sensor": s_id}, behaviour)
                    await self.send_to_defender(danger, coords, s_id, force_drone=True, behaviour=behaviour)
                    incident["escalated"] = True
    
    async def send_to_defender(self, danger, coords, s_id, force_drone, behaviour):
        msg = Message(to=self.defender_jid)
        msg.set_metadata("performative", "request")
        msg.body = json.dumps({
            "danger_type": danger,
            "sensor_jid": str(s_id) if s_id else None,
            "coords": coords,
            "force_drone": force_drone
        })
        await behaviour.send(msg)
        print(f"[Analyzer] Zadanie dla Defendera: {danger} (Wymuś drona: {force_drone})")

    # -- Zachowanie (Behaviour) --

    class ReceiveDataBehav(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                if str(msg.sender) == str(self.agent.defender_jid):
                    await self.agent.handle_defender_feedback(msg, behaviour=self)
                    return

                content = json.loads(msg.body)
                sender_jid = str(msg.sender)

                if "worker_name" in content:
                    self.agent.workers_registry[sender_jid] = {
                        "coords": content.get("coords"),
                        "last_seen": time.time()
                    }
                    return

                if "health" in content:
                    await self.agent.check_bison_safety(content, str(msg.sender), behaviour=self)
                    return

                s_id = content.get("sensor_id")
                if s_id:
                    coords = content.get("coords")
                    meta = content.get("metadata", {})
                    detected = meta.get("detected_object") or meta.get("audio_type")

                    if detected and detected not in ["none","bison_roar","bison"]:
                        await self.agent.process_incident(s_id, detected, coords, behaviour=self)
                    else:
                        if s_id in self.agent.incident_memory:
                            print(f"[Analyzer] Sektor {s_id} bezpieczny. Czyszczę pamięć.")
                            del self.agent.incident_memory[s_id]

    async def setup(self):
        print(f"AnalyzerAgent {self.jid} (Centrum Decyzyjne) wystartował.")
        self.add_behaviour(self.ReceiveDataBehav())