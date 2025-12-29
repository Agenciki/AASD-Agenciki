import spade
import json
import asyncio
import time
from spade.message import Message
import random
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour

class WorkerAgent(spade.agent.Agent):
    def __init__(self, jid, password, analyzer_jid, *args, **kwargs):
        super().__init__(jid, password, *args, **kwargs)
        self.analyzer_jid = analyzer_jid 

    class SendLocationBehav(PeriodicBehaviour):
        async def run(self):
            payload = {
                "worker_name": str(self.agent.jid),
                 "coords": {
                    "x": round(random.uniform(0, 100), 2),
                    "y": round(random.uniform(0, 100), 2)
                }, 
                "timestamp": time.time()
            }
            msg = Message(to=self.agent.analyzer_jid)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("protocol", "fipa-query") 
            msg.body = json.dumps(payload)
            await self.send(msg)
            print(f"[Worker] Wysłałem swoją lokalizację do Analyzera.")

    
    class ReceiveAllCommunications(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                content = json.loads(msg.body)
                perf = msg.get_metadata("performative")
                
                if "health" in content:
                    print(f"[Worker] Dane o żubrze: {content['name']} jest {content['health']}.")
                
                #  Analyzera 
                elif perf == "inform":
                    report_type = content.get("report_type")
                    data = content.get("data")
                    print(f"\n[Worker] RAPORT SYSTEMOWY: {report_type}")
                    print(f" -> Szczegóły: {data}")

                # Pomocy
                elif perf == "request":
                    if content.get("type") == "HELP_REQUIRED":
                        coords = content.get("coords")
                        is_bison = content.get("is_bison", False) # Pobieramy Twoją nową flagę
                        target_jid = content.get("target_jid")
                        
                        if is_bison and target_jid:
                            print(f"\n[Worker] !!! INTERWENCJA: Żubr {target_jid} na {coords}. Idę go przegonić! !!!")
                            
                            # Tworzymy wiadomość skierowaną bezpośrednio do żubra
                            msg_to_bison = Message(to=target_jid) # Adres żubra
                            msg_to_bison.set_metadata("performative", "request")
                            # Wysyłamy akcję, którą żubr już potrafi rozpoznać
                            msg_to_bison.body = json.dumps({"action": "worker_intervention"})
                            
                            await self.send(msg_to_bison)
                            print(f"[Worker] Posłałem sygnał odstraszający do żubra.")
                        else:
                            print(f"\n[Worker] !!! ALARM: Intruz na {coords}. Ruszam na miejsce! !!!")
                                
    async def setup(self):
        print(f"WorkerAgent {self.jid} gotowy do pracy.")
         
        self.add_behaviour(self.SendLocationBehav(period=10)) 
        self.add_behaviour(self.ReceiveAllCommunications())