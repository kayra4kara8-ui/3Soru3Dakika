"""
3 Soru 3 Dakika - Çok Sesli Yapay Zeka Podcast Oluşturucu
Streamlit ile geliştirilmiş çok sesli podcast oluşturma uygulaması
"""

import streamlit as st
import requests
import io
import base64
import time
from datetime import datetime

# Sayfa yapılandırması - SADECE BİR KEZ en başta
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
    "Sunucu": {"color": "#FF4B4B", "emoji": "🎤", "icon": "🎙️"},
    "Konuk": {"color": "#4B8BFF", "emoji": "👤", "icon": "🗣️"},
    "Dış Ses": {"color": "#4BFF4B", "emoji": "🎧", "icon": "📢"}
}

def initialize_session_state():
    """Session state değişkenlerini başlat"""
    if 'podcast_history' not in st.session_state:
        st.session_state.podcast_history = []
    if 'current_audio' not in st.session_state:
        st.session_state.current_audio = None
    if 'generated_lines' not in st.session_state:
        st.session_state.generated_lines = []

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
                if text:
                    parsed_lines.append({
                        'character': character,
                        'text': text,
                        'voice_id': VOICE_IDS[character]
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
                'voice_id': VOICE_IDS["Sunucu"]
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
            return response.content
        else:
            st.error(f"API Hatası: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Ses oluşturma hatası: {str(e)}")
        return None

def get_audio_player(audio_bytes):
    """HTML5 audio player oluştur"""
    b64 = base64.b64encode(audio_bytes).decode()
    audio_html = f"""
        <audio controls style="width: 100%; margin: 10px 0;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            Tarayıcınız audio elementini desteklemiyor.
        </audio>
    """
    return audio_html

def display_character_message(character, text, is_active=False):
    """Karakter mesajını göster"""
    char_info = CHARACTERS.get(character, {"color": "#808080", "emoji": "🎙️"})
    color = char_info["color"]
    emoji = char_info["emoji"]
    
    active_style = "border-left: 5px solid #667eea; transform: translateX(5px);" if is_active else ""
    
    st.markdown(f"""
        <div style="
            padding: 12px;
            margin: 8px 0;
            border-radius: 10px;
            background-color: {color}15;
            border-left: 5px solid {color};
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            {active_style}
        ">
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <span style="font-size: 1.2rem; margin-right: 8px;">{emoji}</span>
                <strong style="color: {color};">{character}</strong>
            </div>
            <p style="margin: 0; color: #333;">{text}</p>
        </div>
    """, unsafe_allow_html=True)

def main():
    """Ana uygulama fonksiyonu"""
    initialize_session_state()
    
    # Custom CSS
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .main-header {
            text-align: center;
            padding: 2rem;
            background: white;
            border-radius: 20px;
            margin-bottom: 2rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .main-header h1 {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 3rem;
            margin-bottom: 0.5rem;
        }
        .stButton > button {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 0.75rem 2rem;
            border-radius: 10px;
            font-weight: bold;
            width: 100%;
            transition: all 0.3s;
        }
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        .success-box {
            background: #10b98115;
            border-left: 5px solid #10b981;
            padding: 1rem;
            border-radius: 10px;
            margin: 1rem 0;
        }
        .info-box {
            background: #3b82f615;
            border-left: 5px solid #3b82f6;
            padding: 1rem;
            border-radius: 10px;
            margin: 1rem 0;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
        <div class="main-header">
            <h1>🎙️ 3 Soru 3 Dakika</h1>
            <p style="color: #666; font-size: 1.2rem;">Çok Sesli Yapay Zeka Podcast Oluşturucu</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Ayarlar")
        
        # API Key
        api_key = st.text_input(
            "🔑 ElevenLabs API Key",
            type="password",
            help="ElevenLabs'dan aldığınız API anahtarını girin",
            placeholder="sk_..."
        )
        
        st.markdown("---")
        
        # Ses ayarları
        st.markdown("### 🎤 Ses Ayarları")
        stability = st.slider("Stabilite", 0.0, 1.0, 0.5)
        similarity = st.slider("Benzerlik", 0.0, 1.0, 0.75)
        
        st.markdown("---")
        
        # Karakterler
        st.markdown("### 🎭 Karakterler")
        for char, info in CHARACTERS.items():
            st.markdown(f"""
                <div style="padding: 5px; margin: 2px 0; background: {info['color']}20; border-radius: 5px;">
                    {info['emoji']} {char}
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Kılavuz
        with st.expander("📖 Kullanım Kılavuzu"):
            st.markdown("""
            **Format:**
            ```
            Sunucu: Metin
            Konuk: Metin
            Dış Ses: Metin
            ```
            
            **İpuçları:**
            - Her satırı karakter: metin formatında yazın
            - 3 dakika ≈ 450 kelime
            - Karakter belirtmezseniz Sunucu'ya atanır
            """)
    
    # Ana içerik
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📝 Podcast Metni")
        
        # Örnek metin
        example_text = """Sunucu: Teknoloji dünyasından herkese merhaba! Bugün çok özel bir konuğumuz var.
Konuk: Merhaba, ben de burada olmaktan mutluluk duyuyorum.
Sunucu: Yapay zeka hayatımızı nasıl değiştirecek sizce?
Konuk: Yapay zeka, sağlıktan eğitime her alanda devrim yaratacak.
Dış Ses: Ve şimdi kısa bir ara..."""
        
        text_input = st.text_area(
            "Senaryonuzu girin:",
            value=example_text,
            height=300,
            help="Karakter: Metin formatında yazın"
        )
        
        # Parse edilmiş metin
        if text_input:
            st.markdown("**📋 Önizleme:**")
            parsed_lines = parse_script(text_input)
            for line in parsed_lines:
                display_character_message(line['character'], line['text'])
    
    with col2:
        st.markdown("### 🎧 Podcast Çıktısı")
        
        # Oluştur butonu
        if st.button("🎙️ Podcast Oluştur", use_container_width=True):
            if not api_key:
                st.error("❌ Lütfen API anahtarınızı girin!")
            elif not text_input:
                st.error("❌ Lütfen bir metin girin!")
            else:
                with st.spinner("Podcast oluşturuluyor..."):
                    try:
                        parsed_lines = parse_script(text_input)
                        
                        if not parsed_lines:
                            st.error("❌ Geçerli bir metin girin!")
                            return
                        
                        # Sesleri oluştur
                        audio_files = []
                        progress_bar = st.progress(0)
                        
                        for i, line in enumerate(parsed_lines):
                            status_text = st.empty()
                            status_text.info(f"🔊 {line['character']} sesi oluşturuluyor...")
                            
                            audio = text_to_speech(
                                line['text'], 
                                line['voice_id'], 
                                api_key,
                                stability,
                                similarity
                            )
                            
                            if audio:
                                audio_files.append(audio)
                                st.audio(audio, format="audio/mp3")
                            
                            progress_bar.progress((i + 1) / len(parsed_lines))
                            status_text.empty()
                            time.sleep(0.3)
                        
                        if audio_files:
                            st.session_state.current_audio = audio_files[-1]
                            st.session_state.generated_lines = parsed_lines
                            
                            st.markdown("""
                                <div class="success-box">
                                    ✅ Podcast başarıyla oluşturuldu!
                                </div>
                            """, unsafe_allow_html=True)
                            
                            # İstatistikler
                            total_words = sum(len(line['text'].split()) for line in parsed_lines)
                            st.info(f"📊 {len(parsed_lines)} satır, {total_words} kelime")
                            
                            # İndirme butonu
                            if audio_files:
                                st.download_button(
                                    label="📥 Son Sesi İndir",
                                    data=audio_files[-1],
                                    file_name=f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                                    mime="audio/mp3"
                                )
                        else:
                            st.error("❌ Ses oluşturulamadı!")
                            
                    except Exception as e:
                        st.error(f"❌ Hata: {str(e)}")
        
        # Mevcut podcast
        elif st.session_state.current_audio:
            st.audio(st.session_state.current_audio, format="audio/mp3")
            
            st.download_button(
                label="📥 Podcast'i İndir",
                data=st.session_state.current_audio,
                file_name=f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                mime="audio/mp3"
            )
            
            if st.session_state.generated_lines:
                st.markdown("**📋 Son Podcast:**")
                for line in st.session_state.generated_lines[-3:]:
                    display_character_message(line['character'], line['text'][:50] + "...")
        
        else:
            st.info("👈 Metninizi girin ve 'Podcast Oluştur' butonuna tıklayın")

if __name__ == "__main__":
    main()
