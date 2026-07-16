from src.risk.kill_switch import KillSwitch

switch = KillSwitch()

print(switch.is_active())

switch.activate()

print(switch.is_active())

switch.deactivate()

print(switch.is_active())