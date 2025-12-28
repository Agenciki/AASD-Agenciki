import spade
import time
import random
import json
import asyncio
from spade.message import Message
import  config

WORKER_JID = "worker@localhost"

# Konfiguracja granic rezerwatu
RESERVE_CONFIG =config.RESERVE_CONFIG


class BisonAgent(spade.agent.Agent):
    def __init__(self, jid: str, password: str, name="Zubr", observers= None, *args, **kwargs):
        super().__init__(jid, password, *args, **kwargs)
        self.bison_name = name
        self.observers= observers if observers is not None else []
    
    class DataSenderBehav(spade.behaviour.PeriodicBehaviour):
        async def on_start(self):
            print(f"[{self.agent.bison_name}] Zaczynam cykliczne przesyłanie danych.")

        async def run(self):


            x_pos = round(random.uniform(
                RESERVE_CONFIG["X_MIN"] - RESERVE_CONFIG["ESCAPE_MARGIN"], 
                RESERVE_CONFIG["X_MAX"] + RESERVE_CONFIG["ESCAPE_MARGIN"]
            ), 2)
            
            y_pos = round(random.uniform(
                RESERVE_CONFIG["Y_MIN"] - RESERVE_CONFIG["ESCAPE_MARGIN"], 
                RESERVE_CONFIG["Y_MAX"] + RESERVE_CONFIG["ESCAPE_MARGIN"]
            ), 2)
            
            health_options = ["spokojny", "agresywny", "chory"]
            health_weights = [0.7, 0.2, 0.1]
            drawn_health = random.choices(health_options, weights=health_weights, k=1)[0]
            payload = {
                "name": self.agent.bison_name,
                "coords": {"x": x_pos, "y": y_pos},
                "health": drawn_health,
                "timestamp": time.time(),     
                "sender": str(self.agent.jid) 
            }
            
           
            for receiver_jid in self.agent.observers:
                msg = Message(to=receiver_jid) # konkretny z listy 
                msg.set_metadata("performative", "inform")
                msg.set_metadata("protocol", "fipa-query")
                msg.body = json.dumps(payload)

                try:
                    await self.send(msg)
                except Exception as e:
                    print(f"Błąd wysyłki do {receiver_jid}: {e}")

                print(f"[{self.agent.bison_name}] Dane rozesłane do {len(self.agent.observers)} odbiorców.")
            
            
    async def setup(self):
        print(f"BisonAgent {self.bison_name} wystartował.")
        
        self.add_behaviour(self.DataSenderBehav(period=5))