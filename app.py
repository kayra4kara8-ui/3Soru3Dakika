"""
🎙️ 3 Soru 3 Dakika - Çok Sesli Podcast Oluşturucu
Kendi klonlanmış sesinizle profesyonel podcast'ler oluşturun.
"""

import streamlit as st
import requests
import time
import json
import io
from typing import Optional

# ============================================================
# 1. KONFİGÜRASYON BÖLÜMÜ - Buradan kolayca düzenleyin!
# ============================================================

CHARACTERS = {
    "Sunucu":    {"color": "#E74C3C", "emoji": "🎤"},
    "Konuk":     {"color": "#3498DB", "emoji": "👤"},
    "Dış Ses":   {"color": "#2ECC71", "emoji": "🎧"},
    # --- İsteğe bağlı ek karakterler (yorum satırını kaldırın veya yenilerini ekleyin) ---
    "Uzman":     {"color": "#F39C12", "emoji": "👨‍🏫"},
    "Raportör":  {"color": "#9B59B6", "emoji": "📰"},
    "Anlatıcı":  {"color": "#1ABC9C", "emoji": "📖"},
    "Çocuk":     {"color": "#E91E63", "emoji": "🧒"},
}

# Ses ID'leri - ElevenLabs'dan aldığınız voice_id değerlerini girin.
# Hepsine aynı ID'yi girebilirsiniz (kendi klonlanmış sesiniz) veya farklı sesler atayabilirsiniz.
VOICE_IDS = {
    "Sunucu":    "KENDI_SES_ID_BURAYA",
    "Konuk":     "KENDI_SES_ID_BURAYA",
    "Dış Ses":   "KENDI_SES_ID_BURAYA",
    "Uzman":     "KENDI_SES_ID_BURAYA",
    "Raportör":  "KENDI_SES_ID_BURAYA",
    "Anlatıcı":  "KENDI_SES_ID_BURAYA",
    "Çocuk":     "KENDI_SES_ID_BURAYA",
}

# Dinamik renk paleti - bilinmeyen karakterlere otomatik renk atanır
FALLBACK_COLORS = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
    "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F",
    "#BB8FCE", "#82E0AA",
]

# Hazır şablonlar
TEMPLATES = {
    "🎤 Röportaj": """Sunucu: Merhaba dinleyiciler! Bugün çok özel bir konuğumuz var. Hoş geldiniz!
Konuk: Merhaba! Burada olmaktan gerçekten mutluyum.
Dış Ses: Bu röportaj öncesinde konuğumuzun son kitabı büyük yankı uyandırdı.
Sunucu: Peki, bize bu projeyi nasıl anlattınız?
Konuk: Her şey küçük bir fikirle başladı. İlk adımlar zordu ama...
Dış Ses: Bu noktada konuğumuz kısa bir duraksamayla devam etti.
Sunucu: Ve o an nasıl hissettiniz?
Konuk: İnanılmaz bir motivasyon kaynağı bulmuştum. Her şey değişti.
Sunucu: Harika bir yolculuk! Dinleyicilerimize son bir mesajınız?
Konuk: Hayallerinizin peşinden gidin. Yol uzun ama değer.
Dış Ses: Bizi dinlediğiniz için teşekkürler. Bir sonraki bölümde görüşmek üzere!""",

    "📰 Haber": """Dış Ses: 3 Soru 3 Dakika haber bültenine hoş geldiniz.
Sunucu: Bugünün öne çıkan haberleriyle başlıyoruz.
Raportör: Teknoloji dünyasından gelişmeler var. Yapay zeka kullanımı rekor kırdı.
Sunucu: Bu gelişme sektörü nasıl etkiliyor?
Uzman: Verimlilik artışı gözle görülür bir seviyeye ulaştı. Rakamlar çarpıcı.
Raportör: İstatistiklere göre son bir yılda kullanım oranı yüzde iki yüz arttı.
Sunucu: Peki önümüzdeki dönemde ne bekleyebiliriz?
Uzman: Entegrasyon süreçleri hızlanacak. İş dünyası adapte olmak zorunda.
Dış Ses: Haberleri takip etmeye devam edin. Yarın görüşmek üzere!""",

    "📚 Eğitim": """Sunucu: Bilim dünyasına hoş geldiniz! Bugün çok ilginç bir konu var.
Dış Ses: Bu bölümde kuantum fiziğinin temellerini ele alacağız.
Konuk: Kuantum fiziği, atom altı parçacıkların davranışını inceler.
Sunucu: Peki bu bizim günlük hayatımızı nasıl etkiliyor?
Uzman: Akıllı telefonunuzdan tıbbi görüntülemeye kadar her yerde kuantum var.
Konuk: En ilgi çekici konu süperpozisyon ilkesi. Parçacık aynı anda iki yerde olabilir.
Sunucu: Bu nasıl mümkün olabiliyor?
Uzman: Ölçüm yapana kadar sistem belirsizliğini korur. Schrödinger'in kedisi tam bunu anlatır.
Dış Ses: Bir sonraki bölümde kuantum dolanıklığını inceleyeceğiz. Takipte kalın!""",

    "📖 Hikaye": """Anlatıcı: Karanlık ve fırtınalı bir geceydi. Şehir uyurken o uyumuyordu.
Sunucu: Dedektif Mara, masasında oturmuş dosyalara bakıyordu.
Konuk: Bu dava diğerlerine benzemiyordu. Bir şeyler tutarsızdı.
Anlatıcı: Tam o sırada telefon çaldı. Karşıdaki ses tanıdıktı.
Sunucu: Kim arıyordu beni bu gece?
Konuk: Sesi titriyordu. "Yardıma ihtiyacım var" dedi yalnızca.
Anlatıcı: Mara ayağa kalktı. Görev çağrısı beklemezdi.
Sunucu: Adresi al, yola çık. Soru sormanın zamanı değil.
Anlatıcı: Ve böylece en büyük davası başlamış oldu...""",
}


