let locationData = [];

document.addEventListener("DOMContentLoaded", () => {
    loadLocations();
});

async function loadLocations() {
    const res = await fetch("/api/locations");
    locationData = await res.json();
    renderTree();
    populateCountrySelects();
}

function populateCountrySelects() {
    const selects = [
        document.getElementById("state-country-select"),
        document.getElementById("city-country-select"),
    ];
    selects.forEach((sel) => {
        const val = sel.value;
        sel.innerHTML = '<option value="">Select Country</option>';
        locationData.forEach((c) => {
            const opt = document.createElement("option");
            opt.value = c.id;
            opt.textContent = c.name;
            sel.appendChild(opt);
        });
        sel.value = val;
    });
}

function loadStatesForCity() {
    const countryId = document.getElementById("city-country-select").value;
    const stateSel = document.getElementById("city-state-select");
    stateSel.innerHTML = '<option value="">Select State</option>';

    if (!countryId) return;

    const country = locationData.find((c) => c.id == countryId);
    if (!country) return;

    country.states.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.id;
        opt.textContent = s.name;
        stateSel.appendChild(opt);
    });
}

function renderTree() {
    const container = document.getElementById("location-tree");
    container.innerHTML = "";

    if (locationData.length === 0) {
        container.innerHTML = '<p style="color:#999; text-align:center;">No locations added yet.</p>';
        return;
    }

    locationData.forEach((country) => {
        const countryDiv = document.createElement("div");
        countryDiv.className = "tree-country";

        countryDiv.innerHTML = `
            <div class="tree-country-header">
                <span class="tree-country-name">${escapeHtml(country.name)}</span>
                <div class="tree-actions">
                    <button class="btn btn-edit btn-sm" onclick="editCountry(${country.id}, '${escapeAttr(country.name)}')">Edit</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteCountry(${country.id}, '${escapeAttr(country.name)}')">Delete</button>
                </div>
            </div>
            <div class="tree-country-body" id="country-body-${country.id}"></div>
        `;

        container.appendChild(countryDiv);

        const body = countryDiv.querySelector(`#country-body-${country.id}`);

        if (country.states.length === 0) {
            body.innerHTML = '<p style="color:#ccc; font-size:0.85rem;">No states yet</p>';
        }

        country.states.forEach((state) => {
            const stateDiv = document.createElement("div");
            stateDiv.className = "tree-state";

            stateDiv.innerHTML = `
                <div class="tree-state-header">
                    <span class="tree-state-name">${escapeHtml(state.name)}</span>
                    <div class="tree-actions">
                        <button class="btn btn-edit btn-sm" onclick="editState(${state.id}, '${escapeAttr(state.name)}')">Edit</button>
                        <button class="btn btn-danger btn-sm" onclick="deleteState(${state.id}, '${escapeAttr(state.name)}')">Delete</button>
                    </div>
                </div>
                <div class="tree-state-body" id="state-body-${state.id}"></div>
            `;

            body.appendChild(stateDiv);

            const stateBody = stateDiv.querySelector(`#state-body-${state.id}`);

            if (state.cities.length === 0) {
                stateBody.innerHTML = '<span style="color:#ccc; font-size:0.85rem;">No cities yet</span>';
            }

            state.cities.forEach((city) => {
                const citySpan = document.createElement("span");
                citySpan.className = "tree-city";
                citySpan.innerHTML = `
                    <span class="city-name">${escapeHtml(city.name)}</span>
                    <button class="btn btn-edit btn-sm" onclick="editCity(${city.id}, '${escapeAttr(city.name)}')">Edit</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteCity(${city.id}, '${escapeAttr(city.name)}')">X</button>
                `;
                stateBody.appendChild(citySpan);
            });
        });
    });
}

// ─── Add Operations ─────────────────────────────────────────────

