"""Register definitions for the Delta ERV mock server.

Mirrors the constants in custom_components/delta_erv/const.py so the mock
server has no dependency on Home Assistant to run. If you add a new
register there, add it here too.
"""

# Control registers
REG_POWER = 0x05
REG_FAN_SPEED = 0x06

# Airflow percentage registers
REG_SUPPLY_AIR_1_PCT = 0x07
REG_EXHAUST_AIR_1_PCT = 0x0A

# Measured fan speeds (RPM)
REG_SUPPLY_FAN_SPEED = 0x0D
REG_EXHAUST_FAN_SPEED = 0x0E

# Bypass / circulation
REG_BYPASS_FUNCTION = 0x0F
REG_INTERNAL_CIRCULATION = 0x14

# Status
REG_ABNORMAL_STATUS = 0x10
REG_OUTDOOR_TEMP = 0x11
REG_INDOOR_RETURN_TEMP = 0x12
REG_SYSTEM_STATUS = 0x13

# Power values
POWER_OFF = 0x00
POWER_ON = 0x01

# Bypass values
BYPASS_HEAT_EXCHANGE = 0x00
BYPASS_BYPASS = 0x01
BYPASS_AUTO = 0x02

# Abnormal status bits
STATUS_EEPROM_ERROR = 0x08
STATUS_INDOOR_TEMP_ERROR = 0x10
STATUS_OUTDOOR_TEMP_ERROR = 0x20
STATUS_EXHAUST_FAN_ERROR = 0x40
STATUS_SUPPLY_FAN_ERROR = 0x80

# Observed fan RPM ranges
SUPPLY_MIN_RPM = 380
SUPPLY_MAX_RPM = 2300
EXHAUST_MIN_RPM = 400
EXHAUST_MAX_RPM = 1840
