# Tank Fill - Home Assistant Integration

A Home Assistant custom integration for monitoring oil levels in a horizontal cylindrical tank. Reads from an existing sensor that measures the distance from the top of the tank to the liquid surface, calculates volume using the circular segment formula, and tracks usage and cost over rolling windows.

## Sensors

The integration creates the following sensors under a single **Oil Tank** device:

| Sensor              | Unit | Description                                                  |
|---------------------|------|--------------------------------------------------------------|
| Oil Depth           | cm   | Depth of oil in the tank                                     |
| Oil Volume          | L    | Current volume of oil in the tank                            |
| Oil Fill Percentage | %    | How full the tank is                                         |
| Avg. Daily Usage    | L    | Average daily oil consumption (weekly usage / 7)             |
| Weekly Usage        | L    | Oil consumed in the last 7 days                              |
| Monthly Usage       | L    | Oil consumed in the last 30 days                             |
| Yearly Usage        | L    | Oil consumed in the last 365 days                            |
| Avg. Daily Cost     | GBP  | Average daily cost (avg daily usage × price per litre)       |
| Weekly Cost         | GBP  | Cost of oil consumed in the last 7 days                      |
| Monthly Cost        | GBP  | Cost of oil consumed in the last 30 days                     |
| Yearly Cost         | GBP  | Cost of oil consumed in the last 365 days                    |
| Last Refill         | —    | Timestamp of the most recent refill detection                |

Usage and cost sensors use **rolling windows** — they always reflect consumption over the last 7/30/365 days rather than resetting at fixed intervals.

Refills are automatically detected when the tank volume increases significantly. The **Last Refill** sensor records the timestamp and includes the volume before, volume after, and litres added as state attributes.

## Prerequisites

You need an existing Home Assistant sensor entity that reports the **distance from the top of the tank to the liquid surface** in centimetres. This is typically an ultrasonic distance sensor mounted inside the top of the tank pointing downward.

- When the tank is full, the sensor reads a small value (close to 0)
- When the tank is empty, the sensor reads close to the tank diameter
- The sensor entity must be in the `sensor` domain

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots menu in the top right and select **Custom repositories**
3. Add `https://github.com/paulspringett/ha-tankfill` with category **Integration**
4. Click **Add**
5. Search for "Tank Fill" in HACS and click **Download**
6. Restart Home Assistant

### Manual

1. Copy the `custom_components/tankfill/` directory into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **Tank Fill**
3. Enter:
   - **Depth sensor** — select your distance sensor entity
   - **Tank diameter** — internal diameter of the tank in cm
   - **Tank length** — internal length of the tank in cm
   - **Price per litre** — cost of heating oil in GBP (default: £0.55)
   - **Price sensor** *(optional)* — a sensor entity that provides a live price per litre

Tank dimensions are fixed after setup. To change the price per litre or price sensor later, go to the integration's **Configure** option.

### Price sensor

If a price sensor is configured, its value is captured **on each refill event** and used for all subsequent cost calculations. This lets you track costs at the price you actually paid. The captured price persists across restarts.

When no price sensor is configured (or the sensor is unavailable at refill time), the manual **price per litre** value is used as the fallback.

## Contributing

### Setup

```bash
git clone https://github.com/paulspringett/ha-tankfill.git
cd ha-tankfill
```

### Running tests

```bash
uv run --with pytest pytest tests/ -v
```

### Project structure

```
custom_components/tankfill/
├── __init__.py        # Integration setup and teardown
├── manifest.json      # Integration metadata
├── const.py           # Shared constants
├── calc.py            # Volume calculation (no HA dependencies)
├── config_flow.py     # Setup and options flows
├── sensor.py          # Sensor entities
├── usage_history.py   # Rolling-window usage tracking and refill detection
├── strings.json       # UI strings
└── translations/
    └── en.json        # English translations
```

The volume calculation (`calc.py`) and usage history (`usage_history.py`) have no Home Assistant dependencies, making them straightforward to test independently.

### Submitting changes

1. Fork the repository
2. Create a feature branch
3. Ensure all tests pass
4. Open a pull request

## Licence

MIT