# ============================================================
# 2. SINIFLAR
# ============================================================

class ScriptParser:
    """Podcast metnini parse eder ve segmentlere ayırır."""

    def __init__(self, characters: dict):
        self.characters = characters
        self._dynamic_colors = {}
        self._color_idx = 0

    def _get_color_for_unknown(self, char_name: str) -> str:
        if char_name not in self._dynamic_colors:
            color = FALLBACK_COLORS[self._color_idx % len(FALLBACK_COLORS)]
            self._dynamic_colors[char_name] = color
            self._color_idx += 1
        return self._dynamic_colors[char_name]

    def parse(self, script: str) -> list[dict]:
        segments = []
        lines = script.strip().split('\n')
        current_char = None
        current_text_parts = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if ':' in line:
                colon_pos = line.index(':')
                potential_char = line[:colon_pos].strip()
                rest = line[colon_pos + 1:].strip()
                # Karakter ismi mi yoksa metin içi iki nokta mı?
                if len(potential_char) > 0 and len(potential_char) <= 30 and not any(c in potential_char for c in ['!', '?', '.', ',']):
                    # Önceki segmenti kaydet
                    if current_char and current_text_parts:
                        segments.append(self._build_segment(current_char, ' '.join(current_text_parts)))
                    current_char = potential_char
                    current_text_parts = [rest] if rest else []
                    continue
            # Devam satırı
            if current_char:
                current_text_parts.append(line)
            else:
                # Karakter tanımlanmamış → Sunucu'ya ata
                default = list(self.characters.keys())[0] if self.characters else "Sunucu"
                current_char = default
                current_text_parts = [line]

        if current_char and current_text_parts:
            segments.append(self._build_segment(current_char, ' '.join(current_text_parts)))

        return segments

    def _build_segment(self, char_name: str, text: str) -> dict:
        if char_name in self.characters:
            info = self.characters[char_name]
            color = info["color"]
            emoji = info["emoji"]
        else:
            color = self._get_color_for_unknown(char_name)
            emoji = "🔊"
        return {"character": char_name, "text": text, "color": color, "emoji": emoji}

    @staticmethod
    def count_words(script: str) -> int:
        return len(script.split())

    @staticmethod
    def estimate_duration(word_count: int) -> str:
        # Ortalama konuşma hızı ~130 kelime/dk
        minutes = word_count / 130
        secs = int((minutes % 1) * 60)
        mins = int(minutes)
        return f"{mins}:{secs:02d}"


