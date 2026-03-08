const $ = (id) => document.getElementById(id);

async function fileToDataUrl(file) {
  if (!file) return "";
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result || "");
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function parseFeatures(text) {
  return (text || "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

function setStatus(text) {
  const status = $("storeStatus");
  status.textContent = text;
  status.hidden = !text;
  status.classList.remove("alert-work", "alert-ok", "alert-error");
  if (!text) return;
  if (text.startsWith("Ошибка")) {
    status.classList.add("alert-error");
    return;
  }
  if (text.startsWith("Сохранено")) {
    status.classList.add("alert-ok");
    return;
  }
  status.classList.add("alert-work");
}

function setAiButtonLoading(buttonId, isLoading, baseLabel) {
  const btn = $(buttonId);
  if (!btn) return;
  btn.disabled = isLoading;
  btn.classList.toggle("loading", isLoading);
  btn.textContent = isLoading ? "Распознавание..." : baseLabel;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return data;
}

function fillShoeFields(data) {
  if (!data) return;
  $("shoeName").value = data.name || $("shoeName").value;
  $("season").value = data.season || $("season").value;
  $("shoeType").value = data.type || $("shoeType").value;
  $("shoeColor").value = data.color || $("shoeColor").value;
  $("genderStyle").value = data.gender_style || $("genderStyle").value;
}

function fillBoxFields(data) {
  if (!data) return;
  $("boxColor").value = data.color || $("boxColor").value;
  $("boxForm").value = data.form || $("boxForm").value;
  $("boxFeatures").value = Array.isArray(data.special_features)
    ? data.special_features.join(", ")
    : $("boxFeatures").value;
  $("boxFingerprint").value = data.visual_fingerprint || $("boxFingerprint").value;
}

function fillLocationFields(data) {
  if (!data) return;
  $("zone").value = data.zone || $("zone").value;
  $("spot").value = data.spot || $("spot").value;
}

async function analyze(objectType, fileInputId) {
  const file = $(fileInputId).files[0];
  if (!file) throw new Error("Сначала выберите фото");
  const imageData = await fileToDataUrl(file);
  return api("/api/ai/analyze", {
    method: "POST",
    body: JSON.stringify({ image_data: imageData, object_type: objectType }),
  });
}

function wireImagePreview(fileInputId, imgId) {
  const input = $(fileInputId);
  const img = $(imgId);
  if (!input || !img) return;

  input.addEventListener("change", async () => {
    const file = input.files[0];
    if (!file) {
      img.src = "";
      img.hidden = true;
      return;
    }
    const dataUrl = await fileToDataUrl(file);
    img.src = dataUrl;
    img.hidden = false;
  });
}

async function saveStoreFlow(event) {
  event.preventDefault();
  setStatus("Сохранение...");

  try {
    const shoePhoto = await fileToDataUrl($("shoePhoto").files[0]);
    const boxPhoto = await fileToDataUrl($("boxPhoto").files[0]);
    const locationPhoto = await fileToDataUrl($("locationPhoto").files[0]);

    const locationRes = await api("/api/locations", {
      method: "POST",
      body: JSON.stringify({
        zone: $("zone").value.trim(),
        spot: $("spot").value.trim(),
        photo_data: locationPhoto || null,
      }),
    });

    const boxRes = await api("/api/boxes", {
      method: "POST",
      body: JSON.stringify({
        location_id: locationRes.id,
        photo_data: boxPhoto,
        color: $("boxColor").value.trim(),
        form: $("boxForm").value.trim(),
        special_features: parseFeatures($("boxFeatures").value),
        visual_fingerprint: $("boxFingerprint").value.trim(),
      }),
    });
    const boxId = boxRes.id;

    const shoeRes = await api("/api/shoe-pairs", {
      method: "POST",
      body: JSON.stringify({
        name: $("shoeName").value.trim(),
        photo_data: shoePhoto,
        season: $("season").value,
        type: $("shoeType").value.trim(),
        color: $("shoeColor").value.trim(),
        gender_style: $("genderStyle").value.trim(),
        status: "хранится",
        box_id: boxId,
      }),
    });

    setStatus(`Сохранено: пара #${shoeRes.id}`);
    $("storeForm").reset();
    $("shoePreview").hidden = true;
    $("boxPreview").hidden = true;
    $("locationPreview").hidden = true;
    await runSearch();
  } catch (err) {
    setStatus(`Ошибка: ${err.message}`);
  }
}

async function runSearch(event) {
  if (event) event.preventDefault();
  const query = $("searchQuery").value.trim();
  const season = $("searchSeason").value;

  const params = new URLSearchParams();
  if (query) params.set("query", query);
  if (season) params.set("season", season);

  const res = await api(`/api/shoe-pairs?${params.toString()}`);
  renderResults(res.items || []);
}

function renderResults(items) {
  const root = $("results");
  const counter = $("resultsCount");
  root.innerHTML = "";

  if (counter) {
    counter.hidden = false;
    counter.textContent = `${items.length} ${items.length === 1 ? "пара" : "пар"}`;
  }

  if (!items.length) {
    root.innerHTML = "<div class=\"empty\">Обувь не найдена. Попробуйте изменить запрос.</div>";
    return;
  }

  const tpl = $("resultItemTpl");
  items.forEach((item) => {
    const node = tpl.content.cloneNode(true);
    const shoeImg = node.querySelector(".shoe-img");
    const boxImg = node.querySelector(".box-img");
    const text = node.querySelector(".result-text");
    const actions = node.querySelector(".result-actions");

    shoeImg.src = item.photo_data || "";
    shoeImg.style.display = item.photo_data ? "block" : "none";
    boxImg.src = item.box_photo || "";
    boxImg.style.display = item.box_photo ? "block" : "none";

    const title = item.name || `${item.season} ${item.type}`;
    text.innerHTML = `
      <strong>${title}</strong>
      <div class="result-meta">
        <span class="badge">${item.season}</span>
        <span class="badge">${item.type}</span>
        <span class="badge">${item.status}</span>
      </div>
      <div>Место: <strong>${item.zone} -> ${item.spot}</strong></div>
      <div>Коробка: #${item.box_id}</div>
    `;

    const retrieveBtn = document.createElement("button");
    retrieveBtn.textContent = "Взял обувь";
    retrieveBtn.className = "primary";
    retrieveBtn.onclick = async () => {
      await api(`/api/shoe-pairs/${item.id}/retrieve`, { method: "POST", body: "{}" });
      await runSearch();
    };

    const storeBtn = document.createElement("button");
    storeBtn.textContent = "Вернул на хранение";
    storeBtn.className = item.status === "хранится" ? "" : "primary";
    storeBtn.onclick = async () => {
      await api(`/api/shoe-pairs/${item.id}/store`, { method: "POST", body: "{}" });
      await runSearch();
    };

    actions.appendChild(retrieveBtn);
    actions.appendChild(storeBtn);
    root.appendChild(node);
  });
}

async function loadConfig() {
  const badge = $("configBadge");
  try {
    const cfg = await api("/api/config");
    if (!cfg.openrouter_enabled) {
      badge.textContent = "OpenRouter: ключ не задан, AI недоступен";
      return;
    }
    badge.textContent = `OpenRouter: ${cfg.model}`;
  } catch {
    badge.textContent = "Не удалось получить конфиг";
  }
}

function initTabs() {
  const triggers = document.querySelectorAll(".tab-trigger");
  const panels = document.querySelectorAll(".tab-panel");
  if (!triggers.length || !panels.length) return;

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const target = trigger.dataset.tabTarget;
      if (!target) return;

      triggers.forEach((btn) => {
        const active = btn === trigger;
        btn.classList.toggle("is-active", active);
        btn.setAttribute("aria-selected", active ? "true" : "false");
      });

      panels.forEach((panel) => {
        const active = panel.dataset.tabPanel === target;
        panel.classList.toggle("is-active", active);
        panel.hidden = !active;
      });
    });
  });
}

