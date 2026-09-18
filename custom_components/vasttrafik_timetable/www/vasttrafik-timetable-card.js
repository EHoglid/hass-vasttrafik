window.__vasttrafikTimetableCardLoaded = true;

class VasttrafikTimetableCard extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: "open" });
        this._pageStartedAt = Date.now();
        this._timer = null;
        this._availableHeight = 0;
        this._chromeHeight = 0;
        this._resizeObserver = this._createResizeObserver();
        this._resizeObserver?.observe(this);
        this._observedCard = null;
    }

    _createResizeObserver() {
        if (!("ResizeObserver" in window)) {
            return null;
        }

        return new ResizeObserver((entries) => {
            const height = Math.round(Math.max(
                ...entries.map((entry) => entry.contentRect.height),
                0,
            ));
            if (height && height !== this._availableHeight) {
                this._availableHeight = height;
                this._render();
            }
        });
    }

    static getConfigElement() {
        return document.createElement("vasttrafik-timetable-card-editor");
    }

    static getStubConfig() {
        return {};
    }

    setConfig(config) {
        this._config = config;
        this._pageStartedAt = Date.now();
    }

    connectedCallback() {
        this._resizeObserver?.observe(this);
        this._ensureTimer();
    }

    set hass(hass) {
        this._hass = hass;
        this._ensureTimer();
        this._render();
    }

    disconnectedCallback() {
        if (this._timer) {
            clearInterval(this._timer);
            this._timer = null;
        }
        this._resizeObserver?.disconnect();
    }

    getCardSize() {
        return 6;
    }

    getGridOptions() {
        return {
            rows: 6,
            columns: 12,
            min_rows: 3,
            min_columns: 6,
        };
    }

    _entityId() {
        if (this._config?.entity) {
            return this._config.entity;
        }

        return Object.keys(this._hass.states).find((entityId) =>
            entityId.startsWith("sensor.") &&
            Array.isArray(this._hass.states[entityId].attributes.departures),
        );
    }

    _minutes(estimatedTime) {
        return Math.max(0, Math.floor((Date.parse(estimatedTime) - Date.now()) / 60000));
    }

    _formatTime(estimatedTime) {
        return new Intl.DateTimeFormat(this._language(), {
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
        }).format(new Date(estimatedTime));
    }

    _language() {
        return this._hass.locale?.language || this._hass.language || "en";
    }

    _text(key) {
        const swedish = this._language().toLowerCase().startsWith("sv");
        const labels = {
            next: swedish ? "Nästa (min)" : "Next (min)",
            then: swedish ? "Därefter" : "Then",
            platform: swedish ? "Läge" : "Platform",
            now: swedish ? "Nu" : "Now",
            cancelled: swedish ? "Inställd" : "Cancelled",
            minutes: swedish ? "min" : "min",
            page: swedish ? "Sida" : "Page",
            noDepartures: swedish ? "Inga kommande avgångar." : "No upcoming departures.",
            wheelchair: swedish ? "Visa rullstolsikon" : "Show wheelchair icon",
        };
        return labels[key];
    }

    _ensureTimer() {
        if (!this._timer) {
            this._timer = setInterval(() => this._render(), 1000);
        }
    }

    _groupDepartures(departures) {
        const groups = new Map();
        for (const departure of departures) {
            const key = `${departure.line}|${departure.direction}`;
            if (!groups.has(key)) {
                groups.set(key, []);
            }
            groups.get(key).push(departure);
        }
        return [...groups.values()].sort((firstGroup, secondGroup) => {
            const firstLine = String(firstGroup[0]?.line || "");
            const secondLine = String(secondGroup[0]?.line || "");
            const firstNumber = Number.parseInt(firstLine, 10);
            const secondNumber = Number.parseInt(secondLine, 10);
            const firstIsNumeric = /^\d+$/.test(firstLine);
            const secondIsNumeric = /^\d+$/.test(secondLine);

            if (firstIsNumeric && secondIsNumeric) {
                return firstNumber - secondNumber;
            }
            if (firstIsNumeric !== secondIsNumeric) {
                return firstIsNumeric ? -1 : 1;
            }
            return firstLine.localeCompare(secondLine, undefined, {
                numeric: true,
                sensitivity: "base",
            });
        });
    }

    _rowsPerPage(cardSize, showDepartureAfter) {
        const fallback = { xs: 7, s: 6, m: 5, l: 4, xl: 3 }[cardSize];
        if (!this._availableHeight) {
            return fallback;
        }

        const gridUnit = 56;
        const rowUnits = {
            xs: 0.75,
            s: 1,
            m: 1.25,
            l: 1.5,
            xl: 1.5,
        }[cardSize];
        const fallbackChromeUnits = { xs: 1.25, s: 2, m: 2.5, l: 3, xl: 3 }[cardSize];
        const chromeHeight = this._chromeHeight || fallbackChromeUnits * gridUnit;
        const usableHeight = this._availableHeight - chromeHeight;
        const rows = Math.floor(usableHeight / (rowUnits * gridUnit));
        return Math.max(1, rows + (showDepartureAfter ? 0 : 1));
    }

    _render() {
        if (!this._hass) {
            return;
        }

        const entityId = this._entityId();
        const entity = entityId && this._hass.states[entityId];
        const departures = entity?.attributes?.departures || [];
        const sizeAliases = { small: "s", medium: "m", large: "l" };
        const requestedSize = this._config?.size || "xs";
        const cardSize = sizeAliases[requestedSize] || (
            ["xs", "s", "m", "l", "xl"].includes(requestedSize)
                ? requestedSize
                : "m"
        );
        const showDepartureAfter = this._config?.show_departure_after !== false;
        const showWheelchair = this._config?.show_wheelchair_accessible === true;
        const rowsPerPage = this._rowsPerPage(cardSize, showDepartureAfter);
        const pageSeconds = Math.max(
            1,
            Math.min(60, Number(this._config?.page_seconds) || 5),
        );
        const lineFilter = String(this._config?.lines || "")
            .split(",")
            .map((line) => line.trim().toLowerCase())
            .filter(Boolean);
        const filteredDepartures = lineFilter.length === 0
            ? departures
            : departures.filter((departure) => {
                const values = [departure.line, departure.line_name]
                    .filter(Boolean)
                    .map((value) => String(value).toLowerCase().trim());
                return lineFilter.some((line) => values.some((value) =>
                    value === line || value.endsWith(` ${line}`),
                ));
            });
        const groups = this._groupDepartures(filteredDepartures);
        const pageCount = Math.max(1, Math.ceil(groups.length / rowsPerPage));
        const elapsed = (Date.now() - this._pageStartedAt) / 1000;
        const pageIndex = Math.floor(elapsed / pageSeconds) % pageCount;
        const progress = pageCount === 1
            ? 1
            : (elapsed % pageSeconds) / pageSeconds;
        const pageGroups = groups.slice(
            pageIndex * rowsPerPage,
            (pageIndex + 1) * rowsPerPage,
        );
        const title = (this._config?.title || entity?.attributes.friendly_name || "Västtrafik")
            .replace(/\s+Next departure$/i, "");

        if (this._observedCard) {
            this._resizeObserver?.unobserve(this._observedCard);
            this._observedCard = null;
        }
        this.shadowRoot.innerHTML = `
            <style>
                :host { display: block; height: 100%; }
                ha-card { background: var(--ha-card-background, var(--card-background-color, #fff)); color: var(--primary-text-color, #212121); display: flex; flex-direction: column; height: 100%; overflow: hidden; }
                ha-card.without-then .columns, ha-card.without-then .departure { grid-template-columns: 24px 48px minmax(0, 1fr) 64px 64px; }
                .header { padding: 8px 16px 6px; font-size: 26px; font-weight: 700; }
                .columns, .departure { display: grid; grid-template-columns: 24px 48px minmax(0, 1fr) 64px 64px 64px; gap: 8px; align-items: center; }
                .columns { padding: 8px 16px 6px; color: var(--secondary-text-color, #5f6368); font-weight: 700; font-size: 12px; }
                .columns .stop-title { justify-self: start; align-self: center; color: var(--primary-text-color, #212121); font-size: 26px; line-height: 1; }
                .columns span { white-space: nowrap; }
                .columns span:nth-child(n + 4) { justify-self: center; text-align: center; }
                .departure { min-height: 84px; padding: 9px 16px; border-top: 1px solid var(--divider-color, #d7d9dc); box-sizing: border-box; }
                .mode { color: var(--secondary-text-color, #5f6368); text-align: center; }
                .mode ha-icon { --mdc-icon-size: 20px; }
                .line { background: var(--line-background); color: var(--line-foreground); border: 2px solid var(--line-border); border-radius: 5px; padding: 5px 2px; text-align: center; font-size: 18px; font-weight: 800; }
                .destination strong { display: block; font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
                small, .time span { display: block; color: var(--secondary-text-color, #5f6368); font-size: 11px; }
                .time { text-align: center; } .time strong { font-size: 22px; } .time.missing { color: var(--disabled-text-color, #9e9e9e); }
                .time.cancelled strong { color: var(--error-color, #db4437); font-size: 13px; text-transform: uppercase; }
                .time-main { align-items: center; display: flex; gap: 6px; justify-content: center; }
                .time-main ha-icon { color: var(--secondary-text-color, #5f6368); --mdc-icon-size: 18px; }
                .platform { background: var(--primary-text-color, #212121); border-radius: 50%; color: var(--ha-card-background, var(--card-background-color, #fff)); font-size: 16px; font-weight: 800; height: 30px; justify-self: center; line-height: 30px; text-align: center; width: 30px; }
                .departures { flex: 1 1 auto; min-height: 0; overflow: hidden; }
                .empty { padding: 20px; color: var(--secondary-text-color, #5f6368); }
                .pager { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 8px 12px 10px; color: var(--secondary-text-color, #5f6368); font-size: 11px; }
                .page-progress { background: var(--secondary-background-color, var(--divider-color, #d7d9dc)); border: 2px solid var(--primary-text-color, #212121); border-radius: 8px; box-sizing: border-box; display: block; flex: 0 0 128px; height: 12px; overflow: hidden; width: 128px; }
                .page-progress-fill { background: var(--primary-color, #03a9f4); display: block; height: 100%; transition: width 0.9s linear; width: 0; }
                .dot { border: 2px solid var(--primary-text-color, #212121); border-radius: 50%; box-sizing: border-box; height: 10px; width: 10px; }
                @media (max-width: 500px) { .columns, .departure { grid-template-columns: 22px 42px minmax(0, 1fr) 54px 54px 54px; gap: 5px; } .departure { padding: 8px 12px; } .columns { padding-left: 12px; padding-right: 12px; } .columns .stop-title { font-size: 22px; } .header { display: none; } .destination strong { font-size: 14px; } ha-card.without-then .columns, ha-card.without-then .departure { grid-template-columns: 22px 42px minmax(0, 1fr) 54px 54px; } }
                ha-card.xs .header, ha-card.s .header, ha-card.m .header, ha-card.l .header, ha-card.xl .header { display: none; }
                ha-card.xs .columns .stop-title { font-size: 20px; }
                ha-card.s .columns .stop-title { font-size: 22px; }
                ha-card.l .columns .stop-title { font-size: 30px; }
                ha-card.xl .columns .stop-title { font-size: 34px; }
                ha-card.xs .columns, ha-card.xs .departure { grid-template-columns: 18px 34px minmax(0, 1fr) 48px 48px 44px; gap: 4px; }
                ha-card.xs.without-then .columns, ha-card.xs.without-then .departure { grid-template-columns: 18px 34px minmax(0, 1fr) 48px 44px; }
                ha-card.xs .departure { min-height: 42px; padding: 3px 8px; }
                ha-card.xs .line { font-size: 14px; padding: 2px 1px; }
                ha-card.xs .mode ha-icon { --mdc-icon-size: 16px; }
                ha-card.xs .destination strong { font-size: 12px; }
                ha-card.xs .time strong { font-size: 15px; }
                ha-card.xs .time-main ha-icon { --mdc-icon-size: 15px; }
                ha-card.xs .time small, ha-card.xs .time span { display: none; }
                ha-card.xs .platform { font-size: 13px; height: 24px; line-height: 24px; width: 24px; }
                ha-card.s .columns, ha-card.s .departure { grid-template-columns: 20px 40px minmax(0, 1fr) 56px 56px 52px; gap: 5px; }
                ha-card.s.without-then .columns, ha-card.s.without-then .departure { grid-template-columns: 20px 40px minmax(0, 1fr) 56px 52px; }
                ha-card.s .departure { min-height: 56px; padding: 5px 12px; }
                ha-card.s .line { font-size: 15px; padding: 3px 1px; }
                ha-card.s .mode ha-icon { --mdc-icon-size: 18px; }
                ha-card.s .destination strong { font-size: 13px; }
                ha-card.s .time strong { font-size: 17px; }
                ha-card.s .time-main ha-icon { --mdc-icon-size: 16px; }
                ha-card.s .time small, ha-card.s .time span { display: none; }
                ha-card.s .platform { font-size: 14px; height: 26px; line-height: 26px; width: 26px; }
                ha-card.m .departure { min-height: 70px; }
                ha-card.m .mode ha-icon { --mdc-icon-size: 22px; }
                ha-card.l .header { padding: 10px 20px 7px; font-size: 30px; }
                ha-card.l .columns, ha-card.l .departure { grid-template-columns: 28px 58px minmax(0, 1fr) 76px 76px 76px; gap: 10px; }
                ha-card.l.without-then .columns, ha-card.l.without-then .departure { grid-template-columns: 28px 58px minmax(0, 1fr) 76px 76px; }
                ha-card.l .columns { padding: 12px 24px 10px; }
                ha-card.l .departure { min-height: 84px; padding: 16px 24px; }
                ha-card.l .line { font-size: 22px; padding: 7px 3px; }
                ha-card.l .mode ha-icon { --mdc-icon-size: 26px; }
                ha-card.l .columns { font-size: 13px; }
                ha-card.l .destination strong { font-size: 21px; }
                ha-card.l .destination small, ha-card.l .time small, ha-card.l .time span { font-size: 13px; }
                ha-card.l .time strong { font-size: 29px; }
                ha-card.l .platform { font-size: 19px; height: 36px; line-height: 36px; width: 36px; }
                ha-card.xl .header { padding: 12px 22px 8px; font-size: 34px; }
                ha-card.xl .columns, ha-card.xl .departure { grid-template-columns: 30px 64px minmax(0, 1fr) 84px 84px 84px; gap: 12px; }
                ha-card.xl.without-then .columns, ha-card.xl.without-then .departure { grid-template-columns: 30px 64px minmax(0, 1fr) 84px 84px; }
                ha-card.xl .columns { padding: 14px 28px 12px; }
                ha-card.xl .departure { min-height: 84px; padding: 18px 28px; }
                ha-card.xl .line { font-size: 24px; padding: 8px 4px; }
                ha-card.xl .mode ha-icon { --mdc-icon-size: 30px; }
                ha-card.xl .columns { font-size: 14px; }
                ha-card.xl .destination strong { font-size: 30px; }
                ha-card.xl .destination small, ha-card.xl .time small, ha-card.xl .time span { font-size: 14px; }
                ha-card.xl .time strong { font-size: 32px; }
                ha-card.xl .platform { font-size: 20px; height: 40px; line-height: 40px; width: 40px; }
            </style>
    <ha-card class="${cardSize} ${showDepartureAfter ? "with-then" : "without-then"}">
        <div class="header">${this._escape(title)}</div>
        <div class="columns"><span class="stop-title">${this._escape(title)}</span><span></span><span></span><span>${this._text("next")}</span>${showDepartureAfter ? `<span>${this._text("then")}</span>` : ""}<span>${this._text("platform")}</span></div>
                <div class="departures">${pageGroups.map((group) => this._row(group, cardSize, showDepartureAfter, showWheelchair)).join("") || `<div class="empty">${this._text("noDepartures")}</div>`}</div>
                ${pageCount > 1 ? `<div class="pager" aria-label="${this._text("page")} ${pageIndex + 1} / ${pageCount}">
                    <span>${this._text("page")} ${pageIndex + 1} / ${pageCount}</span>
                    ${Array.from({ length: pageCount }, (_, index) => index === pageIndex
            ? `<span class="page-progress"><span class="page-progress-fill" style="width:${progress * 100}%"></span></span>`
            : `<span class="dot"></span>`).join("")}
                </div>` : ""}
      </ha-card>
    `;
        const card = this.shadowRoot.querySelector("ha-card");
        if (card) {
            this._resizeObserver?.observe(card);
            this._observedCard = card;
        }
        const header = this.shadowRoot.querySelector(".header");
        const columns = this.shadowRoot.querySelector(".columns");
        const pager = this.shadowRoot.querySelector(".pager");
        const chromeHeight = [header, columns, pager].reduce(
            (height, element) => height + (element?.offsetHeight || 0),
            0,
        );
        if (chromeHeight && chromeHeight !== this._chromeHeight) {
            this._chromeHeight = chromeHeight;
            requestAnimationFrame(() => this._render());
        }
    }

    _row(group, cardSize, showDepartureAfter, showWheelchair) {
        const departure = group[0];
        const background = departure.line_background_color || "#555555";
        const foreground = departure.line_foreground_color || "#ffffff";
        const border = departure.line_border_color || background;
        const times = group.slice(0, showDepartureAfter ? 2 : 1);
        const direction = String(departure.direction || "");
        const via = direction.includes(" via ")
            ? `<small>${this._escape(direction.split(" via ")[1])}</small>`
            : "";
        const modeIcons = {
            bus: "mdi:bus",
            tram: "mdi:tram",
            train: "mdi:train",
            ferry: "mdi:ferry",
        };
        const modeIcon = modeIcons[departure.transport_mode] || "mdi:transit-connection-variant";

        const timeCells = Array.from({ length: showDepartureAfter ? 2 : 1 }, (_, index) => {
            const item = times[index];
            if (!item) {
                return '<div class="time missing">-</div>';
            }
            const minutes = this._minutes(item.estimated_time);
            const timeValue = item.cancelled
                ? this._text("cancelled")
                : minutes === 0 ? this._text("now") : minutes;
            const wheelchair = showWheelchair && item.is_wheelchair_accessible
                ? '<ha-icon icon="mdi:wheelchair"></ha-icon>'
                : "";
            return `<div class="time ${item.cancelled ? "cancelled" : ""} ${["xs", "s"].includes(cardSize) ? "compact" : ""}"><div class="time-main"><strong>${timeValue}</strong>${wheelchair}</div><span>${this._formatTime(item.estimated_time)}</span></div>`;
        });

        return `<div class="departure">
            <div class="mode"><ha-icon icon="${modeIcon}"></ha-icon></div>
      <div class="line" style="--line-background:${background};--line-foreground:${foreground};--line-border:${border}">${this._escape(departure.line)}</div>
            <div class="destination"><strong>${this._escape(direction.split(" via ")[0])}</strong>${via}</div>
      ${timeCells.join("")}
      <div class="platform">${this._escape(departure.platform || "-")}</div>
    </div>`;
    }

    _escape(value) {
        const element = document.createElement("div");
        element.textContent = String(value ?? "");
        return element.innerHTML;
    }
}

