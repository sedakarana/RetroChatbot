const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const clearBtn = document.getElementById("clear");
const statusEl = document.getElementById("status");
const modeBtn = document.getElementById("modeBtn");

// Her mod icin metinler
const THEMES = {
  retro: {
    title: "RetroBot 95 - Hos Geldiniz!!!",
    botLabel: "RetroBot95",
    youLabel: "Siz",
    errLabel: "HATA",
    placeholder: "Bir seyler yazin...",
    send: "Gonder",
    clear: "Temizle",
    ready: "Baglanti hazir. 28.8 Kbps",
    busy: "Baglaniyor... bip-bip-cirrrr... lutfen bekleyin",
    errSuffix: " (Modem baglantisi koptu mu?)",
    greeting: "Merhaba! Ben RetroBot 95. Yillardan 1996, internet harika degil mi? Bana bir sey sorun! :-)",
  },
  future: {
    title: "NEXUS 2030",
    botLabel: "",
    youLabel: "",
    errLabel: "",
    placeholder: "NEXUS'a bir mesaj yaz...",
    send: "Gonder",
    clear: "Temizle",
    ready: "Neural baglanti aktif · gecikme 4 ms",
    busy: "NEXUS dusunuyor...",
    errSuffix: "",
    greeting: "Merhaba, ben NEXUS. 2030'un kisisel asistaniyim. Bugun sana nasil yardimci olabilirim?",
  },
};

let mode = "retro";
let history = [];

// ---------------- Hava durumu ----------------
const citySel = document.getElementById("city");
const weatherBody = document.getElementById("weatherBody");
let lastWeather = null;

const WEATHER_ICONS = {
  retro: { clear: "\\o/ (*)", cloud: "( ~~~ )", fog: "= = = =", rain: "' ' ' '", snow: "* * * *", storm: "/!\\ ZAP" },
  future: { clear: "☀️", cloud: "☁️", fog: "🌫️", rain: "🌧️", snow: "❄️", storm: "⛈️" },
};

function renderWeather() {
  const w = lastWeather;
  weatherBody.textContent = "";
  if (!w) return;

  const make = (cls, text) => {
    const el = document.createElement("div");
    el.className = cls;
    el.textContent = text;
    return el;
  };
  weatherBody.append(
    make("w-icon", WEATHER_ICONS[mode][w.icon] || ""),
    make("w-temp", w.temp + "°C"),
    make("w-desc", w.description),
    make("w-meta", "Hissedilen: " + w.feels_like + "°C"),
    make("w-meta", "Nem: %" + w.humidity + " · Ruzgar: " + w.wind + " km/s")
  );
}

async function loadWeather() {
  weatherBody.textContent = "Yukleniyor...";
  try {
    const res = await fetch("/weather?city=" + encodeURIComponent(citySel.value));
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Hata");
    lastWeather = data;
    renderWeather();
  } catch (err) {
    lastWeather = null;
    weatherBody.textContent = "Hava durumu alinamadi.";
  }
}

citySel.addEventListener("change", () => {
  try { localStorage.setItem("city", citySel.value); } catch (_) { /* yoksay */ }
  loadWeather();
});

// Sahte ziyaretci sayaci (1990'lar ruhu icin)
(function counter() {
  let n = 1337;
  try {
    n = parseInt(localStorage.getItem("visits") || "1337", 10) + 1;
    localStorage.setItem("visits", n);
  } catch (_) { /* localStorage kullanilamiyorsa sorun degil */ }
  document.getElementById("counter").textContent = String(n).padStart(6, "0");
})();

function addLine(who, text) {
  const t = THEMES[mode];
  const div = document.createElement("div");
  div.className = "line " + who;
  const label = who === "you" ? t.youLabel : who === "bot" ? t.botLabel : t.errLabel;
  div.textContent = label ? "<" + label + "> " + text : text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function setBusy(busy) {
  const t = THEMES[mode];
  input.disabled = busy;
  sendBtn.disabled = busy;
  statusEl.textContent = busy ? t.busy : t.ready;
  if (!busy) input.focus();
}

function applyMode(newMode) {
  mode = newMode;
  const t = THEMES[mode];
  document.body.classList.toggle("future", mode === "future");
  document.title = t.title;
  input.placeholder = t.placeholder;
  sendBtn.value = t.send;
  clearBtn.value = t.clear;
  statusEl.textContent = t.ready;
  renderWeather();
  try { localStorage.setItem("mode", mode); } catch (_) { /* yoksay */ }

  // Mod degisince sohbet sifirlanir ve yeni karakter kendini tanitir
  chat.innerHTML = "";
  history = [];
  addLine("bot", t.greeting);
  input.focus();
}

modeBtn.addEventListener("click", () => {
  applyMode(mode === "retro" ? "future" : "retro");
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  addLine("you", message);
  input.value = "";
  setBusy(true);

  const currentMode = mode;
  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history, mode: currentMode }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Bilinmeyen hata");

    // Cevap beklenirken mod degistiyse eski modun cevabini gosterme
    if (currentMode !== mode) return;
    addLine("bot", data.reply);
    history.push({ role: "user", text: message }, { role: "bot", text: data.reply });
    history = history.slice(-20);
  } catch (err) {
    if (currentMode === mode) addLine("err", err.message + THEMES[mode].errSuffix);
  } finally {
    setBusy(false);
  }
});

clearBtn.addEventListener("click", () => {
  chat.innerHTML = "";
  history = [];
});

let savedMode = "retro";
try { savedMode = localStorage.getItem("mode") === "future" ? "future" : "retro"; } catch (_) { /* yoksay */ }
applyMode(savedMode);

try {
  const savedCity = localStorage.getItem("city");
  if (savedCity && [...citySel.options].some((o) => o.value === savedCity)) citySel.value = savedCity;
} catch (_) { /* yoksay */ }
loadWeather();
