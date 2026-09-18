window.__vasttrafikTimetableCardLoaded = true;

const implementationUrl = new URL(
    "./vasttrafik-timetable-card.js",
    import.meta.url,
);
implementationUrl.search = new URL(import.meta.url).search;

let implementationPromise;

function loadImplementation() {
    implementationPromise ||= import(implementationUrl.href);
    return implementationPromise;
}

function renderPlaceholder(root, message = "Loading Västtrafik timetable...") {
    root.innerHTML = `
        <ha-card>
            <div style="padding: 16px; color: var(--secondary-text-color);">
                ${message}
            </div>
        </ha-card>
    `;
}

class VasttrafikTimetableCardLoader extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: "open" });
        this._config = undefined;
        this._hass = undefined;
        this._element = undefined;
        this._loading = false;
        renderPlaceholder(this.shadowRoot);
    }

    setConfig(config) {
        this._config = config;
        this._element?.setConfig(config);
        this._load();
    }

    set hass(hass) {
        this._hass = hass;
        if (this._element) {
            this._element.hass = hass;
        }
        this._load();
    }

    connectedCallback() {
        this._load();
    }

    disconnectedCallback() {
        this._element?.remove();
        this._element = undefined;
    }

    getCardSize() {
        return this._element?.getCardSize?.() ?? 6;
    }

    getGridOptions() {
        return this._element?.getGridOptions?.() ?? {
            rows: 6,
            columns: 12,
            min_rows: 3,
            min_columns: 6,
        };
    }

    async _load() {
        if (this._loading || this._element) {
            return;
        }

        this._loading = true;
        try {
            await loadImplementation();
            const implementationClass = window.VasttrafikTimetableCardImplementation;
            if (!implementationClass) {
                throw new Error("Västtrafik timetable implementation did not load");
            }
            const tag = "vasttrafik-timetable-card-implementation";
            if (!customElements.get(tag)) {
                customElements.define(tag, implementationClass);
            }
            const element = document.createElement(tag);
            this.shadowRoot.replaceChildren(element);
            this._element = element;
            if (this._config !== undefined) {
                element.setConfig(this._config);
            }
            if (this._hass !== undefined) {
                element.hass = this._hass;
            }
        } catch (error) {
            console.error("Failed to load Västtrafik timetable card", error);
            renderPlaceholder(this.shadowRoot, "Unable to load Västtrafik timetable.");
        } finally {
            this._loading = false;
        }
    }

    static getConfigElement() {
        return document.createElement("vasttrafik-timetable-card-editor");
    }

    static getStubConfig() {
        return {};
    }
}

class VasttrafikTimetableCardEditorLoader extends HTMLElement {
    constructor() {
        super();
        this._config = undefined;
        this._hass = undefined;
        this._element = undefined;
        this._loading = false;
    }

    setConfig(config) {
        this._config = config;
        this._element?.setConfig(config);
        this._load();
    }

    set hass(hass) {
        this._hass = hass;
        if (this._element) {
            this._element.hass = hass;
        }
        this._load();
    }

    connectedCallback() {
        this._load();
    }

    async _load() {
        if (this._loading || this._element) {
            return;
        }

        this._loading = true;
        try {
            await loadImplementation();
            const editorClass = window.VasttrafikTimetableCardEditorImplementation;
            if (!editorClass) {
                throw new Error("Västtrafik timetable editor did not load");
            }
            const tag = "vasttrafik-timetable-card-editor-implementation";
            if (!customElements.get(tag)) {
                customElements.define(tag, editorClass);
            }
            const element = document.createElement(tag);
            this.replaceChildren(element);
            this._element = element;
            if (this._config !== undefined) {
                element.setConfig(this._config);
            }
            if (this._hass !== undefined) {
                element.hass = this._hass;
            }
        } catch (error) {
            console.error("Failed to load Västtrafik timetable card editor", error);
            this.textContent = "Unable to load Västtrafik timetable editor.";
        } finally {
            this._loading = false;
        }
    }
}

if (!customElements.get("vasttrafik-timetable-card")) {
    customElements.define(
        "vasttrafik-timetable-card",
        VasttrafikTimetableCardLoader,
    );
}
if (!customElements.get("vasttrafik-timetale-card")) {
    customElements.define(
        "vasttrafik-timetale-card",
        class extends VasttrafikTimetableCardLoader {},
    );
}
if (!customElements.get("vasttrafik-timetable-card-editor")) {
    customElements.define(
        "vasttrafik-timetable-card-editor",
        VasttrafikTimetableCardEditorLoader,
    );
}

window.customCards = window.customCards || [];
window.customCards.push({
    type: "vasttrafik-timetable-card",
    name: "Västtrafik departure board",
    description: "Västtrafik avgångstavla / colored departure board.",
    documentationURL: "https://ehoglid.github.io/hass-vasttrafik/",
    preview: true,
});