if (!customElements.get("vasttrafik-timetable-card")) {
    customElements.define("vasttrafik-timetable-card", VasttrafikTimetableCard);
}

class VasttrafikTimetableCardEditor extends HTMLElement {
    setConfig(config) {
        this._config = config;
        this._render();
    }

    set hass(hass) {
        this._hass = hass;
        this._render();
    }

    _render() {
        if (!this._hass) return;
        const swedish = (this._hass.locale?.language || this._hass.language || "en")
            .toLowerCase().startsWith("sv");
        const labels = swedish
            ? {
                entity: "Avgångsenhet", lines: "Linjer att visa",
                after: "Visa avgång efter", size: "Kortstorlek",
                seconds: "Sekunder per sida", wheelchair: "Visa rullstolsikon",
            }
            : {
                entity: "Departure entity", lines: "Lines to show",
                after: "Show departure after", size: "Card size",
                seconds: "Seconds per page", wheelchair: "Show wheelchair icon",
            };
        const entities = Object.keys(this._hass.states).filter((entityId) =>
            entityId.startsWith("sensor.") && Array.isArray(this._hass.states[entityId].attributes.departures),
        );
        this.innerHTML = `
            <style>
                label { display: grid; gap: 4px; margin: 8px 0; }
                input, select { box-sizing: border-box; padding: 6px; width: 100%; }
            </style>
            <label>${labels.entity}<select id="entity">${entities.map((entityId) => `<option value="${entityId}" ${entityId === this._config?.entity ? "selected" : ""}>${entityId}</option>`).join("")}</select></label>
            <label>${labels.lines} (comma-separated, optional)<input id="lines" type="text" placeholder="10, 12, 19" value="${this._config?.lines || ""}"></label>
            <label>${labels.after}<select id="show_departure_after">
                <option value="true" ${this._config?.show_departure_after !== false ? "selected" : ""}>True</option>
                <option value="false" ${this._config?.show_departure_after === false ? "selected" : ""}>False</option>
            </select></label>
            <label>${labels.wheelchair}<select id="show_wheelchair_accessible">
                <option value="false" ${this._config?.show_wheelchair_accessible !== true ? "selected" : ""}>False</option>
                <option value="true" ${this._config?.show_wheelchair_accessible === true ? "selected" : ""}>True</option>
            </select></label>
            <label>${labels.seconds}<input id="page_seconds" type="number" min="1" max="60" value="${this._config?.page_seconds || 5}"></label>
            <label>${labels.size}<select id="size">
                <option value="xs" ${!this._config?.size || this._config?.size === "xs" ? "selected" : ""}>XS (0.75 row)</option>
                <option value="s" ${this._config?.size === "s" ? "selected" : ""}>S (1 row)</option>
                <option value="m" ${["m", "medium"].includes(this._config?.size) ? "selected" : ""}>M (1.25 rows)</option>
                <option value="l" ${this._config?.size === "l" ? "selected" : ""}>L (1.5 rows)</option>
                <option value="xl" ${this._config?.size === "xl" ? "selected" : ""}>XL (1.5 rows)</option>
            </select></label>
        `;
        for (const id of ["entity", "lines", "show_departure_after", "show_wheelchair_accessible", "page_seconds", "size"]) {
            this.querySelector(`#${id}`).addEventListener("change", (event) => {
                const value = ["show_departure_after", "show_wheelchair_accessible"].includes(id)
                    ? event.target.value === "true"
                    : id === "page_seconds"
                        ? Number(event.target.value)
                        : event.target.value;
                this.dispatchEvent(new CustomEvent("config-changed", {
                    detail: { config: { ...this._config, [id]: value } },
                    bubbles: true,
                    composed: true,
                }));
            });
        }
    }
}

if (!customElements.get("vasttrafik-timetale-card")) {
    customElements.define(
        "vasttrafik-timetale-card",
        class extends VasttrafikTimetableCard { },
    );
}
if (!customElements.get("vasttrafik-timetable-card-editor")) {
    customElements.define("vasttrafik-timetable-card-editor", VasttrafikTimetableCardEditor);
}

window.VasttrafikTimetableCardImplementation = VasttrafikTimetableCard;
window.VasttrafikTimetableCardEditorImplementation = VasttrafikTimetableCardEditor;

window.customCards = window.customCards || [];
window.customCards.push({
    type: "vasttrafik-timetable-card",
    name: "Västtrafik departure board",
    description: "Västtrafik avgångstavla / colored departure board.",
    documentationURL: "https://ehoglid.github.io/hass-vasttrafik/",
    preview: true,
});