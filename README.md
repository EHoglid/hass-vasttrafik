# Västtrafik Journey Planner for Home Assistant

[![CI](https://github.com/EHoglid/hass-vasttrafik/actions/workflows/ci.yml/badge.svg)](https://github.com/EHoglid/hass-vasttrafik/actions/workflows/ci.yml)
[![HACS validation](https://github.com/EHoglid/hass-vasttrafik/actions/workflows/validate.yaml/badge.svg)](https://github.com/EHoglid/hass-vasttrafik/actions/workflows/validate.yaml)
[![GitHub Pages](https://github.com/EHoglid/hass-vasttrafik/actions/workflows/pages.yml/badge.svg)](https://github.com/EHoglid/hass-vasttrafik/actions/workflows/pages.yml)
[![GitHub release](https://img.shields.io/github/v/release/EHoglid/hass-vasttrafik?sort=semver)](https://github.com/EHoglid/hass-vasttrafik/releases)
[![GitHub issues](https://img.shields.io/github/issues/EHoglid/hass-vasttrafik)](https://github.com/EHoglid/hass-vasttrafik/issues)
[![Project page](https://img.shields.io/badge/Project_page-GitHub_Pages-006b76)](https://ehoglid.github.io/hass-vasttrafik/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/EHoglid/hass-vasttrafik/blob/master/LICENSE)

A custom Home Assistant integration that shows live bus, tram, train, and ferry
departures from selected Västtrafik stop areas. It uses Journey Planner API v4,
fetches the configured time window with pagination, and refreshes once per
minute.

The Västtrafik name and logo are trademarks of Västtrafik and are used only to
identify the service. They are not covered by this repository's MIT license.

## Install

### HACS custom repository

Until the integration is included in the default HACS catalogue, add it as a
custom repository:

1. Open **HACS** in Home Assistant.
2. Open **Integrations** and select the three-dot menu.
3. Choose **Custom repositories**.
4. Enter `EHoglid/hass-vasttrafik`.
5. Select **Integration** as the repository type and click **Add**.
6. Search for **Västtrafik Journey Planner**, download it, and restart Home Assistant.

### Manual installation

1. Copy `custom_components/vasttrafik_timetable` into the
   `custom_components` directory in your Home Assistant configuration.
2. Restart Home Assistant.
3. Open **Settings > Devices & services > Add integration** and search for
  **Västtrafik Journey Planner**.

## Configuration

1. Create an account at <https://developer.vasttrafik.se/>.
2. Create an application and subscribe it to **Planera Resa v4**.
3. Add **Västtrafik Journey Planner** in Home Assistant and enter the application's
  Client ID and Client Secret the first time.
4. Search for a stop, select a result, and configure its departure query.

When adding another stop, the integration reuses the credentials from the
existing Västtrafik entry. You only need to search for and select the new stop.

The stop configuration supports:

- Start date and time in RFC 3339 format
- Platform filtering with comma-separated platform names
- Time span from 0 to 1440 minutes, default 60
- Maximum departures per line and direction, default 2
- API page size, default 10
- Optional occupancy data
- Optional direction stop-area GID filtering

All API pages in the selected time window are fetched automatically.

## Entities

Each stop creates:

- **Next departure**: timestamp of the next departure. Its `departures`
  attribute contains all fetched departures with line, direction, platform,
  planned/estimated times, delay, cancellation state, transport mode, and
  line presentation data. Each departure includes `line` (the number),
  `line_name`, `line_background_color`, `line_foreground_color`, and
  `line_border_color` from the stop-area departures response.
- **Minutes until departure**: whole minutes until the next departure.

## Dashboard card

The integration includes a colored **Västtrafik departure board** Lovelace card. The
integration registers its JavaScript resource automatically. After restarting
Home Assistant, add it from **Edit dashboard > Add card**. Remove any manually
added Västtrafik card resource under **Settings > Dashboards > Resources**;
the integration registers its resource automatically.

Add a Manual card with:

```yaml
type: custom:vasttrafik-timetable-card
entity: sensor.lindholmspiren_goteborg_next_departure
title: Lindholmen
size: xs
lines: "10, 12, 19, 21, X1"
show_departure_after: true
page_seconds: 5
```

The card groups departures by line and destination, shows the closest two
departures as **Next** and **Then**, and displays line colors, transport icons,
platforms, and estimated times. It follows the Home Assistant language for its
labels.

Card settings:

- `size`: `xs`, `s`, `m`, `l`, or `xl`. These use approximately `0.75`, `1`,
  `1.25`, `1.5`, and `1.5` Home Assistant grid rows per departure respectively.
  Legacy values `small`, `medium`, and `large` remain supported as aliases for
  `s`, `m`, and `l`.
- `lines`: optional comma-separated line filter. It matches line numbers and
  names such as `10, 12, Buss 19`. Leave empty to show all lines.
- `show_departure_after`: `true` or `false`, default `true`. When false, the
  `Then/Därefter` column is hidden entirely.
- `page_seconds`: page rotation interval from 1 to 60 seconds, default 5.

The card automatically rotates through additional pages and shows the current
page, progress bar, and page indicators. The JavaScript card only requires a
browser refresh after changes; restart Home Assistant after changing Python
integration files.

## Markdown alternative

The following Markdown card is a text-only alternative. Replace the entity ID
with the one Home Assistant creates for your stop.

```yaml
type: markdown
content: |
  ## Departures
  {% set rows = state_attr('sensor.brunnsparken_next_departure', 'departures') or [] %}
  {% for row in rows[:8] %}
  **{{ row.line }}** toward {{ row.direction }} — {{ as_timestamp(row.estimated_time) | timestamp_custom('%H:%M') }}{% if row.platform %}, platform {{ row.platform }}{% endif %}
  {% else %}
  No upcoming departures.
  {% endfor %}
```

## Development

Create a local test environment with:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements_test.txt
```

On Windows PowerShell, activate it with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Run linting, tests, and the frontend syntax check with:

```bash
ruff check .
python -m pytest
node --check custom_components/vasttrafik_timetable/www/vasttrafik-timetable-card.js
```

On Windows, the pure API tests can be run with Home Assistant's optional test
plugin autoload disabled because Home Assistant currently imports the Unix-only
`fcntl` module:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -m pytest
Remove-Item Env:PYTEST_DISABLE_PLUGIN_AUTOLOAD
```

GitHub Actions runs the full Home Assistant test setup on Ubuntu.