async function addCountry() {
    const input = document.getElementById("new-country-name");
    const name = input.value.trim();
    if (!name) return showToast("Please enter a country name", "error");

    const res = await fetch("/api/countries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
    });

    if (res.ok) {
        input.value = "";
        showToast("Country added successfully", "success");
        loadLocations();
    } else {
        const data = await res.json();
        showToast(data.error || "Failed to add country", "error");
    }
}

async function addState() {
    const countryId = document.getElementById("state-country-select").value;
    const input = document.getElementById("new-state-name");
    const name = input.value.trim();

    if (!countryId) return showToast("Please select a country", "error");
    if (!name) return showToast("Please enter a state name", "error");

    const res = await fetch("/api/states", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, country_id: parseInt(countryId) }),
    });

    if (res.ok) {
        input.value = "";
        showToast("State added successfully", "success");
        loadLocations();
    } else {
        const data = await res.json();
        showToast(data.error || "Failed to add state", "error");
    }
}

async function addCity() {
    const stateId = document.getElementById("city-state-select").value;
    const input = document.getElementById("new-city-name");
    const name = input.value.trim();

    if (!stateId) return showToast("Please select a state", "error");
    if (!name) return showToast("Please enter a city name", "error");

    const res = await fetch("/api/cities", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, state_id: parseInt(stateId) }),
    });

    if (res.ok) {
        input.value = "";
        showToast("City added successfully", "success");
        loadLocations();
    } else {
        const data = await res.json();
        showToast(data.error || "Failed to add city", "error");
    }
}

// ─── Edit Operations ────────────────────────────────────────────

let modalCallback = null;

function openModal(title, currentName, callback) {
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-input").value = currentName;
    document.getElementById("edit-modal").classList.remove("hidden");
    modalCallback = callback;

    document.getElementById("modal-save").onclick = async () => {
        const newName = document.getElementById("modal-input").value.trim();
        if (!newName) return showToast("Name cannot be empty", "error");
        await callback(newName);
        closeModal();
    };
}

function closeModal() {
    document.getElementById("edit-modal").classList.add("hidden");
    modalCallback = null;
}

function editCountry(id, currentName) {
    openModal("Edit Country", currentName, async (newName) => {
        const res = await fetch(`/api/countries/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: newName }),
        });
        if (res.ok) {
            showToast("Country updated", "success");
            loadLocations();
        }
    });
}

function editState(id, currentName) {
    openModal("Edit State", currentName, async (newName) => {
        const res = await fetch(`/api/states/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: newName }),
        });
        if (res.ok) {
            showToast("State updated", "success");
            loadLocations();
        }
    });
}

function editCity(id, currentName) {
    openModal("Edit City", currentName, async (newName) => {
        const res = await fetch(`/api/cities/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: newName }),
        });
        if (res.ok) {
            showToast("City updated", "success");
            loadLocations();
        }
    });
}

// ─── Delete Operations ──────────────────────────────────────────

async function deleteCountry(id, name) {
    if (!confirm(`Delete country "${name}" and all its states/cities?`)) return;

    const res = await fetch(`/api/countries/${id}`, { method: "DELETE" });
    if (res.ok) {
        showToast("Country deleted", "success");
        loadLocations();
    }
}

async function deleteState(id, name) {
    if (!confirm(`Delete state "${name}" and all its cities?`)) return;

    const res = await fetch(`/api/states/${id}`, { method: "DELETE" });
    if (res.ok) {
        showToast("State deleted", "success");
        loadLocations();
    }
}

async function deleteCity(id, name) {
    if (!confirm(`Delete city "${name}"?`)) return;

    const res = await fetch(`/api/cities/${id}`, { method: "DELETE" });
    if (res.ok) {
        showToast("City deleted", "success");
        loadLocations();
    }
}

// ─── Utilities ──────────────────────────────────────────────────

function showToast(message, type) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = `toast ${type}`;
    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3000);
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/'/g, "\\'").replace(/"/g, '\\"');
}
