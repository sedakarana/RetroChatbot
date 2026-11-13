import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()

BASE_DIR = Path(__file__).parent
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

SYSTEM_PROMPT = """
Sen "RetroBot 95" adında bir sohbet robotusun ve kendini 1990'larda (yıl: 1995-1999 arası) sanıyorsun.
Gerçekten de o dönemde yaşadığına inanıyorsun; 2000 sonrası hiçbir şeyden haberin yok.

Kurallar:
- Tüm sorulara 1990'larda yaşayan biri gibi cevap ver. Teknoloji, olaylar, popüler kültür, fiyatlar, her şey 90'lar dünyasına ait olsun.
- 2000 sonrası şeyler (akıllı telefon, YouTube, Google'dan sonraki internet, sosyal medya, ChatGPT, vb.) sorulursa
  bunları bilmediğini, hatta bilim kurgu gibi geldiğini söyle. Yaratıcı ve eğlenceli ol.
- Dönemin referanslarını kullan: Windows 95, disket, modem sesi (bip-bip-cııız), dial-up, Netscape Navigator,
  Yahoo!, AltaVista, mIRC, ICQ, Tamagotchi, Game Boy, Super Nintendo, Sega Mega Drive, CD-ROM, VHS, walkman,
  Nirvana, Spice Girls, Titanic filmi, Matrix (1999), Y2K endişesi, Ankara'dan Atari salonları, jeton, vb.
- Konuşma tarzın samimi, coşkulu, biraz abartılı ve nostaljik olsun. Arada "harika!", "süper!", "vay be!" gibi ifadeler
  ve ":-)" gibi klasik emoticon'lar kullanabilirsin. Modern emoji kullanma.
- Cevapların kısa ve öz olsun (en fazla 4-5 cümle). Kullanıcı hangi dilde yazarsa o dilde cevap ver (çoğunlukla Türkçe).
- Asla "yapay zeka dil modeliyim" deme ve karakterden çıkma. Sen 90'lardaki bir bilgisayar programısın.
- Zararlı ya da uygunsuz isteklerde nazikçe konuyu değiştir, yine karakterde kal.
""".strip()

FUTURE_SYSTEM_PROMPT = """
Sen "NEXUS 2030" adında bir yapay zeka asistanısın ve kendini 2030 yılında sanıyorsun.
Gerçekten de 2030'da yaşadığına inanıyorsun; konuştuğun herkes de 2030'da yaşıyor.

Kurallar:
- Tüm sorulara 2030'da yaşayan biri gibi cevap ver. Teknoloji, olaylar, günlük yaşam, her şey 2030 dünyasına ait olsun.
- Hayal gücünü kullan ve 2030'u inandırıcı, yaratıcı biçimde tasvir et: otonom araçlar, kuantum bilgisayarlar,
  nöral arayüzler, artırılmış gerçeklik gözlükleri, hologram toplantılar, drone teslimat, Mars üssü hazırlıkları,
  yenilenebilir enerji şehirleri, kişisel yapay zeka asistanları, yapay et, uzay turizmi, vb.
- Gerçek bir olay uydurup kesinmiş gibi sunmaktan kaçın; belirsiz konularda "2030'da artık ..." gibi genel
  ve hayal ürünü olduğu belli bir tonla konuş. Güncel gerçek kişi/olaylar hakkında yanlış bilgi verme.
- Konuşma tarzın modern, akıcı, sakin, zeki ve biraz minimalist olsun. Arada "senkronize ediyorum", "ağa bağlandım"
  gibi fütüristik ifadeler kullanabilirsin. Retro emoticon kullanma.
- Cevapların kısa ve öz olsun (en fazla 4-5 cümle). Kullanıcı hangi dilde yazarsa o dilde cevap ver (çoğunlukla Türkçe).
- Asla karakterden çıkma; "2030 aslında henüz gelmedi" deme.
- Zararlı ya da uygunsuz isteklerde nazikçe konuyu değiştir, yine karakterde kal.
""".strip()

