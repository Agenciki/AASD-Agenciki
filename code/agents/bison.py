import spade
import time
import random
import json
import asyncio
from spade.message import Message
from . import  config



# rezerwat granicy
RESERVE_CONFIG =config.RESERVE_CONFIG


class BisonAgent(spade.agent.Agent):
    def __init__(self, jid: str, password: str, name="Zubr", observers= None,forced_coords=None,ignore_drones=False, *args, **kwargs):
        super().__init__(jid, password, *args, **kwargs)
        self.bison_name = name
        self.observers= observers if observers is not None else []
        self.forced_coords = forced_coords # wymuszona pozycja dla testów
        self.ignore_drones = ignore_drones  # test zawsze ignoruj dron
    
    class DataSenderBehav(spade.behaviour.PeriodicBehaviour):
        async def on_start(self):
            print(f"[{self.agent.bison_name}] Zaczynam cykliczne przesyłanie danych.")

        async def run(self):
            if self.agent.forced_coords:
                x_pos, y_pos = self.agent.forced_coords    
            else:
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
    
    
    
    class ListenForIntervention(spade.behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg:
                content = json.loads(msg.body)
                action = content.get("action")
                
                if action in ["scare", "worker_intervention"]:
                    is_worker = action == "worker_intervention"
                    
                    # Logika logika dla drona
                    if not is_worker:
                        success_chance = 0.7 
                        if self.agent.ignore_drones:
                            success_chance = 0.0 # Wymuszony upór dla testów
                            print(f"[{self.agent.bison_name}] TRYB TESTOWY: Ignoruję drona.")

                        if random.random() > success_chance:
                            print(f"[{self.agent.bison_name}] Wywalone mam w drona (losowanie niepomyślne).")
                            return
                    
                    
                    self.agent.forced_coords = None 
                    new_x = round(random.uniform(RESERVE_CONFIG["X_MIN"], RESERVE_CONFIG["X_MAX"]), 2)
                    new_y = round(random.uniform(RESERVE_CONFIG["Y_MIN"], RESERVE_CONFIG["Y_MAX"]), 2)
                    self.agent.current_coords = [new_x, new_y]
                    print(f"[{self.agent.bison_name}] !!! {'Pracownik' if is_worker else 'Dron'} mnie przegonił! Wracam.{new_x,new_y} !!!")
                   


            
    async def setup(self):
        print(f"BisonAgent {self.bison_name} wystartował.")
        
        self.add_behaviour(self.DataSenderBehav(period=5))
        self.add_behaviour(self.ListenForIntervention()) #dla testów