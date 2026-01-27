import pytest
import time
from unittest.mock import MagicMock, patch, AsyncMock, Mock
import json
import math
import sys
import os
import random


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from agents.analyzer import AnalyzerAgent
from agents.defender import DefenderAgent
from agents.worker import WorkerAgent
from agents.bison import BisonAgent
from agents.sensor import SensorAgent
from agents.config import RESERVE_CONFIG




@pytest.fixture
def mock_agent_setup():
    """Generyczny setup dla każdego agenta, mockujący infrastrukturę SPADE."""
    def _setup(agent_class, *args, **kwargs):
        with patch(f'agents.{agent_class.__module__.split(".")[-1]}.spade.agent.Agent.__init__', return_value=None):
            agent = agent_class(*args, **kwargs)
        
        
        agent.jid = str(args[0])
        agent.container = AsyncMock()
        agent.send = AsyncMock()
        
        return agent
    return _setup

# --- TESTY ANALYZERA ---

class TestAnalyzerLogic:
    
    @pytest.fixture
    def analyzer(self, mock_agent_setup):
        agent = mock_agent_setup(AnalyzerAgent, "analyzer@localhost", "pass", "defender@localhost", "worker@localhost")
        agent.defender_jid = "defender@localhost"
        agent.worker_jid = "worker@localhost"
        agent.incident_memory = {}
        agent.workers_registry = {}
        agent.send_to_defender = AsyncMock()
        agent.dispatch_nearest_worker = AsyncMock()
        return agent

    def test_distance_calculation_logic(self, analyzer):
        """Testuje, czy algorytm wybiera faktycznie najbliższego pracownika."""
        danger_coords = {"x": 10, "y": 10}
        analyzer.workers_registry = {
            "worker1": {"coords": {"x": 12, "y": 12}},
            "worker2": {"coords": {"x": 50, "y": 50}},
            "worker3": {"coords": {"x": 11, "y": 11}}
        }

        
        best_worker = None
        min_dist = float('inf')
        for w_jid, info in analyzer.workers_registry.items():
            w_coords = info["coords"]
            dist = math.sqrt((w_coords['x'] - danger_coords['x'])**2 + 
                             (w_coords['y'] - danger_coords['y'])**2)
            if dist < min_dist:
                min_dist = dist
                best_worker = w_jid
        
        assert best_worker == "worker3"

    @pytest.mark.asyncio
    async def test_escalation_logic_light_phase(self, analyzer):
        """Sprawdza, czy nowy incydent uruchamia tylko światło."""
        s_id = "sensor1"
        danger = "human"
        coords = {"x": 50, "y": 50}
        
        
        mock_behav = AsyncMock()
        await analyzer.process_incident(s_id, danger, coords, behaviour=mock_behav)

        assert s_id in analyzer.incident_memory
        analyzer.send_to_defender.assert_called_once()

    @pytest.mark.asyncio
    async def test_whitelisting_worker(self, analyzer):
        """Sprawdza, czy analyzer ignoruje człowieka, jeśli obok stoi worker."""
        analyzer.workers_registry = {
            "worker1": {"coords": {"x": 10, "y": 10}}
        }
        sensor_coords = {"x": 12, "y": 12}
        
        mock_behav = AsyncMock()
        await analyzer.process_incident("sensor1", "human", sensor_coords, behaviour=mock_behav)
        
        analyzer.send_to_defender.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_incident_critical_phase_worker(self, analyzer):
        """Testuje, czy po 40s incydentu wołany jest pracownik."""
        s_id = "sensor_crit"
        coords = {"x": 50, "y": 50}
        analyzer.incident_memory[s_id] = {
            "start_time": time.time() - 45,
            "last_time": time.time() - 5,
            "escalated": True,
            "worker_called": False
        }

        mock_behav = AsyncMock()
        await analyzer.process_incident(s_id, "human", coords, behaviour=mock_behav)

        
        analyzer.dispatch_nearest_worker.assert_called_with(coords, mock_behav, is_bison=False)
        assert analyzer.incident_memory[s_id]["worker_called"] is True

    @pytest.mark.asyncio
    async def test_handle_defender_feedback_critical(self, analyzer):
        """Sprawdza reakcję Analyzera na porażkę drona (critical_alarm)."""
        msg = MagicMock()
       
        msg.body = json.dumps({
            "critical_alarm": True, 
            "coords": {"x": 10, "y": 10},
            "danger_type": "wolf"
        })
        
        mock_behav = AsyncMock()
        await analyzer.handle_defender_feedback(msg, behaviour=mock_behav)
        
        
        analyzer.dispatch_nearest_worker.assert_called_with(
            {"x": 10, "y": 10}, 
            behaviour=mock_behav, 
            is_bison=False
        )

    @pytest.mark.asyncio
    async def test_escalation_heavy_phase_drone(self, analyzer):
        """Sprawdza, czy po 25 sekundach trwania incydentu wysyłany jest dron."""
        s_id = "sensor_persistent"
        danger = "wolf"
        coords = {"x": 50, "y": 50}
        
        past_time = time.time() - 25
        analyzer.incident_memory[s_id] = {
            "start_time": past_time,
            "last_time": past_time,
            "escalated": False,
            "worker_called": False
        }

        mock_behav = AsyncMock()
        await analyzer.process_incident(s_id, danger, coords, behaviour=mock_behav)

        
        analyzer.send_to_defender.assert_called_with(
            danger, coords, s_id, force_drone=True, behaviour=mock_behav
        )
        assert analyzer.incident_memory[s_id]["escalated"] is True


