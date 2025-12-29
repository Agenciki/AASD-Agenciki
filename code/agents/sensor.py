import spade
from spade.message import Message
from spade.behaviour import PeriodicBehaviour
from spade.behaviour import RespondRequest 
from spade.template import Template


import asyncio
import json
import random
import time
from spade.message import Message
import base64
import os

def generate_random_base64(length=32):
    random_bytes = os.urandom(length)
    return base64.b64encode(random_bytes).decode('utf-8')

#poprawić ponowne wysłanie alertu

class SensorAgent(spade.agent.Agent):
    def __init__(self, jid, password, analyzer_jid,coords, *args, **kwargs):
        super().__init__(jid, password, *args, **kwargs)
        self.analyzer_jid = analyzer_jid
        self.coords=coords

    class SendSensorDataBehav(spade.behaviour.PeriodicBehaviour):
        async def run(self):
            sensor_type = random.choice(["camera", "microphone"])
            
            payload = {
                "sensor_id": str(self.agent.jid),
                "coords": self.agent.coords,
                "type": sensor_type,
                "timestamp": time.time(),
                "metadata": {},
                "data": generate_random_base64()
            }

            
            if sensor_type == "camera":
                # pole dla kamery
                payload["metadata"] = {
                    "image_mode": random.choice(["standard", "thermal"]), # obraz zwykły lub cieplny 
                    "detected_object": random.choices(
                        ["zubr", "human", "wolf","none"], 
                        weights=[0.57, 0.3,0.1,0.03] #  tweoretycznie można w analyzer przenieść
                    )[0]
                }
            
            elif sensor_type == "microphone":
                
                payload["metadata"] = {
                    "audio_type": random.choices(
                        ["shot", "engine", "bison_roar","wolf_roar", "human","none"], 
                        weights=[0.05, 0.1, 0.55, 0.1,0.17,0.03]
                    )[0]
                }

            
            msg = Message(to=self.agent.analyzer_jid)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("protocol", "fipa-query")
            msg.body = json.dumps(payload)
            
            await self.send(msg)
            print(f"[Sensor] Symulacja: {sensor_type} wykrył {payload['metadata']}")

    class HandleDefenseRequest(RespondRequest):
        async def handle(self, request):
            try:
                instruction = json.loads(request.body)
                action = instruction.get("action")

                
                print(f"[Sensor] >>> OTRZYMANO ZADANIE: {action}")
                
                await asyncio.sleep(1) 

                print(f"[Sensor] <<< WYKONANO ZADANIE: {action} (Aktywowano urządzenia)")

                response = request.make_reply()
                response.set_metadata("performative", "inform")
                response.body = json.dumps({"status": "success", "action": action})
                
                await self.send(response)
                print(f"[Sensor] Potwierdzenie sukcesu wysłane do Defendera.")

            except Exception as e:
                print(f"[Sensor] Błąd podczas wykonywania zadania: {e}")
                reply = request.make_reply()
                reply.set_metadata("performative", "failure")
                await self.send(reply)

    async def setup(self):
        print(f"SensorAgent {self.jid} wystartował.")

        self.add_behaviour(self.SendSensorDataBehav(period=5))
        
        template = Template()
        template.set_metadata("performative", "request")
        self.add_behaviour(self.HandleDefenseRequest(), template)