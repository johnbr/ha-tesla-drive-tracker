"""Constants for the Tesla Drive Tracker integration."""
from __future__ import annotations

import logging

DOMAIN = "tesla_drive_tracker"
LOGGER = logging.getLogger(__package__)

CONF_VIN = "vin"
CONF_THRESHOLDS = "arrival_thresholds"
CONF_ROLES = "roles"
CONF_CAR_MODEL = "car_model"
CONF_CAR_COLOR = "car_color"
CONF_RECORD_DRIVES = "record_drives"
CONF_RECORD_DAYS = "record_days"

DEFAULT_RECORD_DAYS = 7
MAX_RECORD_DAYS = 90

URL_BASE = "/tesla_drive_tracker"
CARD_FILENAME = "tesla-drive-tracker-card.js"

STORAGE_VERSION = 1

# A parked car sends nothing, so the engine's delays need a clock of their own.
TICK_SECONDS = 15
SAVE_EVERY_SECONDS = 30
RESOLVE_COOLDOWN_SECONDS = 5
RECORD_FLUSH_SECONDS = 10
