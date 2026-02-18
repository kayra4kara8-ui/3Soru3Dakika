"""
3 SORU 3 DAKİKA - PROFESYONEL PODCAST OLUŞTURUCU
ElevenLabs API ile çok sesli podcast oluşturma uygulaması
Version: 2.0.0
"""

import streamlit as st
import requests
import json
import time
import base64
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sayfa yapılandırması - TEK VE EN BAŞTA
st.set_page_config(
    page_title="3 Soru 3 Dakika | Profesyonel Podcast Studio",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# SABITLER VE KONFIGÜRASYON
# ============================================================================

class Config:
    """Uygulama konfigürasyonu"""
    
    # ElevenLabs ses kimlikleri (profesyonel sesler)
    VOICE_IDS = {
        "Sunucu": "21m00Tcm4TlvDq8ikWAM",      # Rachel - Profesyonel sunucu
        "Konuk": "AZnzlk1XvdvUeBnXmlld",        # Adam - Doğal konuşma
        "Dış Ses": "EXAVITQu4vr4xnSDxMaL",      # Bella - Anons sesi
        "Uzman": "TxGEqnHWrfWFTfGW9XjX",        # Josh - Uzman sesi
        "Raportör": "XpPJqWX8T7Fir3jRqU6H"      # Nicole - Haber spikeri
    }
    
    # Karakter renkleri ve stilleri
    CHARACTERS = {
        "Sunucu": {
            "color": "#E74C3C",
            "emoji": "🎤",
            "bg": "#E74C3C15",
            "description": "Profesyonel sunucu"
        },
        "Konuk": {
            "color": "#3498DB",
            "emoji": "👤",
            "bg": "#3498DB15",
            "description": "Doğal konuşmacı"
        },
        "Dış Ses": {
            "color": "#2ECC71",
            "emoji": "🎧",
            "bg": "#2ECC7115",
            "description": "Anons sesi"
        },
        "Uzman": {
            "color": "#F39C12",
            "emoji": "👨‍🏫",
            "bg": "#F39C1215",
            "description": "Uzman görüşü"
        },
        "Raportör": {
            "color": "#9B59B6",
            "emoji": "📰",
            "bg": "#9B59B615",
            "description": "Haber spikeri"
        }
    }
    
    # API endpoint'leri
    ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
    
    # Rate limiting
    REQUEST_DELAY = 0.5  # saniye
    
    # Maksimum metin uzunluğu
    MAX_TEXT_LENGTH = 5000

# ============================================================================
# SESSION STATE YÖNETİMİ
# ============================================================================

def init_session_state():
    """Session state değişkenlerini başlat"""
    
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        st.session_state.podcast_history = []
        st.session_state.current_audio = None
        st.session_state.current_script = None
        st.session_state.generated_segments = []
        st.session_state.api_key_valid = False
        st.session_state.error_count = 0
        st.session_state.success_count = 0
        st.session_state.last_error = None
        st.session_state.processing = False

# ============================================================================
# METİN İŞLEME
# ============================================================================

class ScriptParser:
    """Podcast metnini parse eden sınıf"""
    
    @staticmethod
    def parse(text: str) -> List[Dict]:
        """
        Metni parse ederek karakter ve metinleri çıkarır
        
        Args:
            text: Ham metin
            
        Returns:
            List[Dict]: Parse edilmiş satırlar
        """
        if not text or not text.strip():
            return []
        
        lines = text.strip().split('\n')
        parsed_lines = []
        current_line = None
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            # Karakter kontrolü
            character_found = False
            for char in Config.CHARACTERS.keys():
                if line.startswith(f"{char}:"):
                    # Yeni karakter satırı
                    text_content = line[len(char)+1:].strip()
                    if text_content:
                        parsed_lines.append({
                            'character': char,
                            'text': text_content,
                            'line_number': line_num,
                            'voice_id': Config.VOICE_IDS.get(char, Config.VOICE_IDS["Sunucu"])
                        })
                        current_line = parsed_lines[-1]
                    character_found = True
                    break
            
            # Karakter bulunamadıysa önceki satıra ekle
            if not character_found and current_line:
                current_line['text'] += " " + line
            elif not character_found and not current_line:
                # İlk satır karakter yoksa Sunucu'ya ata
                parsed_lines.append({
                    'character': "Sunucu",
                    'text': line,
                    'line_number': line_num,
                    'voice_id': Config.VOICE_IDS["Sunucu"]
                })
                current_line = parsed_lines[-1]
        
        return parsed_lines
    
    @staticmethod
    def validate(parsed_lines: List[Dict]) -> Tuple[bool, str]:
        """
        Parse edilmiş metni validate eder
        
        Args:
            parsed_lines: Parse edilmiş satırlar
            
        Returns:
            Tuple[bool, str]: (geçerli mi, hata mesajı)
        """
        if not parsed_lines:
            return False, "Metin boş olamaz"
        
        total_chars = sum(len(line['text']) for line in parsed_lines)
        if total_chars > Config.MAX_TEXT_LENGTH:
            return False, f"Metin çok uzun (max: {Config.MAX_TEXT_LENGTH} karakter)"
        
        for line in parsed_lines:
            if len(line['text']) > 500:
                return False, f"Satır çok uzun (max: 500 karakter): {line['text'][:50]}..."
        
        return True, "OK"

# ============================================================================
# ELEVENLABS API İŞLEMLERİ
# ============================================================================

class ElevenLabsAPI:
    """ElevenLabs API ile etkileşim"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        })
    
    def text_to_speech(
        self, 
        text: str, 
        voice_id: str,
        stability: float = 0.5,
        similarity: float = 0.75
    ) -> Optional[bytes]:
        """
        Metni sese çevir
        
        Args:
            text: Metin
            voice_id: Ses kimliği
            stability: Stabilite (0-1)
            similarity: Benzerlik (0-1)
            
        Returns:
            Optional[bytes]: Ses dosyası veya None
        """
        url = f"{Config.ELEVENLABS_API_URL}/text-to-speech/{voice_id}"
        
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity
            }
        }
        
        try:
            response = self.session.post(url, json=data, timeout=30)
            
            if response.status_code == 200:
                return response.content
            elif response.status_code == 401:
                raise Exception("Geçersiz API anahtarı")
            elif response.status_code == 429:
                raise Exception("Rate limit aşıldı, lütfen bekleyin")
            else:
                raise Exception(f"API hatası: {response.status_code}")
                
        except requests.exceptions.Timeout:
            raise Exception("İstek zaman aşımına uğradı")
        except requests.exceptions.ConnectionError:
            raise Exception("Bağlantı hatası")
        except Exception as e:
            raise Exception(f"Ses oluşturma hatası: {str(e)}")
    
    def get_voices(self) -> List[Dict]:
        """Kullanılabilir sesleri listele"""
        url = f"{Config.ELEVENLABS_API_URL}/voices"
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.json().get('voices', [])
            return []
        except:
            return []

# ============================================================================
# UI BİLEŞENLERİ
# ============================================================================

class UIComponents:
    """UI bileşenleri"""
    
    @staticmethod
    def character_card(character: str, text: str, is_active: bool = False):
        """Karakter kartı göster"""
        char_info = Config.CHARACTERS.get(character, {
            "color": "#95A5A6",
            "emoji": "🎙️",
            "bg": "#95A5A615"
        })
        
        active_style = """
            border-left: 5px solid #2C3E50;
            transform: translateX(5px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        """ if is_active else ""
        
        card_html = f"""
        <div style="
            padding: 15px;
            margin: 10px 0;
            background: {char_info['bg']};
            border-radius: 12px;
            border-left: 5px solid {char_info['color']};
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            transition: all 0.3s ease;
            {active_style}
        ">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                <span style="font-size: 1.3rem;">{char_info['emoji']}</span>
                <strong style="color: {char_info['color']}; font-size: 1.1rem;">
                    {character}
                </strong>
                <span style="
                    background: {char_info['color']};
                    color: white;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 0.7rem;
                    margin-left: auto;
                ">
                    {char_info['description']}
                </span>
            </div>
            <p style="margin: 0; color: #2C3E50; line-height: 1.6; font-size: 0.95rem;">
                {text}
            </p>
        </div>
        """
        
        return card_html
    
    @staticmethod
    def stats_card(title: str, value: str, icon: str, color: str):
        """İstatistik kartı göster"""
        card_html = f"""
        <div style="
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            text-align: center;
            border-bottom: 3px solid {color};
        ">
            <div style="font-size: 2rem; margin-bottom: 5px;">{icon}</div>
            <div style="color: #7F8C8D; font-size: 0.85rem; margin-bottom: 5px;">
                {title}
            </div>
            <div style="color: {color}; font-size: 1.5rem; font-weight: bold;">
                {value}
            </div>
        </div>
        """
        
        return card_html
    
    @staticmethod
    def progress_tracker(current: int, total: int, label: str = ""):
        """İlerleme takibi göster"""
        percentage = (current / total) * 100 if total > 0 else 0
        
        tracker_html = f"""
        <div style="margin: 15px 0;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span style="color: #2C3E50; font-weight: 500;">{label}</span>
                <span style="color: #7F8C8D;">{current}/{total}</span>
            </div>
            <div style="
                width: 100%;
                height: 8px;
                background: #ECF0F1;
                border-radius: 4px;
                overflow: hidden;
            ">
                <div style="
                    width: {percentage}%;
                    height: 100%;
                    background: linear-gradient(90deg, #3498DB, #9B59B6);
                    border-radius: 4px;
                    transition: width 0.3s ease;
                "></div>
            </div>
        </div>
        """
        
        return tracker_html

# ============================================================================
# ANA UYGULAMA
# ============================================================================

def main():
    """Ana uygulama fonksiyonu"""
    
    # Session state'i başlat
    init_session_state()
    
    # Custom CSS
    st.markdown("""
        <style>
        /* Ana container */
        .main > div {
            background: #FFFFFF;
            border-radius: 25px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.05);
        }
        
        /* Sidebar */
        .css-1d391kg {
            background: linear-gradient(180deg, #2C3E50 0%, #3498DB 100%);
        }
        
        /* Butonlar */
        .stButton > button {
            background: linear-gradient(90deg, #3498DB, #9B59B6);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 12px 24px;
            font-weight: 600;
            font-size: 1rem;
            transition: all 0.3s;
            width: 100%;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(52, 152, 219, 0.3);
        }
        
        .stButton > button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        /* Text area */
        .stTextArea textarea {
            border: 2px solid #ECF0F1;
            border-radius: 15px;
            font-size: 1rem;
            line-height: 1.6;
            transition: all 0.3s;
        }
        
        .stTextArea textarea:focus {
            border-color: #3498DB;
            box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
        }
        
        /* Info boxes */
        .success-box {
            background: #2ECC7115;
            border-left: 5px solid #2ECC71;
            padding: 20px;
            border-radius: 12px;
            margin: 15px 0;
        }
        
        .error-box {
            background: #E74C3C15;
            border-left: 5px solid #E74C3C;
            padding: 20px;
            border-radius: 12px;
            margin: 15px 0;
        }
        
        .warning-box {
            background: #F39C1215;
            border-left: 5px solid #F39C12;
            padding: 20px;
            border-radius: 12px;
            margin: 15px 0;
        }
        
        .info-box {
            background: #3498DB15;
            border-left: 5px solid #3498DB;
            padding: 20px;
            border-radius: 12px;
            margin: 15px 0;
        }
        
        /* Audio player */
        audio {
            width: 100%;
            border-radius: 30px;
            margin: 10px 0;
        }
        
        /* Metrics */
        .metric-container {
            background: white;
            border-radius: 15px;
            padding: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }
        
        /* Divider */
        .custom-divider {
            height: 2px;
            background: linear-gradient(90deg, transparent, #3498DB, transparent);
            margin: 30px 0;
        }
        
        /* Header */
        .app-header {
            text-align: center;
            padding: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 25px;
            margin-bottom: 30px;
            color: white;
        }
        
        .app-header h1 {
            font-size: 3rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        
        .app-header p {
            font-size: 1.2rem;
            opacity: 0.9;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
        <div class="app-header">
            <h1>🎙️ 3 SORU 3 DAKİKA</h1>
            <p>Profesyonel Yapay Zeka Podcast Stüdyosu</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("""
            <div style="
                background: rgba(255,255,255,0.1);
                padding: 20px;
                border-radius: 15px;
                margin-bottom: 20px;
                text-align: center;
            ">
                <h3 style="color: white; margin: 0;">⚙️ STUDIO KONTROL</h3>
            </div>
        """, unsafe_allow_html=True)
        
        # API Key girişi
        api_key = st.text_input(
            "🔑 ELEVENLABS API KEY",
            type="password",
            placeholder="sk_...",
            help="ElevenLabs API anahtarınızı girin"
        )
        
        if api_key:
            st.session_state.api_key_valid = True
            st.success("✅ API key doğrulandı")
        else:
            st.session_state.api_key_valid = False
            st.warning("⚠️ API key gerekli")
        
        st.markdown("<hr style='border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
        
        # Ses ayarları
        st.markdown("""
            <div style="
                background: rgba(255,255,255,0.05);
                padding: 15px;
                border-radius: 10px;
                margin-bottom: 15px;
            ">
                <h4 style="color: white; margin: 0;">🎤 SES AYARLARI</h4>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            stability = st.slider(
                "Stabilite",
                0.0, 1.0, 0.5,
                help="Düşük: dinamik | Yüksek: stabil"
            )
        with col2:
            similarity = st.slider(
                "Benzerlik",
                0.0, 1.0, 0.75,
                help="Orijinal sese benzerlik"
            )
        
        st.markdown("<hr style='border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
        
        # Karakter listesi
        st.markdown("""
            <div style="
                background: rgba(255,255,255,0.05);
                padding: 15px;
                border-radius: 10px;
                margin-bottom: 15px;
            ">
                <h4 style="color: white; margin: 0;">🎭 KARAKTERLER</h4>
            </div>
        """, unsafe_allow_html=True)
        
        for char, info in Config.CHARACTERS.items():
            st.markdown(f"""
                <div style="
                    background: {info['bg']};
                    padding: 8px 12px;
                    margin: 5px 0;
                    border-radius: 8px;
                    border-left: 3px solid {info['color']};
                ">
                    <span style="color: {info['color']};">{info['emoji']} {char}</span>
                    <span style="color: #BDC3C7; font-size: 0.8rem; float: right;">
                        {info['description']}
                    </span>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<hr style='border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
        
        # İstatistikler
        if st.session_state.success_count > 0 or st.session_state.error_count > 0:
            st.markdown("""
                <div style="
                    background: rgba(255,255,255,0.05);
                    padding: 15px;
                    border-radius: 10px;
                ">
                    <h4 style="color: white; margin: 0 0 10px 0;">📊 SİSTEM DURUMU</h4>
                </div>
            """, unsafe_allow_html=True)
            
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.markdown(f"""
                    <div style="text-align: center; background: #2ECC7115; padding: 10px; border-radius: 8px;">
                        <div style="color: #2ECC71; font-size: 1.5rem;">✓</div>
                        <div style="color: white;">{st.session_state.success_count}</div>
                    </div>
                """, unsafe_allow_html=True)
            with col_s2:
                st.markdown(f"""
                    <div style="text-align: center; background: #E74C3C15; padding: 10px; border-radius: 8px;">
                        <div style="color: #E74C3C; font-size: 1.5rem;">✗</div>
                        <div style="color: white;">{st.session_state.error_count}</div>
                    </div>
                """, unsafe_allow_html=True)
    
    # Ana içerik - 2 kolon
    col_left, col_right = st.columns([1, 1], gap="large")
    
    with col_left:
        st.markdown("""
            <div style="
                background: linear-gradient(90deg, #F8F9FA, #FFFFFF);
                padding: 20px;
                border-radius: 20px;
                margin-bottom: 20px;
            ">
                <h2 style="margin: 0; color: #2C3E50;">
                    📝 SENARYO DÜZENLEYİCİ
                </h2>
            </div>
        """, unsafe_allow_html=True)
        
        # Şablon seçici
        template = st.selectbox(
            "Hazır Şablon Seçin",
            ["Boş", "Röportaj", "Haber Bülteni", "Eğitim Podcast", "Hikaye Anlatımı", "Teknoloji"],
            key="template_selector"
        )
        
        templates = {
            "Boş": "",
            "Röportaj": """Sunucu: Merhaba ve podcastimize hoş geldiniz! Bugün konuğumuz yapay zeka uzmanı Dr. Mehmet Demir.
Konuk: Merhaba, ben de burada olmaktan büyük mutluluk duyuyorum.
Sunucu: Yapay zeka son yıllarda çok hızlı gelişiyor. Sizce bu gelişim insanlık için ne anlama geliyor?
Konuk: Yapay zeka, insanlık tarihinin en büyük dönüşümlerinden birini başlatıyor.
Uzman: Özellikle sağlık sektöründe devrim niteliğinde gelişmeler var.
Sunucu: Peki ya etik endişeler? Bu konuda neler söylemek istersiniz?
Konuk: Etik kurallar çok önemli. Yapay zekayı doğru yönlendirmeliyiz.
Dış Ses: Değerli dinleyiciler, podcast'imize kısa bir ara veriyoruz.""",
            
            "Haber Bülteni": """Sunucu: Bugün 17 Şubat 2026, işte günün önemli başlıkları...
Raportör: Ekonomi: Borsa endeksi yüzde 2 yükselişle günü tamamladı.
Raportör: Spor: Milli takımımız hazırlık maçında galip geldi.
Dış Ses: Son dakika gelişmesi! Yeni yapay zeka yasası mecliste kabul edildi.
Sunucu: Detaylar haber bültenimizin devamında.""",
            
            "Eğitim Podcast": """Sunucu: Bugünkü bölümümüzde Python programlamaya giriş yapıyoruz.
Uzman: Değişkenler programlamanın temel yapı taşlarıdır.
Sunucu: Peki fonksiyonlar neden bu kadar önemli?
Uzman: Fonksiyonlar kod tekrarını önler ve daha düzenli kod yazmamızı sağlar.
Dış Ses: Öğrenme zamanı! Bugün öğrendiklerinizi mutlaka pratik yapın.""",
            
            "Hikaye Anlatımı": """Dış Ses: Bir varmış bir yokmuş, evvel zaman içinde...
Sunucu: Genç bir kaşif, kayıp bir şehrin peşine düşmüş.
Konuk: Yıllardır bu anı bekliyordum. Macera başlıyor!
Sunucu: Derin ormanlar, yüksek dağlar aşmışlar.
Dış Ses: Ve böylece unutulmaz bir serüven başlamış oldu.""",
            
            "Teknoloji": """Sunucu: Teknoloji gündemine hoş geldiniz! Bugün yapay zeka konuşacağız.
Uzman: Son çıkan yapay zeka modelleri insan seviyesine yaklaşıyor.
Sunucu: Bu teknolojiler günlük hayatımızı nasıl etkileyecek?
Uzman: Sağlıktan eğitime, finanstan üretime her alanda devrim yaşanacak.
Dış Ses: Teknoloji dünyasından son gelişmeler..."""
        }
        
        # Metin girişi
        text_input = st.text_area(
            "Senaryonuzu girin:",
            value=templates.get(template, ""),
            height=350,
            placeholder="Örnek: Sunucu: Merhaba!\nKonuk: Selam!"
        )
        
        # Parse ve analiz
        if text_input:
            parsed_lines = ScriptParser.parse(text_input)
            
            if parsed_lines:
                # Metrikler
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                
                with col_m1:
                    total_lines = len(parsed_lines)
                    st.markdown(UIComponents.stats_card(
                        "Toplam Satır",
                        str(total_lines),
                        "📝",
                        "#3498DB"
                    ), unsafe_allow_html=True)
                
                with col_m2:
                    total_words = sum(len(line['text'].split()) for line in parsed_lines)
                    st.markdown(UIComponents.stats_card(
                        "Kelime",
                        str(total_words),
                        "📊",
                        "#2ECC71"
                    ), unsafe_allow_html=True)
                
                with col_m3:
                    unique_chars = len(set(line['character'] for line in parsed_lines))
                    st.markdown(UIComponents.stats_card(
                        "Karakter",
                        str(unique_chars),
                        "🎭",
                        "#E74C3C"
                    ), unsafe_allow_html=True)
                
                with col_m4:
                    est_duration = total_words / 150  # dakikada 150 kelime
                    st.markdown(UIComponents.stats_card(
                        "Tahmini Süre",
                        f"{est_duration:.1f} dk",
                        "⏱️",
                        "#F39C12"
                    ), unsafe_allow_html=True)
                
                st.markdown("<div class='custom-divider'></div>", unsafe_allow_html=True)
                
                # Önizleme
                st.markdown("**🔍 SENARYO ÖNİZLEME**")
                
                for i, line in enumerate(parsed_lines[:5]):
                    st.markdown(
                        UIComponents.character_card(
                            line['character'],
                            line['text'][:100] + "..." if len(line['text']) > 100 else line['text']
                        ),
                        unsafe_allow_html=True
                    )
                
                if len(parsed_lines) > 5:
                    st.info(f"ve {len(parsed_lines) - 5} satır daha...")
            else:
                st.warning("⚠️ Geçerli bir senaryo girin")
    
    with col_right:
        st.markdown("""
            <div style="
                background: linear-gradient(90deg, #F8F9FA, #FFFFFF);
                padding: 20px;
                border-radius: 20px;
                margin-bottom: 20px;
            ">
                <h2 style="margin: 0; color: #2C3E50;">
                    🎧 PODCAST STUDIO
                </h2>
            </div>
        """, unsafe_allow_html=True)
        
        # Oluşturma butonu
        generate_button = st.button(
            "🎙️ PODCAST OLUŞTUR",
            disabled=not (api_key and text_input and not st.session_state.processing),
            use_container_width=True
        )
        
        if generate_button:
            if not api_key:
                st.markdown("""
                    <div class="error-box">
                        ❌ API anahtarı gerekli!
                    </div>
                """, unsafe_allow_html=True)
            elif not text_input:
                st.markdown("""
                    <div class="error-box">
                        ❌ Lütfen bir senaryo girin!
                    </div>
                """, unsafe_allow_html=True)
            else:
                # Parse et
                parsed_lines = ScriptParser.parse(text_input)
                
                # Validate
                is_valid, error_msg = ScriptParser.validate(parsed_lines)
                
                if not is_valid:
                    st.markdown(f"""
                        <div class="error-box">
                            ❌ {error_msg}
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    # İşleme başla
                    st.session_state.processing = True
                    
                    try:
                        # API istemcisi
                        api = ElevenLabsAPI(api_key)
                        
                        # Progress container
                        progress_container = st.container()
                        
                        with progress_container:
                            st.markdown("""
                                <div class="info-box">
                                    🎵 Podcast oluşturuluyor...
                                </div>
                            """, unsafe_allow_html=True)
                            
                            # Progress bar
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            # Sesleri oluştur
                            audio_segments = []
                            errors = []
                            
                            for i, line in enumerate(parsed_lines):
                                # Status güncelle
                                status_text.info(
                                    f"📢 {line['character']}: {line['text'][:50]}..."
                                )
                                
                                try:
                                    audio = api.text_to_speech(
                                        line['text'],
                                        line['voice_id'],
                                        stability,
                                        similarity
                                    )
                                    
                                    if audio:
                                        audio_segments.append({
                                            'audio': audio,
                                            'character': line['character'],
                                            'text': line['text']
                                        })
                                        st.session_state.success_count += 1
                                    else:
                                        errors.append(f"{line['character']}: Ses oluşturulamadı")
                                        st.session_state.error_count += 1
                                        
                                except Exception as e:
                                    errors.append(f"{line['character']}: {str(e)}")
                                    st.session_state.error_count += 1
                                
                                # Progress bar güncelle
                                progress_bar.progress((i + 1) / len(parsed_lines))
                                
                                # Rate limiting
                                time.sleep(Config.REQUEST_DELAY)
                            
                            # Progress temizle
                            progress_bar.empty()
                            status_text.empty()
                            
                            if audio_segments:
                                # Başarılı
                                st.session_state.current_audio = audio_segments[-1]['audio']
                                st.session_state.generated_segments = audio_segments
                                
                                st.markdown("""
                                    <div class="success-box">
                                        <strong>✅ PODCAST BAŞARIYLA OLUŞTURULDU!</strong><br>
                                        Ses dosyaları hazır.
                                    </div>
                                """, unsafe_allow_html=True)
                                
                                # Hata varsa göster
                                if errors:
                                    with st.expander("⚠️ Hata Detayları"):
                                        for error in errors[:5]:
                                            st.error(error)
                                
                                # Ses segmentlerini göster
                                st.markdown("### 🔊 SES SEGMENTLERİ")
                                
                                for i, seg in enumerate(audio_segments):
                                    with st.expander(f"{i+1}. {seg['character']}", expanded=i==0):
                                        st.markdown(
                                            UIComponents.character_card(
                                                seg['character'],
                                                seg['text'][:100] + "...",
                                                True
                                            ),
                                            unsafe_allow_html=True
                                        )
                                        st.audio(seg['audio'], format="audio/mp3")
                                
                                # Toplu indirme
                                if len(audio_segments) == 1:
                                    st.markdown("### ▶️ PODCAST OYNATICI")
                                    st.audio(audio_segments[0]['audio'], format="audio/mp3")
                                    
                                    st.download_button(
                                        label="📥 MP3 İNDİR",
                                        data=audio_segments[0]['audio'],
                                        file_name=f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                                        mime="audio/mp3"
                                    )
                                else:
                                    st.info("""
                                        ℹ️ Ses birleştirme için FFmpeg gerekli.
                                        Her ses parçasını ayrı ayrı dinleyebilirsiniz.
                                    """)
                                
                                # Geçmişe ekle
                                st.session_state.podcast_history.append({
                                    'date': datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    'segments': len(audio_segments),
                                    'errors': len(errors)
                                })
                            
                            else:
                                st.markdown("""
                                    <div class="error-box">
                                        ❌ Hiç ses dosyası oluşturulamadı!
                                    </div>
                                """, unsafe_allow_html=True)
                    
                    except Exception as e:
                        st.markdown(f"""
                            <div class="error-box">
                                ❌ SİSTEM HATASI: {str(e)}
                            </div>
                        """, unsafe_allow_html=True)
                        logger.error(f"Podcast oluşturma hatası: {str(e)}")
                    
                    finally:
                        st.session_state.processing = False
        
        # Mevcut podcast göster
        elif st.session_state.current_audio and not st.session_state.processing:
            st.markdown("### ▶️ SON PODCAST")
            st.audio(st.session_state.current_audio, format="audio/mp3")
            
            st.download_button(
                label="📥 MP3 İNDİR",
                data=st.session_state.current_audio,
                file_name=f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                mime="audio/mp3"
            )
            
            # Geçmiş
            if st.session_state.generated_segments:
                with st.expander("📋 SEGMENTLER"):
                    for seg in st.session_state.generated_segments[-3:]:
                        st.markdown(
                            UIComponents.character_card(
                                seg['character'],
                                seg['text'][:50] + "..."
                            ),
                            unsafe_allow_html=True
                        )
        
        else:
            st.markdown("""
                <div style="
                    background: #F8F9FA;
                    border: 2px dashed #BDC3C7;
                    border-radius: 20px;
                    padding: 40px;
                    text-align: center;
                ">
                    <div style="font-size: 4rem; margin-bottom: 20px;">🎙️</div>
                    <h3 style="color: #2C3E50;">Podcast Stüdyosu Hazır</h3>
                    <p style="color: #7F8C8D;">
                        Senaryonuzu yazın ve oluşturmaya başlayın
                    </p>
                </div>
            """, unsafe_allow_html=True)
        
        # Geçmiş
        if st.session_state.podcast_history:
            with st.expander("📜 PODCAST GEÇMİŞİ"):
                for i, podcast in enumerate(st.session_state.podcast_history[-5:]):
                    st.markdown(f"""
                        <div style="
                            background: #F8F9FA;
                            padding: 10px;
                            margin: 5px 0;
                            border-radius: 8px;
                        ">
                            <span style="color: #3498DB;">{podcast['date']}</span>
                            <span style="color: #7F8C8D; float: right;">
                                {podcast['segments']} segment
                            </span>
                        </div>
                    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
