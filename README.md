# Tank Fill - Home Assistant Integration

A Home Assistant custom integration for monitoring oil levels in a horizontal cylindrical tank. Reads from an existing sensor that measures the distance from the top of the tank to the liquid surface, calculates volume using the circular segment formula, and tracks daily usage and cost.

## Sensors

The integration creates four sensors under a single **Oil Tank** device:

| Sensor              | Unit | Description                                        |
|---------------------|------|----------------------------------------------------|
| Oil Volume          | L    | Current volume of oil in the tank                  |
| Oil Fill Percentage | %    | How full the tank is                               |
| Oil Daily Usage     | L    | Cumulative oil consumed today (resets at midnight) |
| Oil Daily Cost      | GBP  | Daily usage multiplied by price per litre          |

Daily usage tracks consumption only — if the volume increases (e.g. a refill delivery), the increase is ignored and usage continues accumulating from the new level.

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

Tank dimensions are fixed after setup. To change the price per litre later, go to the integration's **Configure** option.

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
├── __init__.py       # Integration setup and teardown
├── manifest.json     # Integration metadata
├── const.py          # Shared constants
├── calc.py           # Volume calculation (no HA dependencies)
├── config_flow.py    # Setup and options flows
├── sensor.py         # Sensor entities
├── strings.json      # UI strings
└── translations/
    └── en.json       # English translations
```

The volume calculation lives in `calc.py` with no Home Assistant dependencies, making it straightforward to test independently.

### Submitting changes

1. Fork the repository
2. Create a feature branch
3. Ensure all tests pass
4. Open a pull request

## Licence

MIT