class ElevenLabsAPI:
    """ElevenLabs TTS API ile iletişim kurar."""

    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"xi-api-key": api_key}

    def test_connection(self) -> tuple[bool, str]:
        try:
            r = requests.get(f"{self.BASE_URL}/user", headers=self.headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                name = data.get("first_name", "Kullanıcı")
                chars = data.get("subscription", {}).get("character_count", "?")
                limit = data.get("subscription", {}).get("character_limit", "?")
                return True, f"✅ Hoş geldin, {name}! Karakter: {chars}/{limit}"
            return False, f"❌ Hata {r.status_code}: {r.text[:100]}"
        except Exception as e:
            return False, f"❌ Bağlantı hatası: {str(e)}"

    def list_voices(self) -> list[dict]:
        try:
            r = requests.get(f"{self.BASE_URL}/voices", headers=self.headers, timeout=10)
            if r.status_code == 200:
                return r.json().get("voices", [])
        except Exception:
            pass
        return []

    def validate_voice_id(self, voice_id: str) -> bool:
        if not voice_id or voice_id in ("KENDI_SES_ID_BURAYA", ""):
            return False
        try:
            r = requests.get(f"{self.BASE_URL}/voices/{voice_id}", headers=self.headers, timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    def text_to_speech(self, text: str, voice_id: str, stability: float = 0.5, similarity: float = 0.75) -> Optional[bytes]:
        url = f"{self.BASE_URL}/text-to-speech/{voice_id}"
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity,
            }
        }
        try:
            r = requests.post(url, headers={**self.headers, "Content-Type": "application/json"},
                              json=payload, timeout=60)
            if r.status_code == 200:
                return r.content
            st.warning(f"API hatası {r.status_code}: {r.text[:150]}")
        except Exception as e:
            st.error(f"İstek hatası: {str(e)}")
        return None


