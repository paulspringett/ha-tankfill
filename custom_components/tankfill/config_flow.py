"""Config flow for Tank Fill integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_DEPTH_SENSOR,
    CONF_PRICE_PER_LITRE,
    CONF_TANK_DIAMETER,
    CONF_TANK_LENGTH,
    DEFAULT_PRICE_PER_LITRE,
    DOMAIN,
)


class TankFillConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tank Fill."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial configuration step."""
        if user_input is not None:
            return self.async_create_entry(
                title="Oil Tank",
                data={
                    CONF_DEPTH_SENSOR: user_input[CONF_DEPTH_SENSOR],
                    CONF_TANK_DIAMETER: user_input[CONF_TANK_DIAMETER],
                    CONF_TANK_LENGTH: user_input[CONF_TANK_LENGTH],
                },
                options={
                    CONF_PRICE_PER_LITRE: user_input.get(
                        CONF_PRICE_PER_LITRE, DEFAULT_PRICE_PER_LITRE
                    ),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEPTH_SENSOR): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_TANK_DIAMETER): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=500,
                            step=1,
                            unit_of_measurement="cm",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(CONF_TANK_LENGTH): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=500,
                            step=1,
                            unit_of_measurement="cm",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_PRICE_PER_LITRE, default=DEFAULT_PRICE_PER_LITRE
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=10,
                            step=0.01,
                            unit_of_measurement="GBP/L",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TankFillOptionsFlow:
        """Get the options flow for this handler."""
        return TankFillOptionsFlow(config_entry)


class TankFillOptionsFlow(OptionsFlowWithConfigEntry):
    """Handle options flow for Tank Fill."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PRICE_PER_LITRE,
                        default=self.options.get(
                            CONF_PRICE_PER_LITRE, DEFAULT_PRICE_PER_LITRE
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=10,
                            step=0.01,
                            unit_of_measurement="GBP/L",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
