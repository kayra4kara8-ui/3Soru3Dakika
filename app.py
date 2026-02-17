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
from pydub import AudioSegment

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
    "Sunucu": {"color": "#FF4B4B", "emoji": "🎤", "icon": "🎙️"},
    "Konuk": {"color": "#4B8BFF", "emoji": "👤", "icon": "🗣️"},
    "Dış Ses": {"color": "#4BFF4B", "emoji": "🎧", "icon": "📢"}
}

def initialize_session_state():
    """Session state değişkenlerini başlat"""
    if 'podcast_history' not in st.session_state:
        st.session_state.podcast_history = []
    if 'current_podcast' not in st.session_state:
        st.session_state.current_podcast = None

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
            st.error(f"API Hatası ({response.status_code}): {response.text[:100]}")
            return None
    except requests.exceptions.Timeout:
        st.error("İstek zaman aşımına uğradı. Lütfen tekrar deneyin.")
        return None
    except Exception as e:
        st.error(f"Ses oluşturma hatası: {str(e)}")
        return None

def combine_audio_files(audio_segments, pause_ms=500):
    """Ses dosyalarını birleştir"""
    if not audio_segments:
        return None
    
    combined = AudioSegment.empty()
    for i, segment in enumerate(audio_segments):
        if segment:
            combined += segment
            if i < len(audio_segments) - 1:  # Son segmentten sonra boşluk ekleme
                combined += AudioSegment.silent(duration=pause_ms)
    
    return combined

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