class UIComponents:
    """Streamlit UI bileşenlerini yönetir."""

    @staticmethod
    def inject_css():
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

        html, body, [class*="css"] {
            font-family: 'Sora', sans-serif;
        }

        .stApp {
            background: linear-gradient(135deg, #0a0a0f 0%, #12121f 40%, #0d1117 100%);
            color: #e8e8f0;
        }

        /* Header */
        .main-header {
            text-align: center;
            padding: 2.5rem 1rem 1.5rem;
        }
        .main-header h1 {
            font-size: 2.8rem;
            font-weight: 800;
            background: linear-gradient(90deg, #E74C3C, #FF6B6B, #3498DB, #2ECC71);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: -1px;
            margin-bottom: 0.3rem;
        }
        .main-header p {
            color: #888;
            font-size: 0.95rem;
            letter-spacing: 0.05em;
        }

        /* Segment card */
        .segment-card {
            border-radius: 14px;
            padding: 1rem 1.2rem;
            margin: 0.6rem 0;
            border-left: 4px solid;
            background: rgba(255,255,255,0.04);
            backdrop-filter: blur(8px);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .segment-card:hover {
            transform: translateX(4px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        }
        .segment-char {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }
        .segment-text {
            font-size: 0.95rem;
            line-height: 1.65;
            color: #dde;
        }

        /* Stats bar */
        .stats-bar {
            display: flex;
            gap: 1.5rem;
            padding: 0.8rem 1.2rem;
            background: rgba(255,255,255,0.04);
            border-radius: 10px;
            margin-bottom: 1rem;
            font-size: 0.82rem;
            color: #aaa;
        }
        .stat-item strong {
            color: #eee;
        }

        /* Voice badge */
        .voice-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.3rem 0.75rem;
            border-radius: 50px;
            font-size: 0.75rem;
            font-weight: 600;
            margin: 0.2rem 0.2rem 0.2rem 0;
        }
        .voice-ok   { background: rgba(46,204,113,0.15); color: #2ECC71; border: 1px solid rgba(46,204,113,0.3); }
        .voice-warn { background: rgba(231,76,60,0.15);  color: #E74C3C;  border: 1px solid rgba(231,76,60,0.3);  }

        /* Template button override */
        div[data-testid="stButton"] button {
            border-radius: 8px;
            font-family: 'Sora', sans-serif;
            font-size: 0.82rem;
            transition: all 0.2s;
        }

        /* Progress */
        .stProgress > div > div { border-radius: 10px; }

        /* Sidebar */
        section[data-testid="stSidebar"] {
            background: rgba(10,10,20,0.95);
            border-right: 1px solid rgba(255,255,255,0.06);
        }

        /* Audio player */
        audio { width: 100%; border-radius: 8px; margin: 4px 0; }

        /* Text area */
        textarea {
            background: rgba(255,255,255,0.04) !important;
            border-radius: 10px !important;
            color: #eee !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 0.85rem !important;
        }

        /* Divider */
        hr { border-color: rgba(255,255,255,0.07); }

        .section-title {
            font-size: 0.7rem;
            letter-spacing: 0.15em;
            text-transform: uppercase;
            color: #666;
            margin: 1rem 0 0.5rem;
        }

        .pulse {
            animation: pulse 1.4s ease-in-out infinite;
        }
        @keyframes pulse {
            0%,100% { opacity: 1; }
            50%      { opacity: 0.45; }
        }
        </style>
        """, unsafe_allow_html=True)

    @staticmethod
    def render_segment_card(seg: dict, idx: int):
        color = seg["color"]
        st.markdown(f"""
        <div class="segment-card" style="border-color:{color};">
            <div class="segment-char" style="color:{color};">{seg['emoji']} {seg['character']}</div>
            <div class="segment-text">{seg['text']}</div>
        </div>
        """, unsafe_allow_html=True)

    @staticmethod
    def render_voice_status(voice_ids: dict, api: Optional["ElevenLabsAPI"] = None):
        st.markdown('<p class="section-title">🔊 Ses Durumu</p>', unsafe_allow_html=True)
        cols = st.columns(3)
        i = 0
        for char, vid in voice_ids.items():
            if char not in CHARACTERS:
                continue
            is_ok = bool(vid and vid not in ("KENDI_SES_ID_BURAYA", ""))
            cls = "voice-ok" if is_ok else "voice-warn"
            icon = "✓" if is_ok else "✗"
            info = CHARACTERS[char]
            with cols[i % 3]:
                st.markdown(f"""
                <span class="voice-badge {cls}">{info['emoji']} {char} {icon}</span>
                """, unsafe_allow_html=True)
            i += 1


# ============================================================
# 3. ANA UYGULAMA
# ============================================================

def init_session_state():
    defaults = {
        "audio_segments": [],
        "podcast_history": [],
        "parsed_segments": [],
        "full_audio": None,
        "api_connected": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def render_sidebar() -> tuple[Optional[ElevenLabsAPI], float, float]:
    with st.sidebar:
        st.markdown("### 🎙️ 3 Soru 3 Dakika")
        st.markdown("---")

        st.markdown('<p class="section-title">🔑 API Bağlantısı</p>', unsafe_allow_html=True)
        api_key = st.text_input("ElevenLabs API Key", type="password", placeholder="xi-...")

        api = None
        if api_key:
            if st.button("🔌 Bağlan", use_container_width=True):
                with st.spinner("Bağlanıyor..."):
                    api = ElevenLabsAPI(api_key)
                    ok, msg = api.test_connection()
                    st.session_state.api_connected = ok
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                        api = None
            if st.session_state.api_connected:
                api = ElevenLabsAPI(api_key)

        st.markdown("---")
        st.markdown('<p class="section-title">⚙️ Ses Ayarları</p>', unsafe_allow_html=True)
        stability  = st.slider("Kararlılık", 0.0, 1.0, 0.5, 0.05)
        similarity = st.slider("Benzerlik Güçlendirme", 0.0, 1.0, 0.75, 0.05)

        st.markdown("---")
        st.markdown('<p class="section-title">📋 Karakterler</p>', unsafe_allow_html=True)
        for char, info in CHARACTERS.items():
            vid = VOICE_IDS.get(char, "")
            is_set = bool(vid and vid not in ("KENDI_SES_ID_BURAYA", ""))
            dot = "🟢" if is_set else "🔴"
            st.markdown(f"{dot} {info['emoji']} **{char}**")

        if api and st.button("🎧 Sesleri Listele", use_container_width=True):
            with st.spinner("Yükleniyor..."):
                voices = api.list_voices()
                if voices:
                    st.markdown("**Mevcut Sesler:**")
                    for v in voices[:10]:
                        st.code(f"{v['name']}: {v['voice_id']}", language=None)
                else:
                    st.info("Ses bulunamadı veya API hatası.")

        st.markdown("---")
        st.caption("v1.0.0 | ElevenLabs TTS")

    return api, stability, similarity


def generate_podcast(segments: list[dict], api: ElevenLabsAPI,
                     stability: float, similarity: float) -> list[dict]:
    """Her segment için ses üretir."""
    audio_segments = []
    total = len(segments)

    progress_bar = st.progress(0, text="Hazırlanıyor...")
    status_placeholder = st.empty()

    for i, seg in enumerate(segments):
        char = seg["character"]
        voice_id = VOICE_IDS.get(char)

        if not voice_id or voice_id in ("KENDI_SES_ID_BURAYA", ""):
            status_placeholder.warning(f"⚠️ {char} için ses ID tanımlanmamış, atlanıyor.")
            audio_segments.append({**seg, "audio": None, "skipped": True})
        else:
            status_placeholder.markdown(
                f'<span class="pulse">🎙️ {seg["emoji"]} {char} seslendiriliyor... ({i+1}/{total})</span>',
                unsafe_allow_html=True
            )
            audio_data = api.text_to_speech(seg["text"], voice_id, stability, similarity)
            audio_segments.append({**seg, "audio": audio_data, "skipped": False})
            time.sleep(0.5)  # Rate limiting

        progress_bar.progress((i + 1) / total, text=f"{i+1}/{total} segment tamamlandı")

    status_placeholder.success(f"✅ {total} segmentin seslendirmesi tamamlandı!")
    return audio_segments


def combine_audio(audio_segments: list[dict]) -> Optional[bytes]:
    """Tüm ses parçalarını birleştirir (ham MP3 bytes concat)."""
    combined = b""
    for seg in audio_segments:
        if seg.get("audio"):
            combined += seg["audio"]
    return combined if combined else None


def main():
    st.set_page_config(
        page_title="3 Soru 3 Dakika",
        page_icon="🎙️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    UIComponents.inject_css()
    init_session_state()

    # Sidebar
    api, stability, similarity = render_sidebar()

    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🎙️ 3 Soru 3 Dakika</h1>
        <p>Kendi klonlanmış sesinizle çok karakterli podcast oluşturun</p>
    </div>
    """, unsafe_allow_html=True)

    # Ana layout
    col_left, col_right = st.columns([1, 1], gap="large")

    # ── SOL PANEL: Metin Girişi ──
    with col_left:
        st.markdown('<p class="section-title">📝 Senaryo</p>', unsafe_allow_html=True)

        # Şablonlar
        st.markdown('<p class="section-title">📂 Hazır Şablonlar</p>', unsafe_allow_html=True)
        t_cols = st.columns(2)
        for idx, (label, content) in enumerate(TEMPLATES.items()):
            with t_cols[idx % 2]:
                if st.button(label, use_container_width=True):
                    st.session_state["template_text"] = content

        script_value = st.session_state.get("template_text", "")
        script = st.text_area(
            "Senaryo Metni",
            value=script_value,
            height=400,
            placeholder="Sunucu: Merhaba!\nKonuk: Merhaba!\nDış Ses: Bugünkü konu...",
            label_visibility="collapsed",
        )

        # İstatistikler
        if script.strip():
            word_count = ScriptParser.count_words(script)
            duration   = ScriptParser.estimate_duration(word_count)
            parser     = ScriptParser(CHARACTERS)
            segs       = parser.parse(script)
            chars_used = list({s["character"] for s in segs})

            st.markdown(f"""
            <div class="stats-bar">
                <div class="stat-item">📊 <strong>{word_count}</strong> kelime</div>
                <div class="stat-item">⏱️ ~<strong>{duration}</strong></div>
                <div class="stat-item">👥 <strong>{len(segs)}</strong> satır</div>
                <div class="stat-item">🎭 <strong>{len(chars_used)}</strong> karakter</div>
            </div>
            """, unsafe_allow_html=True)

            # Ön izleme
            st.markdown('<p class="section-title">👁️ Önizleme</p>', unsafe_allow_html=True)
            for i, seg in enumerate(segs):
                UIComponents.render_segment_card(seg, i)

    # ── SAĞ PANEL: Çıktı ──
    with col_right:
        st.markdown('<p class="section-title">🎧 Podcast Çıktısı</p>', unsafe_allow_html=True)

        # Ses durumu
        UIComponents.render_voice_status(VOICE_IDS, api)

        st.markdown("---")

        btn_col1, btn_col2 = st.columns(2)
        generate_btn = btn_col1.button("🚀 Podcast Oluştur", use_container_width=True, type="primary")
        clear_btn    = btn_col2.button("🗑️ Temizle", use_container_width=True)

        if clear_btn:
            st.session_state.audio_segments = []
            st.session_state.full_audio = None
            st.session_state.parsed_segments = []
            if "template_text" in st.session_state:
                del st.session_state["template_text"]
            st.rerun()

        if generate_btn:
            if not api:
                st.error("❌ Lütfen önce ElevenLabs API anahtarınızı girin ve bağlanın.")
            elif not script.strip():
                st.warning("⚠️ Senaryo metni boş. Lütfen bir metin girin.")
            else:
                parser = ScriptParser(CHARACTERS)
                segs   = parser.parse(script)
                st.session_state.parsed_segments = segs

                # Geçerli voice ID kontrolü
                valid_chars = [
                    s["character"] for s in segs
                    if VOICE_IDS.get(s["character"], "") not in ("KENDI_SES_ID_BURAYA", "")
                ]
                if not valid_chars:
                    st.error("❌ Hiçbir karakter için geçerli ses ID tanımlanmamış. Lütfen VOICE_IDS bölümünü güncelleyin.")
                else:
                    with st.container():
                        audio_segs = generate_podcast(segs, api, stability, similarity)
                        st.session_state.audio_segments = audio_segs
                        combined = combine_audio(audio_segs)
                        st.session_state.full_audio = combined

                        # Geçmişe ekle
                        preview = script[:60] + "..." if len(script) > 60 else script
                        st.session_state.podcast_history.append({
                            "preview": preview,
                            "segment_count": len(segs),
                        })

        # Ses segmentleri
        if st.session_state.audio_segments:
            st.markdown("---")
            st.markdown('<p class="section-title">🎵 Ses Segmentleri</p>', unsafe_allow_html=True)

            for i, seg in enumerate(st.session_state.audio_segments):
                with st.expander(f"{seg['emoji']} {seg['character']}: {seg['text'][:50]}...", expanded=False):
                    if seg.get("audio"):
                        st.audio(seg["audio"], format="audio/mp3")
                    else:
                        st.caption("⚠️ Bu segment için ses üretilemedi.")

            # Tam podcast
            if st.session_state.full_audio:
                st.markdown("---")
                st.markdown('<p class="section-title">📥 Tam Podcast</p>', unsafe_allow_html=True)
                st.audio(st.session_state.full_audio, format="audio/mp3")
                st.download_button(
                    label="⬇️ MP3 İndir",
                    data=st.session_state.full_audio,
                    file_name="podcast.mp3",
                    mime="audio/mpeg",
                    use_container_width=True,
                )

        # Geçmiş
        if st.session_state.podcast_history:
            st.markdown("---")
            st.markdown('<p class="section-title">📜 Podcast Geçmişi</p>', unsafe_allow_html=True)
            for h in reversed(st.session_state.podcast_history[-5:]):
                st.markdown(f"🎙️ *{h['preview']}* — {h['segment_count']} satır")


if __name__ == "__main__":
    main()
