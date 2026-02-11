# Delta ERV (台達全熱交換機) Integration for Home Assistant

This is a custom component for Home Assistant that integrates Delta ERV (Energy Recovery Ventilation) devices via Modbus (serial or TCP). You need to connect a RS485 to Ethernet/Wi-Fi converter to the RS485 port of the Delta ERV system.

## Features

- Control ERV fan speed (Low/Medium/High)
- Turn ERV system on/off
- Monitor outdoor and indoor return temperatures
- Monitor supply and exhaust fan speeds
- Monitor system status and error conditions
- Support for both serial RS485 and TCP connections

## Supported Models

Based on the Delta ERV specification document, this integration supports:
- VEB250-N, VEB150, VEB250, VEB350 models (full feature support)
- VEB500, VEB800, VEB1000 models (limited register support)

**Note:** Some sensors may show as "unavailable" depending on your ERV model. This is normal as different models support different registers. The core fan control functionality (power and speed) is supported on all models.

## Installation

### Hardware
The delta ERV's stock control panel consists of an AC (220V) to DC (5V) transformer, and a screen module with built-in control board. Since we want to control the ERV ourselves, the control board is no longer needed. We can purchase any off-the-self RS485 to wifi converter which can be powered by 5V DC. For example, this [EP-W100 RS485 to Wifi converter](https://e.tb.cn/h.79rbgwYYMP1WPCZ?tk=7FMdUWSXanM) by 华允物联. Connect the pinout from the stock transformer's GND, 5VDC, RS485 A/B pins to the RS845 to wifi converter as shown in the image below.

<p align="center">
  <img src=".img/installation.jpg" width="300px" />
  <img src=".img/installation2.jpg" width="300px" />
</p>

I've also designed a 3D printable case which matches the original panel design, which can be used to hide the RS485 to wifi converter. You can download the design from this [Makerworld page](https://makerworld.com/en/models/2381915-delta-erv-control-panel-vfru-ervt-03ss-cover)

### Software

1. Copy the `custom_components/delta_erv` directory to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration through the Home Assistant UI (Configuration > Integrations > Add Integration).

## Configuration

The integration can be configured through the Home Assistant UI. You'll need to provide:

- **Name**: A friendly name for your ERV device
- **Connection Type**: Choose between Serial, TCP, or RTU over TCP
- **For Serial connections**:
  - Port: Serial port (e.g., `/dev/ttyUSB0`)
  - Slave ID: Modbus slave ID (1-247, default: 100/0x64)
  - Optional: Baud rate, data bits, parity, stop bits
- **For TCP connections**:
  - Host: IP address of the Modbus TCP gateway
  - Port: TCP port (default: 502)
  - Slave ID: Modbus slave ID (1-247, default: 100/0x64)

## Entities

### Fan Entity
- **ERV Fan**: Controls the main ERV fan with three speed levels
  - Low (風量 1)
  - Medium (風量 2) 
  - High (風量 3)

### Sensor Entities
- **Outdoor Temperature**: External air temperature
- **Indoor Return Temperature**: Return air temperature
- **Supply Fan Speed**: Supply fan RPM
- **Exhaust Fan Speed**: Exhaust fan RPM
- **Abnormal Status**: System error conditions
- **System Status**: Current system operating state

## Register Mapping

The integration uses the following Modbus registers based on the Delta ERV specification:

| Register | Name | Function |
|----------|------|----------|
| 0x05 | 開關機 | Power On/Off |
| 0x06 | 風量設定 | Fan Speed Setting |
| 0x10 | 異常狀態 | Abnormal Status |
| 0x11 | 外氣溫度 | Outdoor Temperature |
| 0x12 | 室內回風溫度 | Indoor Return Temperature |
| 0x0D | 送風機轉速 | Supply Fan Speed |
| 0x0E | 排風機轉速 | Exhaust Fan Speed |
| 0x13 | 系統狀態 | System Status |

## Hardware Setup

1. Connect your Delta ERV system to a RS485 to Ethernet/Wi-Fi converter
2. Configure the converter for the appropriate baud rate (default: 9600)
3. Set the ERV Modbus slave ID (default: 100)
4. Connect the converter to your network

## Troubleshooting

### Connection Issues
- Verify RS485 wiring (A/B or +/- connections)
- Check baud rate and communication parameters
- Ensure the slave ID matches between the ERV and configuration
- Test with a Modbus testing tool first

### Missing Entities
- Some registers may not be available on all ERV models
- Check the specification document for your specific model
- Enable debug logging to see communication details

### Debug Logging
Add this to your `configuration.yaml` to enable debug logging:

```yaml
logger:
  logs:
    custom_components.delta_erv: debug
```

## Development

This integration is based on the Delta ERV Modbus specification document and follows Home Assistant integration best practices.

## License

This project is licensed under the MIT License.