$("analyzeShoe").addEventListener("click", async () => {
  setAiButtonLoading("analyzeShoe", true, "AI: распознать обувь");
  setStatus("Распознавание обуви...");
  try {
    const res = await analyze("shoe", "shoePhoto");
    fillShoeFields(res.data);
    setStatus("Обувь распознана. Проверьте и при необходимости отредактируйте поля.");
  } catch (err) {
    setStatus(`Ошибка AI: ${err.message}`);
  } finally {
    setAiButtonLoading("analyzeShoe", false, "AI: распознать обувь");
  }
});

$("analyzeBox").addEventListener("click", async () => {
  setAiButtonLoading("analyzeBox", true, "AI: распознать коробку");
  setStatus("Распознавание коробки...");
  try {
    const res = await analyze("box", "boxPhoto");
    fillBoxFields(res.data);
    setStatus("Коробка распознана. Проверьте признаки.");
  } catch (err) {
    setStatus(`Ошибка AI: ${err.message}`);
  } finally {
    setAiButtonLoading("analyzeBox", false, "AI: распознать коробку");
  }
});

$("analyzeLocation").addEventListener("click", async () => {
  setAiButtonLoading("analyzeLocation", true, "AI: распознать место");
  setStatus("Распознавание места...");
  try {
    const file = $("locationPhoto").files[0];
    if (!file) throw new Error("Сначала выберите фото места");
    const res = await analyze("location", "locationPhoto");
    fillLocationFields(res.data);
    setStatus("Место распознано. Проверьте зону и место.");
  } catch (err) {
    setStatus(`Ошибка AI: ${err.message}`);
  } finally {
    setAiButtonLoading("analyzeLocation", false, "AI: распознать место");
  }
});

$("storeForm").addEventListener("submit", saveStoreFlow);
$("searchForm").addEventListener("submit", runSearch);
wireImagePreview("shoePhoto", "shoePreview");
wireImagePreview("boxPhoto", "boxPreview");
wireImagePreview("locationPhoto", "locationPreview");

initTabs();
loadConfig();
runSearch();
