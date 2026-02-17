"""
3 Soru 3 Dakika - Çok Sesli Yapay Zeka Podcast Oluşturucu
Streamlit ile geliştirilmiş çok sesli podcast oluşturma uygulaması
"""

import streamlit as st
import requests
import io
import base64
import time
import json
from datetime import datetime

# audioop-lts'yi dene, yoksa fallback mekanizması kullan
try:
    import audioop
except ImportError:
    try:
        import audioop_lts as audioop
    except ImportError:
        # audioop olmadan da çalışacak fallback
        audioop = None
        st.warning("audioop modülü bulunamadı, ses birleştirme sınırlı olabilir.")

# Sayfa yapılandırması
st.set_page_config(
    page_title="3 Soru 3 Dakika - Podcast Oluşturucu",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sabit ses kimlikleri (ElevenLabs voice_id'leri)
VOICE_IDS = {
    "Sunucu": "21m00Tcm4TlvDq8ikWAM",  # Rachel - profesyonel sunucu sesi
    "Konuk": "AZnzlk1XvdvUeBnXmlld",    # Adam - konuk sesi
    "Dış Ses": "EXAVITQu4vr4xnSDxMaL"    # Bella - dış ses
}

# Karakter renkleri ve emojileri
CHARACTERS = {
    "Sunucu": {"color": "#FF4B4B", "emoji": "🎤", "icon": "🎙️", "bg": "#FF4B4B20"},
    "Konuk": {"color": "#4B8BFF", "emoji": "👤", "icon": "🗣️", "bg": "#4B8BFF20"},
    "Dış Ses": {"color": "#4BFF4B", "emoji": "🎧", "icon": "📢", "bg": "#4BFF4B20"}
}

def initialize_session_state():
    """Session state değişkenlerini başlat"""
    if 'podcast_history' not in st.session_state:
        st.session_state.podcast_history = []
    if 'current_podcast' not in st.session_state:
        st.session_state.current_podcast = None
    if 'audio_segments' not in st.session_state:
        st.session_state.audio_segments = []

def parse_script(text):
    """Metni satır satır parse ederek karakter ve metinleri çıkar"""
    lines = text.strip().split('\n')
    parsed_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Karakter ve metin ayırma
        matched = False
        for character in VOICE_IDS.keys():
            if line.startswith(f"{character}:"):
                text = line[len(character)+1:].strip()
                if text:  # Boş metin ekleme
                    parsed_lines.append({
                        'character': character,
                        'text': text,
                        'voice_id': VOICE_IDS[character],
                        'order': len(parsed_lines)
                    })
                matched = True
                break
        
        # Eğer karakter tanımlanmamışsa ve önceki satır varsa ona ekle
        if not matched and parsed_lines:
            parsed_lines[-1]['text'] += " " + line
        elif not matched and not parsed_lines:
            # Hiç satır yoksa yeni Sunucu satırı oluştur
            parsed_lines.append({
                'character': "Sunucu",
                'text': line,
                'voice_id': VOICE_IDS["Sunucu"],
                'order': 0
            })
    
    return parsed_lines

def text_to_speech(text, voice_id, api_key, stability=0.5, similarity=0.75):
    """ElevenLabs API ile metni sese çevir"""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity
        }
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        if response.status_code == 200:
            return {
                'success': True,
                'audio': response.content,
                'format': 'mp3'
            }
        else:
            return {
                'success': False,
                'error': f"API Hatası ({response.status_code})",
                'details': response.text[:200]
            }
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': "İstek zaman aşımına uğradı"
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def combine_audio_files_base64(audio_contents):
    """Ses dosyalarını base64 olarak birleştir (pydub kullanmadan)"""
    if not audio_contents:
        return None
    
    # Basit birleştirme için audio elementlerini sıralı oynat
    combined = {
        'segments': audio_contents,
        'count': len(audio_contents)
    }
    
    return combined

def get_audio_player(audio_bytes, autoplay=False):
    """HTML5 audio player oluştur"""
    b64 = base64.b64encode(audio_bytes).decode()
    autoplay_attr = "autoplay" if autoplay else ""
    audio_html = f"""
        <audio controls {autoplay_attr} style="width: 100%; margin: 10px 0;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            Tarayıcınız audio elementini desteklemiyor.
        </audio>
    """
    return audio_html

def get_playlist_player(audio_segments):
    """Birden fazla ses dosyası için playlist oluştur"""
    if not audio_segments:
        return None
    
    html = """
    <div style="background: #f8f9fa; padding: 1rem; border-radius: 10px;">
        <h4 style="margin-top: 0;">📋 Ses Parçaları</h4>
    """
    
    for i, segment in enumerate(audio_segments):
        b64 = base64.b64encode(segment).decode()
        html += f"""
        <div style="margin: 10px 0; padding: 10px; background: white; border-radius: 5px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="background: #667eea; color: white; width: 25px; height: 25px; 
                           display: flex; align-items: center; justify-content: center; 
                           border-radius: 50%; font-size: 0.8rem;">{i+1}</span>
                <audio controls style="flex: 1;">
                    <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                </audio>
            </div>
        </div>
        """
    
    html += "</div>"
    return html

def display_character_message(character, text, index=None, is_active=False):
    """Karakter mesajını göster"""
    char_info = CHARACTERS.get(character, {
        "color": "#808080", 
        "emoji": "🎙️", 
        "icon": "📢",
        "bg": "#80808020"
    })
    
    color = char_info["color"]
    emoji = char_info["emoji"]
    bg = char_info["bg"]
    
    active_style = "border-left: 5px solid #667eea; transform: translateX(5px);" if is_active else ""
    
    st.markdown(f"""
        <div style="
            padding: 12px;
            margin: 8px 0;
            border-radius: 10px;
            background-color: {bg};
            border-left: 5px solid {color};
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            {active_style}
            hover: transform: translateX(5px);
        ">
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <span style="font-size: 1.2rem; margin-right: 8px;">{emoji}</span>
                <strong style="color: {color}; font-size: 1.1rem;">{character}</strong>
                {f'<span style="margin-left: auto; font-size: 0.8rem; color: #999;">#{index+1}</span>' if index is not None else ''}
            </div>
            <p style="margin: 0; color: #333; line-height: 1.5;">{text}</p>
        </div>
    """, unsafe_allow_html=True)

def calculate_word_count(text):
    """Kelime sayısını hesapla"""
    return len(text.split())

def estimate_duration(word_count):
    """Tahmini süreyi hesapla (dakika cinsinden)"""
    # Ortalama konuşma hızı: dakikada 150 kelime
    minutes = word_count / 150
    return minutes

def main():
    """Ana uygulama fonksiyonu"""
    initialize_session_state()
    
    # Custom CSS
    st.markdown("""
        <style>
        /* Ana stil */
        .stApp {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        }
        
        .main > div {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 2rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
        }
        
        /* Buton stili */
        .stButton > button {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 0.75rem 2rem;
            border-radius: 10px;
            font-weight: bold;
            font-size: 1.1rem;
            transition: all 0.3s;
            width: 100%;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        /* Success box */
        .success-box {
            background: #10b98115;
            border-left: 5px solid #10b981;
            padding: 1rem;
            border-radius: 10px;
            margin: 1rem 0;
        }
        
        /* Warning box */
        .warning-box {
            background: #f59e0b15;
            border-left: 5px solid #f59e0b;
            padding: 1rem;
            border-radius: 10px;
            margin: 1rem 0;
        }
        
        /* Info box */
        .info-box {
            background: #3b82f615;
            border-left: 5px solid #3b82f6;
            padding: 1rem;
            border-radius: 10px;
            margin: 1rem 0;
        }
        
        /* Sidebar stili */
        .css-1d391kg {
            background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
        }
        
        /* Metric cards */
        .metric-card {
            background: white;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }
        
        /* Progress bar */
        .stProgress > div > div {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Ana başlık
    st.markdown("""
        <div style="text-align: center; padding: 2rem; background: white; border-radius: 20px; margin-bottom: 2rem;">
            <h1 style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); 
                      -webkit-background-clip: text; 
                      -webkit-text-fill-color: transparent; 
                      font-size: 3rem;
                      margin-bottom: 0.5rem;">
                🎙️ 3 Soru 3 Dakika
            </h1>
            <p style="color: #666; font-size: 1.2rem;">Çok Sesli Yapay Zeka Podcast Oluşturucu</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("""
            <div style="text-align: center; padding: 1rem; background: white; border-radius: 10px; margin-bottom: 1rem;">
                <h2 style="color: #667eea; margin: 0;">⚙️ Ayarlar</h2>
            </div>
        """, unsafe_allow_html=True)
        
        # API Key girişi
        api_key = st.text_input(
            "🔑 ElevenLabs API Key",
            type="password",
            help="ElevenLabs'dan aldığınız API anahtarını girin",
            placeholder="sk_...",
            key="api_key_input"
        )
        
        if api_key:
            st.success("✅ API Key girildi")
        else:
            st.info("🔑 Lütfen API anahtarınızı girin")
        
        st.markdown("---")
        
        # Ses ayarları
        st.subheader("🎤 Ses Ayarları")
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            stability = st.slider(
                "Stabilite",
                min_value=0.0,
                max_value=1.0,
                value=0.5,
                help="Düşük: dinamik | Yüksek: stabil",
                key="stability"
            )
        
        with col_s2:
            similarity = st.slider(
                "Benzerlik",
                min_value=0.0,
                max_value=1.0,
                value=0.75,
                help="Orijinal sese benzerlik",
                key="similarity"
            )
        
        st.markdown("---")
        
        # Karakter bilgileri
        st.subheader("🎭 Karakterler")
        
        for char, info in CHARACTERS.items():
            st.markdown(f"""
                <div style="
                    padding: 8px; 
                    margin: 4px 0; 
                    background: {info['bg']}; 
                    border-radius: 8px;
                    border-left: 3px solid {info['color']};
                ">
                    <span style="font-size: 1.2rem;">{info['emoji']}</span>
                    <strong style="color: {info['color']}; margin-left: 8px;">{char}</strong>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Hızlı ipuçları
        with st.expander("📖 Hızlı Kılavuz", expanded=False):
            st.markdown("""
            ### 📝 Format
            ```
            Sunucu: Merhaba!
            Konuk: Selam!
            Dış Ses: Duyuru
            ```
            
            ### ✨ Özellikler
            - 🎤 3 farklı karakter
            - 🎨 Renk kodlaması
            - 📥 MP3 indirme
            - 📊 Anlık istatistikler
            - ⏱️ Süre tahmini
            
            ### 💡 İpuçları
            - 3 dakika ≈ 450 kelime
            - Sesler arası boşluk otomatik
            - Her satır için ayrı ses
            """)
        
        # Versiyon
        st.markdown("""
            <div style="text-align: center; color: #999; font-size: 0.8rem; margin-top: 2rem;">
                <p>v1.0.0 | ElevenLabs ile güçlendirildi</p>
                <p style="font-size: 0.7rem;">© 2024 3 Soru 3 Dakika</p>
            </div>
        """, unsafe_allow_html=True)
    
    # Ana içerik - iki kolon
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.markdown("""
            <div style="background: linear-gradient(90deg, #667eea20 0%, #764ba220 100%); 
                       padding: 1rem; 
                       border-radius: 10px; 
                       margin-bottom: 1rem;">
                <h3 style="color: #333; margin: 0;">📝 Podcast Metni</h3>
            </div>
        """, unsafe_allow_html=True)
        
        # Örnek metin seçici
        template_option = st.selectbox(
            "Hazır şablon seçin:",
            ["Boş", "🎙️ Röportaj", "📰 Haber Bülteni", "🎓 Eğitim", "📖 Hikaye"],
            key="template_selector"
        )
        
        templates = {
            "Boş": "",
            "🎙️ Röportaj": """Sunucu: Teknoloji dünyasından herkese merhaba! Bugün çok özel bir konuğumuz var: Yapay Zeka Uzmanı Dr. Ayşe Yılmaz.
Konuk: Merhaba, ben de burada olmaktan mutluluk duyuyorum.
Sunucu: Yapay zeka son yıllarda hayatımızın her alanına girdi. Sizce bizi gelecekte neler bekliyor?
Konuk: Yapay zeka, sağlıktan eğitime, finanstan sanata her alanda devrim yaratacak.
Dış Ses: Ve şimdi kısa bir ara... Size özel mesajımız var!
Sunucu: Evet, kaldığımız yerden devam ediyoruz. Peki yapay zeka etik sorunları nasıl çözeceğiz?
Konuk: Bu çok önemli bir soru. Etik kurallar ve düzenlemeler de yapay zeka ile birlikte gelişmeli.""",
            
            "📰 Haber Bülteni": """Sunucu: Bugünün önemli başlıklarıyla karşınızdayız. İşte günün haberleri.
Dış Ses: Ekonomi: Borsada yükseliş trendi devam ediyor. Endeks yüzde 2 değer kazandı.
Dış Ses: Spor: Milli takımımız hazırlık maçında rakibini 3-1 mağlup etti.
Sunucu: Şimdi hava durumuna geçiyoruz. Meteoroloji'den alınan bilgilere göre...
Dış Ses: Yarından itibaren sıcaklıklar mevsim normallerine dönecek.""",
            
            "🎓 Eğitim": """Sunucu: Bugünkü bölümümüzde Python programlama öğreniyoruz.
Konuk: Değişkenler ve veri tipleriyle başlayalım. Python'da her şey bir nesnedir.
Sunucu: Peki fonksiyonlar nasıl çalışır? Neden kullanırız?
Konuk: Fonksiyonlar, tekrar kullanılabilir kod bloklarıdır. Kodu daha düzenli hale getirir.
Dış Ses: Öğrenme zamanı! Bugün öğrendiklerinizi tekrar edin.""",
            
            "📖 Hikaye": """Dış Ses: Bir varmış bir yokmuş, evvel zaman içinde...
Sunucu: Genç bir kaşif, kayıp şehrin izini sürüyormuş.
Dış Ses: Macera dolu bir yolculuk başlıyor!
Konuk: Uzun yıllardır bu anı bekliyordum. Heyecan verici!
Sunucu: Ve böylece unutulmaz bir serüvenin ilk adımı atılmış oldu."""
        }
        
        # Metin girişi
        text_input = st.text_area(
            "Senaryonuzu girin:",
            value=templates.get(template_option, ""),
            height=350,
            help="Karakter: Metin formatında yazın",
            key="script_input"
        )
        
        # Parse edilmiş metni göster
        if text_input:
            st.markdown("""
                <div style="background: linear-gradient(90deg, #f0f2f6 0%, #e0e4e9 100%); 
                           padding: 0.75rem; 
                           border-radius: 8px; 
                           margin: 1rem 0;
                           font-weight: bold;">
                    📋 Senaryo Önizleme
                </div>
            """, unsafe_allow_html=True)
            
            parsed_lines = parse_script(text_input)
            
            # Kelime sayısı ve süre tahmini
            total_words = sum(calculate_word_count(line['text']) for line in parsed_lines)
            estimated_minutes = estimate_duration(total_words)
            
            # Metrikler
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric("Satır Sayısı", len(parsed_lines))
            with col_m2:
                st.metric("Toplam Kelime", total_words)
            with col_m3:
                st.metric("Tahmini Süre", f"{estimated_minutes:.1f} dk")
            
            # Karakter mesajlarını göster
            for i, line in enumerate(parsed_lines):
                display_character_message(line['character'], line['text'], i)
    
    with col2:
        st.markdown("""
            <div style="background: linear-gradient(90deg, #667eea20 0%, #764ba220 100%); 
                       padding: 1rem; 
                       border-radius: 10px; 
                       margin-bottom: 1rem;">
                <h3 style="color: #333; margin: 0;">🎧 Podcast Çıktısı</h3>
            </div>
        """, unsafe_allow_html=True)
        
        # Oluşturma butonu
        if st.button("🎙️ Podcast Oluştur", use_container_width=True, key="generate_btn"):
            if not api_key:
                st.error("❌ Lütfen ElevenLabs API anahtarınızı girin!")
            elif not text_input:
                st.error("❌ Lütfen bir metin girin!")
            else:
                with st.spinner("🎵 Podcast oluşturuluyor..."):
                    try:
                        # Metni parse et
                        parsed_lines = parse_script(text_input)
                        
                        if not parsed_lines:
                            st.error("❌ Geçerli bir metin girin!")
                            return
                        
                        # Ses dosyalarını oluştur
                        audio_segments = []
                        error_count = 0
                        
                        # Progress bar
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        for i, line in enumerate(parsed_lines):
                            # Status güncelle
                            status_text.info(f"🔊 Ses oluşturuluyor: {line['character']}... ({i+1}/{len(parsed_lines)})")
                            
                            # Ses oluştur
                            result = text_to_speech(
                                line['text'], 
                                line['voice_id'], 
                                api_key,
                                stability,
                                similarity
                            )
                            
                            if result['success']:
                                audio_segments.append({
                                    'audio': result['audio'],
                                    'character': line['character'],
                                    'text': line['text'],
                                    'order': i
                                })
                            else:
                                error_count += 1
                                st.warning(f"⚠️ {line['character']} sesi oluşturulamadı: {result['error']}")
                            
                            # Progress bar güncelle
                            progress_bar.progress((i + 1) / len(parsed_lines))
                            
                            # Rate limiting
                            time.sleep(0.3)
                        
                        if audio_segments:
                            # Session state'e kaydet
                            st.session_state.audio_segments = [seg['audio'] for seg in audio_segments]
                            st.session_state.current_podcast = {
                                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'lines': len(parsed_lines),
                                'segments': len(audio_segments),
                                'errors': error_count
                            }
                            
                            # Progress bar ve status temizle
                            progress_bar.empty()
                            status_text.empty()
                            
                            # Başarı mesajı
                            if error_count == 0:
                                st.markdown("""
                                    <div class="success-box">
                                        <strong>✅ Podcast başarıyla oluşturuldu!</strong><br>
                                        Tüm ses dosyaları hazır.
                                    </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                    <div class="warning-box">
                                        <strong>⚠️ Podcast kısmen oluşturuldu</strong><br>
                                        {error_count} ses dosyası oluşturulamadı.
                                    </div>
                                """, unsafe_allow_html=True)
                            
                            # İstatistikler
                            st.markdown("### 📊 Podcast İstatistikleri")
                            
                            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                            with col_s1:
                                st.metric("Toplam Satır", len(parsed_lines))
                            with col_s2:
                                st.metric("Başarılı", len(audio_segments))
                            with col_s3:
                                st.metric("Hatalı", error_count)
                            with col_s4:
                                total_words = sum(calculate_word_count(line['text']) for line in parsed_lines)
                                st.metric("Kelime", total_words)
                            
                            # Karakter bazlı istatistikler
                            st.markdown("#### 🎭 Konuşma Dağılımı")
                            
                            char_counts = {}
                            for seg in audio_segments:
                                char = seg['character']
                                char_counts[char] = char_counts.get(char, 0) + 1
                            
                            for char, count in char_counts.items():
                                percentage = (count / len(audio_segments)) * 100
                                char_info = CHARACTERS.get(char, {"color": "#808080", "emoji": "🎙️"})
                                
                                st.markdown(f"""
                                    <div style="margin: 10px 0;">
                                        <div style="display: flex; align-items: center; gap: 10px;">
                                            <span style="color: {char_info['color']}; min-width: 100px;">
                                                {char_info['emoji']} {char}:
                                            </span>
                                            <div style="flex: 1; background: #f0f2f6; border-radius: 10px; height: 20px;">
                                                <div style="background: {char_info['color']}; 
                                                          width: {percentage}%; 
                                                          height: 20px; 
                                                          border-radius: 10px;
                                                          transition: width 0.5s ease;">
                                                </div>
                                            </div>
                                            <span style="min-width: 70px; color: #666;">
                                                {count} (%{percentage:.1f})
                                            </span>
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)
                            
                            # Ses parçalarını göster
                            with st.expander("🔊 Ses Parçaları", expanded=False):
                                for i, seg in enumerate(audio_segments):
                                    char_info = CHARACTERS.get(seg['character'], {"color": "#808080", "emoji": "🎙️"})
                                    b64 = base64.b64encode(seg['audio']).decode()
                                    
                                    st.markdown(f"""
                                        <div style="
                                            padding: 10px;
                                            margin: 5px 0;
                                            background: {char_info['color']}10;
                                            border-radius: 8px;
                                            border-left: 3px solid {char_info['color']};
                                        ">
                                            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 5px;">
                                                <span style="color: {char_info['color']};">{char_info['emoji']} {seg['character']}</span>
                                                <span style="color: #999; font-size: 0.8rem;">#{i+1}</span>
                                            </div>
                                            <p style="margin: 5px 0; color: #666; font-size: 0.9rem;">{seg['text'][:100]}...</p>
                                            <audio controls style="width: 100%; margin-top: 5px;">
                                                <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                                            </audio>
                                        </div>
                                    """, unsafe_allow_html=True)
                            
                            # Toplu indirme için birleştirilmiş ses
                            if len(audio_segments) == 1:
                                st.markdown("#### ▶️ Podcast Oynatıcı")
                                audio_player = get_audio_player(audio_segments[0]['audio'])
                                st.markdown(audio_player, unsafe_allow_html=True)
                                
                                st.download_button(
                                    label="📥 MP3 İndir",
                                    data=audio_segments[0]['audio'],
                                    file_name=f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                                    mime="audio/mp3",
                                    use_container_width=True
                                )
                            else:
                                st.info("""
                                    ℹ️ Ses birleştirme için FFmpeg gerekli. 
                                    Her ses parçasını ayrı ayrı dinleyebilirsiniz.
                                """)
                        
                        else:
                            st.error("❌ Hiç ses dosyası oluşturulamadı!")
                            progress_bar.empty()
                            status_text.empty()
                    
                    except Exception as e:
                        st.error(f"❌ Beklenmeyen hata: {str(e)}")
        
        # Mevcut podcast varsa göster
        elif st.session_state.audio_segments:
            st.markdown("#### ▶️ Son Oluşturulan Podcast")
            
            for i, audio_bytes in enumerate(st.session_state.audio_segments[:3]):  # İlk 3 parçayı göster
                with st.expander(f"🔊 Ses Parçası {i+1}", expanded=i==0):
                    audio_player = get_audio_player(audio_bytes)
                    st.markdown(audio_player, unsafe_allow_html=True)
            
            if len(st.session_state.audio_segments) > 3:
                st.info(f"ve {len(st.session_state.audio_segments) - 3} parça daha...")
        
        else:
            st.info("""
                👈 Sol taraftan metninizi girin ve 
                'Podcast Oluştur' butonuna tıklayın
            """)

if __name__ == "__main__":
    main()