def display_character_message(character, text, index=None):
    """Karakter mesajını göster"""
    char_info = CHARACTERS.get(character, {"color": "#808080", "emoji": "🎙️", "icon": "📢"})
    color = char_info["color"]
    emoji = char_info["emoji"]
    
    st.markdown(f"""
        <div style="
            padding: 12px;
            margin: 8px 0;
            border-radius: 10px;
            background-color: {color}15;
            border-left: 5px solid {color};
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s;
            hover: transform: translateX(5px);
        ">
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <span style="font-size: 1.2rem; margin-right: 8px;">{emoji}</span>
                <strong style="color: {color}; font-size: 1.1rem;">{character}</strong>
            </div>
            <p style="margin: 0; color: #333; line-height: 1.5;">{text}</p>
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
        .main > div {
            background: white;
            border-radius: 20px;
            padding: 2rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .stButton > button {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 0.5rem 2rem;
            border-radius: 10px;
            font-weight: bold;
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
        </style>
    """, unsafe_allow_html=True)
    
    # Ana başlık
    st.markdown("""
        <div style="text-align: center; padding: 2rem; background: white; border-radius: 20px; margin-bottom: 2rem;">
            <h1 style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 3rem;">
                🎙️ 3 Soru 3 Dakika
            </h1>
            <p style="color: #666; font-size: 1.2rem;">Çok Sesli Yapay Zeka Podcast Oluşturucu</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("""
            <div style="text-align: center; padding: 1rem;">
                <h2 style="color: #667eea;">⚙️ Ayarlar</h2>
            </div>
        """, unsafe_allow_html=True)
        
        # API Key girişi
        api_key = st.text_input(
            "🔑 ElevenLabs API Key",
            type="password",
            help="ElevenLabs'dan aldığınız API anahtarını girin",
            placeholder="sk_..."
        )
        
        st.markdown("---")
        
        # Ses ayarları
        st.subheader("🎤 Ses Ayarları")
        stability = st.slider(
            "Stabilite",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            help="Düşük: dinamik | Yüksek: stabil"
        )
        
        similarity = st.slider(
            "Benzerlik",
            min_value=0.0,
            max_value=1.0,
            value=0.75,
            help="Orijinal sese benzerlik"
        )
        
        pause_duration = st.slider(
            "Ses arası boşluk (ms)",
            min_value=0,
            max_value=2000,
            value=500,
            step=100,
            help="Konuşmalar arası bekleme süresi"
        )
        
        st.markdown("---")
        
        # Karakter bilgileri
        st.subheader("🎭 Karakterler")
        for char, info in CHARACTERS.items():
            st.markdown(f"""
                <div style="padding: 5px; margin: 2px 0; background: {info['color']}20; border-radius: 5px;">
                    {info['emoji']} <strong>{char}</strong>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Hızlı ipuçları
        with st.expander("📖 Hızlı Kılavuz"):
            st.markdown("""
            **Format:**
            ```
            Sunucu: Merhaba!
            Konuk: Selam!
            Dış Ses: Duyuru
            ```
            
            **Özellikler:**
            - 🎤 3 farklı karakter
            - 🎨 Renk kodlaması
            - 📥 MP3 indirme
            - 📊 Anlık istatistikler
            """)
        
        # Versiyon
        st.markdown("""
            <div style="text-align: center; color: #999; font-size: 0.8rem; margin-top: 2rem;">
                v1.0.0 | ElevenLabs ile güçlendirildi
            </div>
        """, unsafe_allow_html=True)
    
    # Ana içerik - iki kolon
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.markdown("""
            <div style="background: #f8f9fa; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;">
                <h3 style="color: #333;">📝 Podcast Metni</h3>
            </div>
        """, unsafe_allow_html=True)
        
        # Örnek metin şablonu
        example_text = """Sunucu: Teknoloji dünyasından herkese merhaba! Bugün çok özel bir konuğumuz var.
Konuk: Merhaba, ben de burada olmaktan mutluluk duyuyorum.
Sunucu: Yapay zeka hayatımızı nasıl değiştirecek sizce?
Konuk: Yapay zeka, sağlıktan eğitime her alanda devrim yaratacak.
Dış Ses: Ve şimdi kısa bir müzik arası...
Sunucu: Evet, kaldığımız yerden devam ediyoruz."""
        
        text_input = st.text_area(
            "Senaryonuzu girin:",
            value=example_text,
            height=300,
            help="Karakter: Metin formatında yazın"
        )
        
        # Parse edilmiş metni göster
        if text_input:
            st.markdown("""
                <div style="background: #f0f2f6; padding: 0.5rem; border-radius: 5px; margin: 1rem 0;">
                    <strong>📋 Önizleme:</strong>
                </div>
            """, unsafe_allow_html=True)
            
            parsed_lines = parse_script(text_input)
            for line in parsed_lines:
                display_character_message(line['character'], line['text'])
    
    with col2:
        st.markdown("""
            <div style="background: #f8f9fa; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;">
                <h3 style="color: #333;">🎧 Podcast Çıktısı</h3>
            </div>
        """, unsafe_allow_html=True)
        
        # Oluşturma butonu
        if st.button("🎙️ Podcast Oluştur", use_container_width=True):
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
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        for i, line in enumerate(parsed_lines):
                            status_text.info(f"🔊 Ses oluşturuluyor: {line['character']}...")
                            
                            audio_content = text_to_speech(
                                line['text'], 
                                line['voice_id'], 
                                api_key,
                                stability,
                                similarity
                            )
                            
                            if audio_content:
                                audio_segment = AudioSegment.from_mp3(io.BytesIO(audio_content))
                                audio_segments.append(audio_segment)
                            
                            progress_bar.progress((i + 1) / len(parsed_lines))
                            time.sleep(0.3)  # Rate limiting
                        
                        if audio_segments:
                            # Sesleri birleştir
                            status_text.info("🔗 Ses dosyaları birleştiriliyor...")
                            combined_audio = combine_audio_files(audio_segments, pause_duration)
                            
                            # Ses dosyasını kaydet
                            audio_bytes = io.BytesIO()
                            combined_audio.export(audio_bytes, format="mp3")
                            audio_bytes = audio_bytes.getvalue()
                            
                            # Session state'e kaydet
                            st.session_state.current_podcast = {
                                'audio': audio_bytes,
                                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'lines': len(parsed_lines)
                            }
                            
                            # Başarı mesajı
                            st.markdown("""
                                <div class="success-box">
                                    ✅ Podcast başarıyla oluşturuldu!
                                </div>
                            """, unsafe_allow_html=True)
                            
                            progress_bar.empty()
                            status_text.empty()
                            
                            # Ses oynatıcı
                            st.markdown("#### ▶️ Podcast Oynatıcı")
                            audio_player = get_audio_player(audio_bytes)
                            st.markdown(audio_player, unsafe_allow_html=True)
                            
                            # İndirme butonu
                            col_d1, col_d2 = st.columns(2)
                            with col_d1:
                                st.download_button(
                                    label="📥 MP3 İndir",
                                    data=audio_bytes,
                                    file_name=f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                                    mime="audio/mp3",
                                    use_container_width=True
                                )
                            
                            # İstatistikler
                            st.markdown("---")
                            st.markdown("### 📊 İstatistikler")
                            col_s1, col_s2, col_s3 = st.columns(3)
                            
                            with col_s1:
                                st.metric("Toplam Satır", len(parsed_lines))
                            with col_s2:
                                total_words = sum(len(line['text'].split()) for line in parsed_lines)
                                st.metric("Kelime Sayısı", total_words)
                            with col_s3:
                                duration = len(combined_audio) / 1000
                                minutes = int(duration // 60)
                                seconds = int(duration % 60)
                                st.metric("Süre", f"{minutes}:{seconds:02d}")
                            
                            # Karakter bazlı istatistikler
                            char_counts = {}
                            for line in parsed_lines:
                                char = line['character']
                                char_counts[char] = char_counts.get(char, 0) + 1
                            
                            st.markdown("#### 🎭 Konuşma Dağılımı")
                            for char, count in char_counts.items():
                                percentage = (count / len(parsed_lines)) * 100
                                st.markdown(f"""
                                    <div style="margin: 5px 0;">
                                        <span style="color: {CHARACTERS[char]['color']};">{CHARACTERS[char]['emoji']} {char}:</span>
                                        <div style="background: #f0f2f6; border-radius: 10px; height: 10px; width: 100%; margin-top: 2px;">
                                            <div style="background: {CHARACTERS[char]['color']}; width: {percentage}%; height: 10px; border-radius: 10px;"></div>
                                        </div>
                                        <small>{count} satır (%{percentage:.1f})</small>
                                    </div>
                                """, unsafe_allow_html=True)
                        
                        else:
                            st.error("❌ Ses dosyası oluşturulamadı!")
                    
                    except Exception as e:
                        st.error(f"❌ Hata: {str(e)}")
        
        # Mevcut podcast varsa göster
        elif st.session_state.current_podcast:
            audio_bytes = st.session_state.current_podcast['audio']
            
            st.markdown("#### ▶️ Son Oluşturulan Podcast")
            audio_player = get_audio_player(audio_bytes)
            st.markdown(audio_player, unsafe_allow_html=True)
            
            st.download_button(
                label="📥 MP3 İndir",
                data=audio_bytes,
                file_name=f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                mime="audio/mp3",
                use_container_width=True
            )
        
        else:
            st.info("👈 Sol taraftan metninizi girin ve 'Podcast Oluştur' butonuna tıklayın")

if __name__ == "__main__":
    main()