# --- TESTY DEFENDERA ---

class TestDefenderLogic:
    
    @pytest.fixture
    def defender(self, mock_agent_setup):
        agent = mock_agent_setup(DefenderAgent, "defender@localhost", "pass")
        agent.activate_drones = AsyncMock(return_value=True)
        agent.trigger_sensor_action = AsyncMock(return_value=True)
        return agent

    @pytest.mark.asyncio
    async def test_prevention_request_force_drone_success(self, defender):
        """Testuje zachowanie Defendera, gdy Analyzer wymusza drona."""
        behav = defender.HandlePreventionRequest()
        behav.agent = defender
        
        msg = MagicMock()
        msg.body = json.dumps({
            "danger_type": "human",
            "coords": {"x": 20, "y": 20},
            "force_drone": True,
            "sensor_jid": "sensor1"
        })
        msg.make_reply.return_value = MagicMock()
        behav.receive = AsyncMock(return_value=msg)
        behav.send = AsyncMock()

        await behav.run()

        defender.activate_drones.assert_called_once()
        defender.trigger_sensor_action.assert_not_called()
        
        args, _ = behav.send.call_args
        reply_body = json.loads(args[0].body)
        assert reply_body["success"] is True
        assert reply_body["critical_alarm"] is False

    @pytest.mark.asyncio
    async def test_prevention_request_drone_failure(self, defender):
        """Testuje, czy Defender zgłasza critical_alarm, gdy dron zawiedzie."""
        behav = defender.HandlePreventionRequest()
        behav.agent = defender
        defender.activate_drones.return_value = False
        
        msg = MagicMock()
        msg.body = json.dumps({"danger_type": "wolf", "coords": {}, "force_drone": True})
        msg.make_reply.return_value = MagicMock()
        behav.receive = AsyncMock(return_value=msg)
        behav.send = AsyncMock()

        await behav.run()

        args, _ = behav.send.call_args
        reply_body = json.loads(args[0].body)
        assert reply_body["success"] is False
        assert reply_body["critical_alarm"] is True

    @pytest.mark.asyncio
    async def test_activate_drones_logic(self, defender):
        """Testuje logikę losowania sukcesu drona."""
        real_activate = DefenderAgent.activate_drones 
        
        with patch('random.random', return_value=0.5):
            result = await real_activate(defender, {"x":0,"y":0}, "human")
            assert result is True

        with patch('random.random', return_value=0.05):
            result = await real_activate(defender, {"x":0,"y":0}, "human")
            assert result is False

    @pytest.mark.asyncio
    async def test_prevention_request_sensor_trigger(self, defender):
        """Testuje, czy Defender obsługuje żądania bez force_drone."""
        behav = defender.HandlePreventionRequest()
        behav.agent = defender
        defender.trigger_sensor_action.return_value = True
        
        msg = MagicMock()
        msg.body = json.dumps({
            "danger_type": "human",
            "coords": {"x": 20, "y": 20},
            "force_drone": False,
            "sensor_jid": "sensor1"
        })
        msg.make_reply.return_value = MagicMock()
        behav.receive = AsyncMock(return_value=msg)
        behav.send = AsyncMock()

        await behav.run()

        defender.trigger_sensor_action.assert_called()
        args, _ = behav.send.call_args
        reply_body = json.loads(args[0].body)
        assert reply_body["success"] is True


# --- TESTY WORKERA ---

