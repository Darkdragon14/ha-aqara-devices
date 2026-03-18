from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries


class OptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, **user_input},
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="Aqara Devices", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "username",
                        default=self.config_entry.options.get(
                            "username",
                            self.config_entry.data.get("username", ""),
                        ),
                    ): str,
                    vol.Required(
                        "password",
                        default=self.config_entry.options.get(
                            "password",
                            self.config_entry.data.get("password", ""),
                        ),
                    ): str,
                    vol.Required(
                        "area",
                        default=self.config_entry.options.get(
                            "area",
                            self.config_entry.data.get("area", "EU"),
                        ),
                    ): vol.In(["EU", "US", "CN", "RU", "OTHER"]),
                }
            ),
        )