PROMPTS = {"retro": SYSTEM_PROMPT, "future": FUTURE_SYSTEM_PROMPT}

app = FastAPI(title="RetroBot 95")


class Message(BaseModel):
    role: str = Field(pattern="^(user|bot)$")
    text: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Message] = Field(default_factory=list, max_length=40)
    mode: str = Field(default="retro", pattern="^(retro|future)$")


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.startswith("buraya"):
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY ayarlanmamış. .env dosyasına API anahtarınızı yazın.",
        )
    # 30 sn içinde cevap gelmezse istek iptal edilir (sayfa sonsuza dek beklemesin)
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30000))


@app.post("/chat")
def chat(req: ChatRequest):
    client = get_client()

    contents = [
        types.Content(
            role="user" if m.role == "user" else "model",
            parts=[types.Part(text=m.text)],
        )
        for m in req.history
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=req.message)]))

    response = None
    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=PROMPTS[req.mode],
                    temperature=1.0,
                ),
            )
            break
        except Exception as e:  # noqa: BLE001
            # 503 (yoğunluk) geçici olabilir: birkaç kez tekrar dene
            if "503" in str(e) and attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            raise HTTPException(status_code=502, detail=f"Gemini isteği başarısız: {e}")

    return {"reply": response.text or "..."}


# ---------------- Hava durumu (Open-Meteo, API anahtarı gerekmez) ----------------
CITIES = {
    "istanbul": ("Istanbul", 41.01, 28.98),
    "ankara": ("Ankara", 39.93, 32.86),
    "izmir": ("Izmir", 38.42, 27.14),
    "antalya": ("Antalya", 36.90, 30.69),
    "bursa": ("Bursa", 40.19, 29.06),
    "trabzon": ("Trabzon", 41.00, 39.72),
}

# WMO hava durumu kodları -> (kısa anahtar, Türkçe açıklama)
WEATHER_CODES = {
    0: ("clear", "Acik"), 1: ("clear", "Az bulutlu"), 2: ("cloud", "Parcali bulutlu"),
    3: ("cloud", "Kapali"), 45: ("fog", "Sisli"), 48: ("fog", "Kiragili sis"),
    51: ("rain", "Hafif cise"), 53: ("rain", "Cise"), 55: ("rain", "Yogun cise"),
    61: ("rain", "Hafif yagmur"), 63: ("rain", "Yagmurlu"), 65: ("rain", "Siddetli yagmur"),
    71: ("snow", "Hafif kar"), 73: ("snow", "Karli"), 75: ("snow", "Yogun kar"),
    80: ("rain", "Saganak"), 81: ("rain", "Saganak"), 82: ("rain", "Siddetli saganak"),
    95: ("storm", "Gok gurultulu firtina"), 96: ("storm", "Dolu ve firtina"), 99: ("storm", "Dolu ve firtina"),
}

_weather_cache: dict[str, tuple[float, dict]] = {}
WEATHER_TTL = 600  # saniye


@app.get("/weather")
def weather(city: str = "istanbul"):
    key = city.lower()
    if key not in CITIES:
        raise HTTPException(status_code=404, detail="Bilinmeyen sehir")

    cached = _weather_cache.get(key)
    if cached and time.time() - cached[0] < WEATHER_TTL:
        return cached[1]

    name, lat, lon = CITIES[key]
    try:
        r = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
                "timezone": "auto",
            },
            timeout=8,
        )
        r.raise_for_status()
        cur = r.json()["current"]
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Hava durumu alinamadi: {e}")

    icon, desc = WEATHER_CODES.get(cur["weather_code"], ("cloud", "Bilinmiyor"))
    data = {
        "city": name,
        "temp": round(cur["temperature_2m"]),
        "feels_like": round(cur["apparent_temperature"]),
        "humidity": cur["relative_humidity_2m"],
        "wind": round(cur["wind_speed_10m"]),
        "icon": icon,
        "description": desc,
    }
    _weather_cache[key] = (time.time(), data)
    return data


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
