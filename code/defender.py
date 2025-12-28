import spade
import json
import asyncio
from spade.message import Message
from spade.behaviour import RespondRequest
from spade.template import Template
import random

class DefenderAgent(spade.agent.Agent):
    def __init__(self, jid, password, *args, **kwargs):
        super().__init__(jid, password, *args, **kwargs)
        

    class HandlePreventionRequest(RespondRequest):
        async def handle(self, request):
            try:
                data = json.loads(request.body)
                danger_type = data.get("danger_type") # "wolf", "human", "shot","bison_escape" jak opisałem w sensorze
                coords = data.get("coords")
                sensor_jid = data.get("sensor_jid")

                print(f"\n[Defender] >>> NOWE ZADANIE: {danger_type} w kwadracie {coords}")
                force_drone = data.get("force_drone", False)
                success = False
                critical_alarm =False

                # REAKCJA
                if force_drone:
                    success = await self.activate_drones(coords)
                    # jeśli nie udało się wołaj o pomóc
                    if not success:
                        print("[Defender] ! PORAŻKA DRONA ! ")
                        critical_alarm = True
                else:
                    #albo wysyłam do sensora
                    success = await self.trigger_sensor_action(sensor_jid, "both")

                # Odpowiedź do Analyzera
                reply = request.make_reply()
                reply.set_metadata("performative", "inform")
                reply.body = json.dumps({
                            "status": "success" if success else "failed",
                            "success": success, 
                            "critical_alarm": critical_alarm, # tutaj woła o pomoc
                            "danger_type": danger_type,
                            "coords": coords
                        })
                await self.send(reply)

            except Exception as e:
                print(f"[Defender] Błąd: {e}")

        async def trigger_sensor_action(self, sensor_jid, action):
            if not sensor_jid: return False
            msg = Message(to=sensor_jid)
            msg.set_metadata("performative", "request")
            msg.body = json.dumps({"action": action})
            await self.send(msg)
            
            
            reply = await self.receive(timeout=5)
            return reply and reply.get_metadata("performative") == "inform"

        async def activate_drones(self, coords, target):

            print(f"[Defender] DRON: Start lotu do {coords} cel: {target}")
            await asyncio.sleep(2) 
             
            success = random.random() > 0.1 
            if success:
                print(f"[Defender] DRON: Akcja zakończona sukcesem.")
            else:
                print(f"[Defender] DRON: Akcja zakończona porażką.")
            return success
            

        

    async def setup(self):
        print(f"DefenderAgent {self.jid} gotowy (z logiką drona i geofencingu).")
        template = Template()
        template.set_metadata("performative", "request")
        self.add_behaviour(self.HandlePreventionRequest(), template)