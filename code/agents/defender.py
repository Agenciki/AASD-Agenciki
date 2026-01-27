import spade
import json
import asyncio
from spade.message import Message
from spade.behaviour import CyclicBehaviour  # Zmieniono z RespondRequest
from spade.template import Template
import random

class DefenderAgent(spade.agent.Agent):
    def __init__(self, jid, password, *args, **kwargs):
        super().__init__(jid, password, *args, **kwargs)
        
    #pomocnicze
    async def trigger_sensor_action(self, sensor_jid, action):
        if not sensor_jid:
            return False
        msg = Message(to=sensor_jid)
        msg.set_metadata("performative", "request")
        msg.body = json.dumps({"action": action})
        
        
        await self.container.send(msg, self)
        
        # Ntutaj coś nie tak
        return True

    async def activate_drones(self, coords, target_type, target_jid=None):
        print(f"[Defender] DRON: Start lotu do {coords} cel: {target_type}")
        await asyncio.sleep(2) 

        if target_jid:
            msg = Message(to=target_jid)
            msg.set_metadata("performative", "request")
            msg.body = json.dumps({"action": "scare"})
            await self.container.send(msg, self)
             
        # szans na to że dron wyleci
        success = random.random() > 0.1 
        if success:
            print(f"[Defender] DRON: Akcja zakończona sukcesem.")
        else:
            print(f"[Defender] DRON: Akcja zakończona porażką.")
        return success

   
    class HandlePreventionRequest(CyclicBehaviour):
        async def run(self):
            
            msg = await self.receive(timeout=10)
            if msg:
                try:
                    data = json.loads(msg.body)
                    danger_type = data.get("danger_type")
                    coords = data.get("coords")
                    sensor_jid = data.get("sensor_jid")
                    force_drone = data.get("force_drone", False)

                    print(f"\n[Defender] >>> NOWE ZADANIE: {danger_type} w kwadracie {coords}")
                    
                    success = False
                    critical_alarm = False

                    # dron albo sensor
                    if force_drone:
                        
                        success = await self.agent.activate_drones(coords, danger_type)
                        if not success:
                            print("[Defender] ! PORAŻKA DRONA ! ")
                            critical_alarm = True
                    else:
                        success = await self.agent.trigger_sensor_action(sensor_jid, "both")

                    
                    reply = msg.make_reply()
                    reply.set_metadata("performative", "inform")
                    reply.body = json.dumps({
                        "status": "success" if success else "failed",
                        "success": success, 
                        "critical_alarm": critical_alarm,
                        "danger_type": danger_type,
                        "coords": coords
                    })
                    await self.send(reply)

                except Exception as e:
                    print(f"[Defender] Błąd podczas przetwarzania: {e}")

    async def setup(self):
        print(f"DefenderAgent {self.jid} gotowy (obsługa dronów i prewencji).")
        

        template = Template()
        template.set_metadata("performative", "request")
        
        self.add_behaviour(self.HandlePreventionRequest(), template)