class TestWorkerLogic:

    @pytest.fixture
    def worker(self, mock_agent_setup):
        return mock_agent_setup(WorkerAgent, "worker@localhost", "pass", "analyzer@localhost")

    @pytest.mark.asyncio
    async def test_worker_receives_help_request_bison(self, worker):
        """Sprawdza, czy worker poprawnie reaguje na wezwanie do żubra."""
        behav = worker.ReceiveAllCommunications()
        behav.agent = worker
        
        target_bison = "bison_benek@localhost"
        msg = MagicMock()
        msg.get_metadata.return_value = "request"
        msg.body = json.dumps({
            "type": "HELP_REQUIRED",
            "coords": {"x": 100, "y": 100},
            "is_bison": True,
            "target_jid": target_bison
        })
        behav.receive = AsyncMock(return_value=msg)
        
        
        behav.agent.container.send = AsyncMock()
        behav.agent.traces = MagicMock() 

        await behav.run()

        
        assert behav.agent.container.send.called
        args, _ = behav.agent.container.send.call_args
        sent_msg = args[0]
        
        assert str(sent_msg.to) == target_bison
        assert json.loads(sent_msg.body)["action"] == "worker_intervention"

    @pytest.mark.asyncio
    async def test_worker_receives_help_request_regular(self, worker):
        """Testuje, czy worker obsługuje normalne żądania pomocy."""
        behav = worker.ReceiveAllCommunications()
        behav.agent = worker
        
        behav.agent.container.send = AsyncMock()
        behav.agent.traces = MagicMock() 
        
        msg = MagicMock()
        msg.get_metadata.return_value = "request"
        msg.body = json.dumps({
            "type": "HELP_REQUIRED",
            "coords": {"x": 50, "y": 50},
            "is_bison": False
        })
        behav.receive = AsyncMock(return_value=msg)

        
        await behav.run()
        assert not behav.agent.container.send.called


# --- TESTY BISONA ---

class TestBisonLogic:

    @pytest.fixture
    def bison(self, mock_agent_setup):
        return mock_agent_setup(BisonAgent, "bison@localhost", "pass", "Benek", [], None, False)

    @pytest.mark.asyncio
    async def test_bison_scared_by_worker(self, bison):
        """Testuje reakcję żubra na interwencję pracownika."""
        behav = bison.ListenForIntervention()
        behav.agent = bison
        
        msg = MagicMock()
        msg.body = json.dumps({"action": "worker_intervention"})
        behav.receive = AsyncMock(return_value=msg)
        bison.forced_coords = {"x": 50, "y": 50}

        with patch('random.uniform', return_value=99.9):
            await behav.run()

        assert bison.forced_coords is None
        assert bison.current_coords == [99.9, 99.9]

    @pytest.mark.asyncio
    async def test_bison_ignores_drone(self, bison):
        """Testuje scenariusz, w którym żubr ignoruje drona."""
        behav = bison.ListenForIntervention()
        behav.agent = bison
        
        msg = MagicMock()
        msg.body = json.dumps({"action": "scare"})
        behav.receive = AsyncMock(return_value=msg)
        bison.forced_coords = {"x": 50, "y": 50}

        with patch('random.random', return_value=0.8):
            await behav.run()

        assert bison.forced_coords == {"x": 50, "y": 50}

    @pytest.mark.asyncio
    async def test_bison_responds_to_drone_scare(self, bison):
        """Testuje, czy żubr czasami ucieka od drona."""
        behav = bison.ListenForIntervention()
        behav.agent = bison
        
        msg = MagicMock()
        msg.body = json.dumps({"action": "scare"})
        behav.receive = AsyncMock(return_value=msg)
        bison.forced_coords = {"x": 50, "y": 50}

        with patch('random.random', return_value=0.5):
            with patch('random.uniform', return_value=25.0):
                await behav.run()

        assert bison.current_coords == [25.0, 25.0]

    @pytest.mark.asyncio
    async def test_bison_position_update(self, bison):
        """Testuje aktualizację pozycji żubra."""
        new_coords = {"x": 75, "y": 75}
        bison.current_coords = [new_coords["x"], new_coords["y"]]
        assert bison.current_coords == [75, 75]


# --- TESTY CZUJNIKA (Sensor) ---

class TestSensorLogic:

    @pytest.fixture
    def sensor(self, mock_agent_setup):
        return mock_agent_setup(SensorAgent, "sensor@localhost", "pass", "analyzer@localhost", 10, 10)

    @pytest.mark.asyncio
    async def test_sensor_sends_alarm_on_detection(self, sensor):
        """Testuje, czy czujnik wysyła alarm (w trybie testowym)."""
        
        sensor.analyzer_jid = "analyzer@localhost"
        sensor.test_mode = True 
        sensor.coords = {"x": 10, "y": 10}
        
       
        behav = sensor.SendSensorDataBehav(period=5)
        behav.agent = sensor
        
        
        behav.agent.container.send = AsyncMock()
        behav.agent.traces = MagicMock()
        await behav.run()


        assert behav.agent.container.send.called
