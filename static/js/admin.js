let locationData = [];
let menuData = [];

document.addEventListener("DOMContentLoaded", () => {
    loadLocations();
    loadMenuItems();
    loadLogo();
    loadCategories();
});

// ─── Sidebar Navigation ─────────────────────────────────────────

function showPage(page, el) {
    document.querySelectorAll(".admin-page").forEach((p) => p.classList.remove("active"));
    document.getElementById("page-" + page).classList.add("active");
    document.querySelectorAll(".sidebar .sidebar-link[data-page]").forEach((l) => l.classList.remove("active"));
    if (el) el.classList.add("active");
    if (window.innerWidth < 900) document.querySelector(".sidebar").classList.remove("open");
}

function toggleDropdown(el) {
    const menu = el.nextElementSibling;
    menu.classList.toggle("open");
    el.querySelector(".sidebar-chevron").classList.toggle("rotated");
}

function toggleSidebar() {
    document.querySelector(".sidebar").classList.toggle("open");
}

// ─── Data Loading ───────────────────────────────────────────────

async function loadLocations() {
    const res = await fetch("/api/locations");
    locationData = await res.json();
    renderCountriesList();
    renderStatesList();
    renderCitiesList();
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

// ─── Render Tables ──────────────────────────────────────────────

function renderCountriesList() {
    const container = document.getElementById("countries-list");
    if (locationData.length === 0) {
        container.innerHTML = '<p class="empty-msg">No countries added yet.</p>';
        return;
    }

    let html = '<table class="data-table"><thead><tr><th>#</th><th>Country Name</th><th>States</th><th>Actions</th></tr></thead><tbody>';
    locationData.forEach((c, i) => {
        html += `<tr>
            <td>${i + 1}</td>
            <td>${escapeHtml(c.name)}</td>
            <td>${c.states.length}</td>
            <td class="table-actions">
                <button class="btn btn-edit btn-sm" onclick="editCountry(${c.id}, '${escapeAttr(c.name)}')">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteCountry(${c.id}, '${escapeAttr(c.name)}')">Delete</button>
            </td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

function renderStatesList() {
    const container = document.getElementById("states-list");
    let allStates = [];
    locationData.forEach((c) => {
        c.states.forEach((s) => {
            allStates.push({ ...s, countryName: c.name, countryId: c.id });
        });
    });

    if (allStates.length === 0) {
        container.innerHTML = '<p class="empty-msg">No states added yet.</p>';
        return;
    }

    let html = '<table class="data-table"><thead><tr><th>#</th><th>State Name</th><th>Country</th><th>Cities</th><th>Actions</th></tr></thead><tbody>';
    allStates.forEach((s, i) => {
        html += `<tr>
            <td>${i + 1}</td>
            <td>${escapeHtml(s.name)}</td>
            <td>${escapeHtml(s.countryName)}</td>
            <td>${s.cities.length}</td>
            <td class="table-actions">
                <button class="btn btn-edit btn-sm" onclick="editState(${s.id}, '${escapeAttr(s.name)}')">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteState(${s.id}, '${escapeAttr(s.name)}')">Delete</button>
            </td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

function renderCitiesList() {
    const container = document.getElementById("cities-list");
    let allCities = [];
    locationData.forEach((c) => {
        c.states.forEach((s) => {
            s.cities.forEach((city) => {
                allCities.push({ ...city, stateName: s.name, countryName: c.name });
            });
        });
    });

    if (allCities.length === 0) {
        container.innerHTML = '<p class="empty-msg">No cities added yet.</p>';
        return;
    }

    let html = '<table class="data-table"><thead><tr><th>#</th><th>City Name</th><th>State</th><th>Country</th><th>Actions</th></tr></thead><tbody>';
    allCities.forEach((city, i) => {
        html += `<tr>
            <td>${i + 1}</td>
            <td>${escapeHtml(city.name)}</td>
            <td>${escapeHtml(city.stateName)}</td>
            <td>${escapeHtml(city.countryName)}</td>
            <td class="table-actions">
                <button class="btn btn-edit btn-sm" onclick="editCity(${city.id}, '${escapeAttr(city.name)}')">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteCity(${city.id}, '${escapeAttr(city.name)}')">Delete</button>
            </td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
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
    const urlField = document.getElementById("modal-url-input");
    if (urlField) urlField.style.display = "none";
    const colorField = document.getElementById("modal-color-input");
    if (colorField) colorField.style.display = "none";
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

// ─── Menu Items ─────────────────────────────────────────────────

async function loadMenuItems() {
    const res = await fetch("/api/menu-items");
    menuData = await res.json();
    renderMenuItemsList();
}

function renderMenuItemsList() {
    const container = document.getElementById("menu-items-list");
    if (menuData.length === 0) {
        container.innerHTML = '<p class="empty-msg">No menu items added yet.</p>';
        return;
    }

    let html = '<table class="data-table"><thead><tr><th>#</th><th>Name</th><th>URL</th><th>Actions</th></tr></thead><tbody>';
    menuData.forEach((m, i) => {
        html += `<tr>
            <td>${i + 1}</td>
            <td>${escapeHtml(m.name)}</td>
            <td><a href="${escapeHtmlAttr(m.url)}" target="_blank" style="color:#42a5f5;word-break:break-all;">${escapeHtml(m.url)}</a></td>
            <td class="table-actions">
                <button class="btn btn-edit btn-sm" onclick="editMenuItem(${m.id}, '${escapeAttr(m.name)}', '${escapeAttr(m.url)}')">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteMenuItem(${m.id}, '${escapeAttr(m.name)}')">Delete</button>
            </td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

async function addMenuItem() {
    const nameInput = document.getElementById("new-menu-name");
    const urlInput = document.getElementById("new-menu-url");
    const name = nameInput.value.trim();
    const url = urlInput.value.trim();

    if (!name) return showToast("Please enter a menu name", "error");
    if (!url) return showToast("Please enter a URL", "error");

    const res = await fetch("/api/menu-items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, url }),
    });

    if (res.ok || res.status === 201) {
        nameInput.value = "";
        urlInput.value = "";
        showToast("Menu item added", "success");
        loadMenuItems();
    } else {
        const data = await res.json();
        showToast(data.error || "Failed to add menu item", "error");
    }
}

function editMenuItem(id, currentName, currentUrl) {
    document.getElementById("modal-title").textContent = "Edit Menu Item";
    document.getElementById("modal-input").value = currentName;

    const urlField = document.getElementById("modal-url-input");
    if (urlField) {
        urlField.style.display = "block";
        urlField.value = currentUrl;
    }

    document.getElementById("edit-modal").classList.remove("hidden");

    document.getElementById("modal-save").onclick = async () => {
        const newName = document.getElementById("modal-input").value.trim();
        const newUrl = urlField ? urlField.value.trim() : currentUrl;
        if (!newName) return showToast("Name cannot be empty", "error");

        const res = await fetch(`/api/menu-items/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: newName, url: newUrl }),
        });
        if (res.ok) {
            showToast("Menu item updated", "success");
            loadMenuItems();
        }
        closeModal();
    };
}

async function deleteMenuItem(id, name) {
    if (!confirm(`Delete menu item "${name}"?`)) return;

    const res = await fetch(`/api/menu-items/${id}`, { method: "DELETE" });
    if (res.ok) {
        showToast("Menu item deleted", "success");
        loadMenuItems();
    }
}

// ─── Logo Management ────────────────────────────────────────────

async function loadLogo() {
    const res = await fetch("/api/logo");
    const data = await res.json();
    const preview = document.getElementById("logo-preview");
    if (!preview) return;

    if (data.logo_url) {
        preview.innerHTML = `<img src="${escapeHtmlAttr(data.logo_url)}" alt="Current Logo" style="max-height:80px;max-width:300px;border:1px solid #444;border-radius:8px;padding:8px;background:#222;">`;
    } else {
        preview.innerHTML = '<p class="empty-msg">No logo uploaded. The site header shows "Classified" text.</p>';
    }
}

async function uploadLogo() {
    const input = document.getElementById("logo-file-input");
    if (!input.files || !input.files[0]) {
        return showToast("Please select an image file", "error");
    }

    const formData = new FormData();
    formData.append("file", input.files[0]);

    const res = await fetch("/api/logo", {
        method: "POST",
        body: formData,
    });

    if (res.ok) {
        showToast("Logo uploaded successfully", "success");
        input.value = "";
        loadLogo();
    } else {
        const data = await res.json();
        showToast(data.error || "Failed to upload logo", "error");
    }
}

async function deleteLogo() {
    if (!confirm("Remove the website logo? The header will show 'Classified' text instead.")) return;

    const res = await fetch("/api/logo", { method: "DELETE" });
    if (res.ok) {
        showToast("Logo deleted", "success");
        loadLogo();
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

// ─── Categories ─────────────────────────────────────────────────

let categoryData = [];

async function loadCategories() {
    const res = await fetch("/api/categories");
    categoryData = await res.json();
    renderCategoriesList();
}

function renderCategoriesList() {
    const container = document.getElementById("categories-list");
    if (!container) return;
    if (categoryData.length === 0) {
        container.innerHTML = '<p class="empty-msg">No categories added yet.</p>';
        return;
    }

    let html = '<table class="data-table"><thead><tr><th>#</th><th>Name</th><th>Color</th><th>Actions</th></tr></thead><tbody>';
    categoryData.forEach((c, i) => {
        html += `<tr>
            <td>${i + 1}</td>
            <td>${escapeHtml(c.name)}</td>
            <td><span style="display:inline-block;width:30px;height:20px;border-radius:4px;background:${escapeHtmlAttr(c.color)};vertical-align:middle;"></span> ${escapeHtml(c.color)}</td>
            <td class="table-actions">
                <button class="btn btn-edit btn-sm" onclick="editCategory(${c.id}, '${escapeAttr(c.name)}', '${escapeAttr(c.color)}')">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteCategory(${c.id}, '${escapeAttr(c.name)}')">Delete</button>
            </td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

async function addCategory() {
    const nameInput = document.getElementById("cat-name-input");
    const colorInput = document.getElementById("cat-color-input");
    const name = nameInput.value.trim();
    const color = colorInput.value;

    if (!name) return showToast("Please enter a category name", "error");

    const res = await fetch("/api/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, color }),
    });

    if (res.ok) {
        nameInput.value = "";
        showToast("Category added successfully", "success");
        loadCategories();
    } else {
        const data = await res.json();
        showToast(data.error || "Failed to add category", "error");
    }
}

function editCategory(id, currentName, currentColor) {
    openModal("Edit Category", currentName, async (newName) => {
        const colorInput = document.getElementById("modal-color-input");
        const newColor = colorInput ? colorInput.value : currentColor;
        const res = await fetch(`/api/categories/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: newName, color: newColor }),
        });
        if (res.ok) {
            showToast("Category updated", "success");
            loadCategories();
        }
    });
    // Add color picker to modal
    setTimeout(() => {
        let colorField = document.getElementById("modal-color-input");
        if (!colorField) {
            colorField = document.createElement("input");
            colorField.type = "color";
            colorField.id = "modal-color-input";
            colorField.style.cssText = "width:50px;height:36px;border:none;cursor:pointer;margin-top:8px;";
            document.getElementById("modal-input").parentNode.appendChild(colorField);
        }
        colorField.value = currentColor;
        colorField.style.display = "block";
    }, 50);
}

async function deleteCategory(id, name) {
    if (!confirm(`Delete category "${name}"?`)) return;

    const res = await fetch(`/api/categories/${id}`, { method: "DELETE" });
    if (res.ok) {
        showToast("Category deleted", "success");
        loadCategories();
    }
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function escapeHtmlAttr(str) {
    return escapeHtml(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function escapeAttr(str) {
    return str
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/"/g, '\\x22')
        .replace(/</g, '\\x3c')
        .replace(/>/g, '\\x3e')
        .replace(/\n/g, '\\n')
        .replace(/\r/g, '\\r');
}
