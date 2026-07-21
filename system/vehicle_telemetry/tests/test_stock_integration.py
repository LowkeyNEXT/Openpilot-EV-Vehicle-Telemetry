from cereal import car

from openpilot.common.params import Params
from openpilot.system.manager.process_config import managed_processes


def test_stock_manager_runs_ev_vehicle_telemetry_onroad_at_low_priority():
  process = managed_processes["vehicle_telemetryd"]
  params = Params()
  car_params = car.CarParams.new_message()
  assert process.nice == 19
  assert process.should_run(False, params, car_params)
  assert process.should_run(True, params, car_params)
