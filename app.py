"""
🎬 3 Soru 3 Dakika — Sesli Animasyonlu Sunum Oluşturucu
Kendi klonlanmış sesinizle animasyonlu slaytlar + MP4 video.
"""

import streamlit as st
import requests
import time
import json
import base64
import io
import os
import tempfile
import subprocess
import math
from typing import Optional

# ============================================================
# 1. KONFİGÜRASYON — Buradan düzenleyin
# ============================================================

CHARACTERS = {
    "Sunucu": {
        "color": "#E74C3C",
        "bg": "linear-gradient(135deg,#E74C3C 0%,#922b21 100%)",
        "emoji": "🎤",
        "animation": "bounce",
        "position": "left",
        "svg_accent": "#ff8a80",
    },
    "Konuk": {
        "color": "#3498DB",
        "bg": "linear-gradient(135deg,#3498DB 0%,#1a5276 100%)",
        "emoji": "👤",
        "animation": "pulse",
        "position": "right",
        "svg_accent": "#82cfff",
    },
    "Dis Ses": {
        "color": "#2ECC71",
        "bg": "linear-gradient(135deg,#2ECC71 0%,#1a7a45 100%)",
        "emoji": "🎧",
        "animation": "float",
        "position": "center",
        "svg_accent": "#a8ffcb",
    },
    "Uzman": {
        "color": "#F39C12",
        "bg": "linear-gradient(135deg,#F39C12,#7d5300)",
        "emoji": "👨‍🏫",
        "animation": "shake",
        "position": "left",
        "svg_accent": "#ffe082",
    },
    "Raportör": {
        "color": "#9B59B6",
        "bg": "linear-gradient(135deg,#9B59B6,#4a235a)",
        "emoji": "📰",
        "animation": "bounce",
        "position": "right",
        "svg_accent": "#e1bee7",
    },
    "Anlatici": {
        "color": "#1ABC9C",
        "bg": "linear-gradient(135deg,#1ABC9C,#0e6655)",
        "emoji": "📖",
        "animation": "pulse",
        "position": "center",
        "svg_accent": "#b2dfdb",
    },
}

VOICE_IDS = {
    "Sunucu":    "KENDI_SES_ID_BURAYA",
    "Konuk":     "KENDI_SES_ID_BURAYA",
    "Dis Ses":   "KENDI_SES_ID_BURAYA",
    "Uzman":     "KENDI_SES_ID_BURAYA",
    "Raportör":  "KENDI_SES_ID_BURAYA",
    "Anlatici":  "KENDI_SES_ID_BURAYA",
}

FALLBACK_COLORS = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
    "#FFEAA7", "#DDA0DD", "#F7DC6F", "#BB8FCE",
]

TEMPLATES = {
    "🎤 Röportaj": (
        "Sunucu: Merhaba ve podcastimize hos geldiniz! Bugün cok özel bir konugumuz var.\n"
        "Konuk: Merhaba! Burada olmaktan gercekten mutluyum.\n"
        "Dis Ses: Bugünkü konumuz yapay zekanin gelecegi.\n"
        "Sunucu: Peki, yapay zeka hayatimizi nasil degistirecek?\n"
        "Konuk: Inanilmaz gelismeler yasaniyor. On yil icinde her sey farkli olacak.\n"
        "Dis Ses: Ve simdi kisa bir ara veriyoruz.\n"
        "Sunucu: Tekrar hos geldiniz! Son sorumuz: Bize tavsiyeniz nedir?\n"
        "Konuk: Merak edin, ögrenin ve adapte olun. Bu üclü yeterli.\n"
        "Dis Ses: Bizi dinlediginiz icin tesekkürler!"
    ),
    "📰 Haber": (
        "Dis Ses: 3 Soru 3 Dakika haber bültenine hos geldiniz.\n"
        "Sunucu: Bugünün öne cikan gelismelerini aktariyoruz.\n"
        "Uzman: Teknoloji sektöründen carpici rakamlar aciklandi.\n"
        "Sunucu: Bu gelismeler sektörü nasil etkiliyor?\n"
        "Uzman: Dönüsüm hizi beklentilerin cok üzerinde seyrediyor.\n"
        "Raportör: Uzmanlar önümüzdeki döneme dikkatli yaklasılmasini öneriyor.\n"
        "Dis Ses: Bültenimizin sonuna geldik. Yarin görüsmek üzere!"
    ),
    "📚 Egitim": (
        "Sunucu: Bilim dünyasina hos geldiniz!\n"
        "Dis Ses: Bu bölümde kuantum fiziginin temellerini ele alacagiz.\n"
        "Konuk: Kuantum fizigi, atom alti parcaciklarin davranisini inceler.\n"
        "Sunucu: Bu bilgi günlük hayatimiza nasil yansiyor?\n"
        "Uzman: Akilli telefondan tibbi cihazlara kadar her yerde kuantum var.\n"
        "Konuk: Süperpozisyon ilkesi en ilginc kavram. Parcacik ayni anda iki yerde olabilir.\n"
        "Anlatici: Bir sonraki bölümde kuantum dolanikligini inceleyecegiz. Takipte kalin!"
    ),
}

VIDEO_CONFIG = {
    "fps": 30,
    "width": 1280,
    "height": 720,
    "bg_color": (10, 10, 20),
}


# ============================================================
# 2. YARDIMCI
# ============================================================

def hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ============================================================
# 3. SCRIPT PARSER
# ============================================================

class ScriptParser:
    def __init__(self):
        self._dyn = {}
        self._ci  = 0

    def _info(self, name):
        if name in CHARACTERS:
            return CHARACTERS[name]
        if name not in self._dyn:
            c = FALLBACK_COLORS[self._ci % len(FALLBACK_COLORS)]
            self._dyn[name] = {
                "color": c, "bg": f"linear-gradient(135deg,{c},{c}88)",
                "emoji": "🔊", "animation": "pulse", "position": "center", "svg_accent": "#fff",
            }
            self._ci += 1
        return self._dyn[name]

    def parse(self, script: str) -> list:
        segments, cur_char, cur_parts = [], None, []
        for line in script.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            if ':' in line:
                ci = line.index(':')
                cand = line[:ci].strip()
                rest = line[ci+1:].strip()
                if 0 < len(cand) <= 35 and not any(x in cand for x in '.!?,'):
                    if cur_char and cur_parts:
                        segments.append(self._make(cur_char, ' '.join(cur_parts)))
                    cur_char, cur_parts = cand, [rest] if rest else []
                    continue
            if cur_char:
                cur_parts.append(line)
            else:
                cur_char = list(CHARACTERS.keys())[0]
                cur_parts = [line]
        if cur_char and cur_parts:
            segments.append(self._make(cur_char, ' '.join(cur_parts)))
        return segments

    def _make(self, char, text):
        return {"character": char, "text": text, "info": self._info(char)}

    @staticmethod
    def wc(s): return len(s.split())

    @staticmethod
    def dur(wc):
        m, s = divmod(int(wc / 130 * 60), 60)
        return f"{m}:{s:02d}"


# ============================================================
# 4. ELEVENLABS
# ============================================================

class ElevenLabsAPI:
    BASE = "https://api.elevenlabs.io/v1"

    def __init__(self, key):
        self.key = key
        self.h = {"xi-api-key": key}

    def check(self):
        try:
            r = requests.get(f"{self.BASE}/user", headers=self.h, timeout=10)
            if r.status_code == 200:
                d = r.json()
                name = d.get("first_name", "Kullanici")
                cc   = d.get("subscription", {}).get("character_count", "?")
                cl   = d.get("subscription", {}).get("character_limit", "?")
                return True, f"Hos geldin, {name}! Karakter: {cc}/{cl}"
            return False, f"Hata {r.status_code}: {r.text[:80]}"
        except Exception as e:
            return False, f"Baglanti hatasi: {e}"

    def list_voices(self):
        try:
            r = requests.get(f"{self.BASE}/voices", headers=self.h, timeout=10)
            return r.json().get("voices", []) if r.status_code == 200 else []
        except:
            return []

    def tts(self, text, voice_id, stab=0.5, sim=0.75) -> Optional[bytes]:
        try:
            r = requests.post(
                f"{self.BASE}/text-to-speech/{voice_id}",
                headers={**self.h, "Content-Type": "application/json"},
                json={"text": text, "model_id": "eleven_multilingual_v2",
                      "voice_settings": {"stability": stab, "similarity_boost": sim}},
                timeout=60,
            )
            return r.content if r.status_code == 200 else None
        except:
            return None

    @staticmethod
    def audio_duration(audio: bytes) -> float:
        if not audio:
            return 3.0
        return max(1.0, len(audio) / 16000)


# ============================================================
# 5. VIDEO MAKER
# ============================================================

class VideoMaker:
    def __init__(self):
        self.has_pil    = False
        self.has_ffmpeg = False
        try:
            from PIL import Image, ImageDraw, ImageFont
            self.Image = Image
            self.ImageDraw = ImageDraw
            self.ImageFont = ImageFont
            self.has_pil = True
        except ImportError:
            pass
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=5)
            self.has_ffmpeg = True
        except:
            pass

    def ready(self):
        return self.has_pil and self.has_ffmpeg

    def _frame(self, seg: dict, frame_n: int, total_n: int):
        w, h = VIDEO_CONFIG["width"], VIDEO_CONFIG["height"]
        info  = seg["info"]
        color = hex_to_rgb(info["color"])
        dark  = tuple(max(0, c - 90) for c in color)
        darker = tuple(max(0, c - 150) for c in color)

        img  = self.Image.new("RGBA", (w, h), (10, 10, 20, 255))
        draw = self.ImageDraw.Draw(img)

        # gradient rows
        for y in range(h):
            t = y / h
            r = int(darker[0]*(1-t) + dark[0]*t)
            g = int(darker[1]*(1-t) + dark[1]*t)
            b = int(darker[2]*(1-t) + dark[2]*t)
            draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

        # animated orb
        t     = frame_n / max(total_n - 1, 1)
        anim  = info.get("animation", "pulse")
        cx, cy = w // 2, h // 2 - 80
        orb_r = 110
        if anim == "bounce":
            cy += int(14 * math.sin(t * math.pi * 4))
        elif anim == "pulse":
            orb_r = int(110 + 10 * math.sin(t * math.pi * 4))
        elif anim == "float":
            cx += int(12 * math.sin(t * math.pi * 2))
            cy += int(9 * math.cos(t * math.pi * 2))
        elif anim == "shake":
            cx += int(7 * math.sin(t * math.pi * 8))

        # glow rings
        for g_i in range(4, 0, -1):
            gr = orb_r + g_i * 14
            ga = max(0, 28 - g_i * 7)
            draw.ellipse([cx-gr, cy-gr, cx+gr, cy+gr], fill=(*color, ga))

        draw.ellipse([cx-orb_r, cy-orb_r, cx+orb_r, cy+orb_r], fill=(*color, 210))

        # fonts
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
        font_big = font_med = font_sm = None
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    font_big = self.ImageFont.truetype(fp, 36)
                    font_med = self.ImageFont.truetype(fp, 28)
                    font_sm  = self.ImageFont.truetype(fp, 24)
                    break
                except:
                    pass
        if font_sm is None:
            font_big = font_med = font_sm = self.ImageFont.load_default()

        # character name
        draw.text((cx, cy + orb_r + 28), seg["character"],
                  font=font_big, fill=(255, 255, 255, 220), anchor="mm")

        # speech bubble
        bub_y  = h - 210
        bub_x  = 80
        bub_w  = w - 160
        bub_h  = 160
        draw.rounded_rectangle(
            [bub_x, bub_y, bub_x + bub_w, bub_y + bub_h],
            radius=22, fill=(240, 240, 255, 210),
            outline=(*color, 200), width=3,
        )

        # typewriter text
        text     = seg["text"]
        revealed = int(len(text) * min(1.0, t * 2.8 + 0.04))
        partial  = text[:revealed]

        # word wrap
        words  = partial.split()
        lines, line = [], ""
        for word in words:
            test = (line + " " + word).strip()
            try:
                bbox = draw.textbbox((0, 0), test, font=font_sm)
                tw   = bbox[2] - bbox[0]
            except:
                tw = len(test) * 13
            if tw < bub_w - 60:
                line = test
            else:
                if line: lines.append(line)
                line = word
        if line: lines.append(line)

        ty = bub_y + 22
        for tl in lines[:4]:
            draw.text((bub_x + bub_w // 2, ty), tl, font=font_sm,
                      fill=(20, 20, 40, 240), anchor="mm")
            ty += 32

        # sound wave bars
        wy = bub_y - 45
        for bi in range(8):
            bh_val = int(14 + 22 * abs(math.sin(t * math.pi * 3 + bi * 0.5)))
            bx = w // 2 - 62 + bi * 18
            draw.rounded_rectangle(
                [bx, wy - bh_val, bx + 10, wy],
                radius=3, fill=(*color, 180),
            )

        # progress bar
        pw = int(w * frame_n / max(total_n - 1, 1))
        draw.rectangle([0, h - 7, pw, h], fill=color)

        return img.convert("RGB")

    def make(self, audio_segs: list, out_path: str, cb=None) -> bool:
        fps    = VIDEO_CONFIG["fps"]
        tmpdir = tempfile.mkdtemp()

        frame_list  = []
        all_audio   = b""
        frame_cursor = 0

        for seg in audio_segs:
            audio  = seg.get("audio") or b""
            dur    = seg.get("duration", 3.0)
            n      = max(fps, int(dur * fps))
            frame_list.append((frame_cursor, frame_cursor + n, seg))
            frame_cursor += n
            all_audio += audio

        total = frame_cursor
        if cb: cb(0.05, "Kareler olusturuluyor...")

        fid = 0
        for start, end, seg in frame_list:
            seg_n = end - start
            for fi in range(seg_n):
                img = self._frame(seg, fi, seg_n)
                img.save(os.path.join(tmpdir, f"frame_{fid:06d}.png"))
                fid += 1
            if cb:
                cb(0.05 + 0.65 * (fid / total), f"Kare {fid}/{total}")

        if cb: cb(0.72, "Ses dosyasi hazirlaniyor...")
        audio_path = os.path.join(tmpdir, "audio.mp3")
        with open(audio_path, "wb") as f:
            f.write(all_audio)

        if cb: cb(0.78, "FFmpeg ile video olusturuluyor...")
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", os.path.join(tmpdir, "frame_%06d.png"),
            "-i", audio_path,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-pix_fmt", "yuv420p",
            out_path,
        ]
        res = subprocess.run(cmd, capture_output=True)
        if cb: cb(1.0, "Tamamlandi!")
        return res.returncode == 0


# ============================================================
# 6. HTML SLAYT MOTORU
# ============================================================

def build_slide_html(segments: list) -> str:
    data = json.dumps([
        {
            "char": s["character"],
            "text": s["text"],
            "emoji": s["info"]["emoji"],
            "color": s["info"]["color"],
            "bg": s["info"]["bg"],
            "anim": s["info"].get("animation", "pulse"),
        }
        for s in segments
    ])

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:'Segoe UI',sans-serif;background:#0a0a14;color:#eee;overflow:hidden;height:100vh;display:flex;flex-direction:column;}}
  #stage{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:28px;transition:background 0.6s ease;}}
  .av{{font-size:96px;display:block;margin-bottom:12px;line-height:1;}}
  .cname{{font-size:20px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin-bottom:20px;text-align:center;}}
  .bubble{{background:rgba(255,255,255,0.11);backdrop-filter:blur(14px);border-radius:22px;padding:24px 36px;max-width:700px;font-size:19px;line-height:1.7;text-align:center;border:1.5px solid rgba(255,255,255,0.18);box-shadow:0 10px 50px rgba(0,0,0,0.45);}}
  .waves{{display:flex;gap:6px;align-items:flex-end;justify-content:center;height:40px;margin-top:20px;}}
  .wb{{width:7px;border-radius:4px;animation:wb 0.6s ease-in-out infinite;}}
  #prog{{height:5px;background:rgba(255,255,255,0.08);flex-shrink:0;}}
  #pfill{{height:100%;width:0%;transition:width 0.4s;}}
  #ctrl{{display:flex;gap:10px;justify-content:center;align-items:center;padding:14px;background:rgba(0,0,0,0.5);flex-shrink:0;}}
  btn,button{{padding:9px 20px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;transition:all .18s;}}
  #bprev{{background:rgba(255,255,255,.09);color:#fff;}}
  #bnext{{background:#27ae60;color:#fff;}}
  #bplay{{background:#2980b9;color:#fff;}}
  button:hover{{opacity:.82;transform:translateY(-2px);}}
  #cnt{{color:rgba(255,255,255,.45);font-size:13px;padding:0 8px;}}
  .in{{animation:fadeUp .4s ease both;}}
  @keyframes fadeUp{{from{{opacity:0;transform:translateY(28px)}}to{{opacity:1;transform:translateY(0)}}}}
  @keyframes bounce{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-16px)}}}}
  @keyframes pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.12)}}}}
  @keyframes float{{0%,100%{{transform:translateY(-8px) rotate(-3deg)}}50%{{transform:translateY(8px) rotate(3deg)}}}}
  @keyframes shake{{0%,100%{{transform:rotate(0)}}25%{{transform:rotate(-6deg)}}75%{{transform:rotate(6deg)}}}}
  @keyframes wb{{0%,100%{{transform:scaleY(.35)}}50%{{transform:scaleY(1)}}}}
  @keyframes tw{{from{{clip-path:inset(0 100% 0 0)}}to{{clip-path:inset(0 0% 0 0)}}}}
</style>
</head>
<body>
<div id="prog"><div id="pfill"></div></div>
<div id="stage">
  <div class="av" id="av">🎤</div>
  <div class="cname" id="cname"></div>
  <div class="bubble"><span id="bt" style="animation:tw 1.4s steps(60,end) forwards;"></span></div>
  <div class="waves" id="waves"></div>
</div>
<div id="ctrl">
  <button id="bprev" onclick="go(-1)">◀ Geri</button>
  <span id="cnt">0/0</span>
  <button id="bplay" onclick="togglePlay()">▶ Oynat</button>
  <button id="bnext" onclick="go(1)">İleri ▶</button>
</div>
<script>
const S={slides_js}, slides=S;
let cur=0,playing=false,timer=null;
function render(i){{
  const s=slides[i];
  const stage=document.getElementById('stage');
  stage.style.background=s.bg;
  const av=document.getElementById('av');
  av.textContent=s.emoji;
  av.style.animation='none';
  void av.offsetWidth;
  av.style.animation=s.anim+' 0.75s ease-in-out infinite';
  document.getElementById('cname').textContent=s.char;
  document.getElementById('cname').style.color=s.color;
  const bt=document.getElementById('bt');
  bt.textContent=s.text;
  bt.style.animation='none';
  void bt.offsetWidth;
  bt.style.animation='tw 1.5s steps(60,end) forwards';
  const bub=document.querySelector('.bubble');
  bub.style.borderColor=s.color+'44';
  bub.style.boxShadow='0 10px 50px '+s.color+'2a';
  const wv=document.getElementById('waves');
  wv.innerHTML='';
  for(let j=0;j<9;j++){{
    const b=document.createElement('div');
    b.className='wb';
    b.style.background=s.color;
    b.style.height=(12+Math.random()*28)+'px';
    b.style.animationDelay=(j*.07)+'s';
    b.style.animationDuration=(.38+Math.random()*.44)+'s';
    wv.appendChild(b);
  }}
  stage.className='in';
  document.getElementById('pfill').style.width=((i+1)/slides.length*100)+'%';
  document.getElementById('pfill').style.background=s.color;
  document.getElementById('cnt').textContent=(i+1)+' / '+slides.length;
}}
function go(d){{cur=(cur+d+slides.length)%slides.length;render(cur);}}
function togglePlay(){{
  playing=!playing;
  document.getElementById('bplay').textContent=playing?'⏸ Durdur':'▶ Oynat';
  if(playing)loop(); else clearTimeout(timer);
}}
function loop(){{if(!playing)return;go(1);timer=setTimeout(loop,4200);}}
if(slides.length)render(0);
</script>
</body>
</html>""".replace("{slides_js}", data)


# ============================================================
# 7. UI
# ============================================================

def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400&display=swap');
html,body,[class*="css"]{font-family:'Sora',sans-serif;}
.stApp{background:linear-gradient(145deg,#08080f,#0f1018 50%,#0a0d15);color:#e8e8f4;}
.hdr{text-align:center;padding:1.8rem 1rem 1rem;}
.hdr h1{font-size:2.5rem;font-weight:800;background:linear-gradient(90deg,#E74C3C,#ff9a9a,#3498DB,#a8d8ff,#2ECC71);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;letter-spacing:-1px;margin-bottom:.25rem;}
.hdr p{color:#778;font-size:.88rem;letter-spacing:.07em;}
section[data-testid="stSidebar"]{background:rgba(8,8,18,.97);border-right:1px solid rgba(255,255,255,.05);}
.sc{border-radius:12px;padding:.85rem 1.05rem;margin:.45rem 0;border-left:4px solid;background:rgba(255,255,255,.04);transition:transform .14s;}
.sc:hover{transform:translateX(4px);}
.sc-c{font-size:.68rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.28rem;}
.sc-t{font-size:.9rem;line-height:1.6;color:#ccd;}
.sr{display:flex;gap:1rem;padding:.65rem .9rem;background:rgba(255,255,255,.04);border-radius:8px;margin:.6rem 0;font-size:.78rem;color:#aaa;}
.sr strong{color:#eee;}
.bdg{display:inline-flex;align-items:center;gap:.3rem;padding:.26rem .65rem;border-radius:50px;font-size:.7rem;font-weight:600;margin:.15rem;}
.bok{background:rgba(46,204,113,.12);color:#2ECC71;border:1px solid rgba(46,204,113,.28);}
.bwn{background:rgba(231,76,60,.12);color:#E74C3C;border:1px solid rgba(231,76,60,.28);}
.sct{font-size:.66rem;letter-spacing:.14em;text-transform:uppercase;color:#555;margin:.75rem 0 .35rem;}
audio{width:100%;border-radius:8px;margin:3px 0;}
textarea{background:rgba(255,255,255,.04)!important;border-radius:10px!important;color:#eee!important;font-family:'JetBrains Mono',monospace!important;font-size:.82rem!important;}
hr{border-color:rgba(255,255,255,.07);}
</style>
""", unsafe_allow_html=True)


def voice_status_html():
    parts = []
    for ch, info in CHARACTERS.items():
        vid = VOICE_IDS.get(ch, "")
        ok  = bool(vid and vid not in ("KENDI_SES_ID_BURAYA", ""))
        cls = "bok" if ok else "bwn"
        ic  = "✓" if ok else "✗"
        parts.append(f'<span class="bdg {cls}">{info["emoji"]} {ch} {ic}</span>')
    return "".join(parts)


def seg_card(s):
    c = s["info"]["color"]
    st.markdown(
        f'<div class="sc" style="border-color:{c};">'
        f'<div class="sc-c" style="color:{c};">{s["info"]["emoji"]} {s["character"]}</div>'
        f'<div class="sc-t">{s["text"]}</div></div>',
        unsafe_allow_html=True,
    )


# ============================================================
# 8. SESSION STATE
# ============================================================

def init():
    for k, v in [
        ("segs", []), ("audio_segs", []), ("full_audio", None),
        ("history", []), ("api_ok", False), ("pres_html", ""),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v


# ============================================================
# 9. SIDEBAR
# ============================================================

def sidebar():
    with st.sidebar:
        st.markdown("### 🎬 3 Soru 3 Dakika")
        st.markdown("---")
        st.markdown('<p class="sct">🔑 ElevenLabs API</p>', unsafe_allow_html=True)
        key = st.text_input("API Anahtari", type="password", placeholder="xi-...")
        api = None
        if key:
            if st.button("Baglan", use_container_width=True):
                el = ElevenLabsAPI(key)
                ok, msg = el.check()
                st.session_state.api_ok = ok
                st.success(f"✅ {msg}") if ok else st.error(f"❌ {msg}")
                if not ok: key = None
            if st.session_state.api_ok:
                api = ElevenLabsAPI(key)

        st.markdown("---")
        st.markdown('<p class="sct">Ses Ayarlari</p>', unsafe_allow_html=True)
        stab = st.slider("Kararlilik", 0.0, 1.0, 0.50, 0.05)
        sim  = st.slider("Benzerlik",  0.0, 1.0, 0.75, 0.05)

        st.markdown("---")
        st.markdown('<p class="sct">Video FPS</p>', unsafe_allow_html=True)
        fps = st.select_slider("FPS", [15, 24, 30], value=30)
        VIDEO_CONFIG["fps"] = fps

        st.markdown("---")
        st.markdown('<p class="sct">Karakterler</p>', unsafe_allow_html=True)
        for ch, info in CHARACTERS.items():
            vid = VOICE_IDS.get(ch, "")
            ok  = bool(vid and vid not in ("KENDI_SES_ID_BURAYA", ""))
            st.markdown(f"{'🟢' if ok else '🔴'} {info['emoji']} **{ch}**")

        if api and st.button("Sesleri Listele", use_container_width=True):
            vs = api.list_voices()
            if vs:
                for v in vs[:12]:
                    st.code(f"{v['name']}\n{v['voice_id']}", language=None)
            else:
                st.info("Ses bulunamadi.")

        st.markdown("---")
        st.caption("v2.0 | Ses + Animasyon + Video")

    return api, stab, sim


# ============================================================
# 10. AUDIO GENERATION
# ============================================================

def gen_audio(segs, api, stab, sim):
    out  = []
    n    = len(segs)
    pb   = st.progress(0, "Sesler hazirlaniyor...")
    ph   = st.empty()
    for i, seg in enumerate(segs):
        ch  = seg["character"]
        vid = VOICE_IDS.get(ch, "")
        ph.markdown(f'🎙️ **{seg["info"]["emoji"]} {ch}** seslendiriliyor... ({i+1}/{n})')
        if not vid or vid in ("KENDI_SES_ID_BURAYA", ""):
            out.append({**seg, "audio": None, "duration": 3.0})
        else:
            audio = api.tts(seg["text"], vid, stab, sim)
            dur   = ElevenLabsAPI.audio_duration(audio) if audio else 3.0
            out.append({**seg, "audio": audio, "duration": dur})
            time.sleep(0.5)
        pb.progress((i+1)/n, f"{i+1}/{n} tamamlandi")
    ph.success(f"✅ {n} segment tamamlandi!")
    return out


# ============================================================
# 11. MAIN
# ============================================================

def main():
    st.set_page_config(
        page_title="3 Soru 3 Dakika",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    init()
    api, stab, sim = sidebar()

    st.markdown(
        '<div class="hdr"><h1>🎬 3 Soru 3 Dakika</h1>'
        '<p>Kendi sesinizle animasyonlu slaytlar ve MP4 video olusturun</p></div>',
        unsafe_allow_html=True,
    )

    t1, t2, t3 = st.tabs(["✏️ Senaryo & Ses", "🖥️ Canli Sunum", "🎞️ Video"])

    # ── TAB 1 ──────────────────────────────────────────────
    with t1:
        col1, col2 = st.columns([1, 1], gap="large")

        with col1:
            st.markdown('<p class="sct">Hazir Sablonlar</p>', unsafe_allow_html=True)
            tc = st.columns(3)
            for idx, (lbl, content) in enumerate(TEMPLATES.items()):
                with tc[idx % 3]:
                    if st.button(lbl, use_container_width=True):
                        st.session_state["_tpl"] = content

            script = st.text_area(
                "Senaryo",
                value=st.session_state.get("_tpl", ""),
                height=380,
                placeholder="Sunucu: Merhaba!\nKonuk: Hos geldiniz!\nDis Ses: Bugun...",
                label_visibility="collapsed",
            )

            if script.strip():
                parser = ScriptParser()
                segs   = parser.parse(script)
                wc     = parser.wc(script)
                dur    = parser.dur(wc)
                chars  = list({s["character"] for s in segs})
                st.markdown(
                    f'<div class="sr"><span>📊 <strong>{wc}</strong> kelime</span>'
                    f'<span>⏱️ ~<strong>{dur}</strong></span>'
                    f'<span>💬 <strong>{len(segs)}</strong> satir</span>'
                    f'<span>🎭 <strong>{len(chars)}</strong> karakter</span></div>',
                    unsafe_allow_html=True,
                )
                st.session_state.segs = segs

        with col2:
            st.markdown('<p class="sct">Onizleme</p>', unsafe_allow_html=True)
            st.markdown(voice_status_html(), unsafe_allow_html=True)
            st.markdown("---")

            for s in st.session_state.segs:
                seg_card(s)

            st.markdown("---")
            b1, b2 = st.columns(2)
            gen_btn = b1.button("🚀 Sesleri Olustur", use_container_width=True, type="primary")
            clr_btn = b2.button("🗑️ Temizle",        use_container_width=True)

            if clr_btn:
                for k in ("segs","audio_segs","full_audio","pres_html"):
                    st.session_state[k] = [] if k in ("segs","audio_segs") else (None if k=="full_audio" else "")
                if "_tpl" in st.session_state: del st.session_state["_tpl"]
                st.rerun()

            if gen_btn:
                if not api:
                    st.error("API baglantisi yok.")
                elif not script.strip():
                    st.warning("Senaryo bos.")
                else:
                    parser = ScriptParser()
                    segs   = parser.parse(script)
                    st.session_state.segs = segs
                    asegs  = gen_audio(segs, api, stab, sim)
                    st.session_state.audio_segs  = asegs
                    combined = b"".join(s["audio"] for s in asegs if s.get("audio"))
                    st.session_state.full_audio   = combined or None
                    st.session_state.pres_html    = build_slide_html(segs)
                    st.session_state.history.append(
                        {"preview": script[:55]+"...", "n": len(segs)}
                    )
                    st.rerun()

            # segment player
            if st.session_state.audio_segs:
                st.markdown('<p class="sct">Segment Oynatici</p>', unsafe_allow_html=True)
                for seg in st.session_state.audio_segs:
                    with st.expander(
                        f"{seg['info']['emoji']} {seg['character']}: {seg['text'][:48]}...",
                        expanded=False,
                    ):
                        if seg.get("audio"):
                            st.audio(seg["audio"], format="audio/mp3")
                            st.caption(f"~{seg['duration']:.1f} sn")
                        else:
                            st.caption("Ses üretilemedi (voice ID eksik?)")

                if st.session_state.full_audio:
                    st.markdown("---")
                    st.audio(st.session_state.full_audio, format="audio/mp3")
                    st.download_button(
                        "⬇️ Tam Ses MP3",
                        st.session_state.full_audio,
                        "podcast.mp3", "audio/mpeg",
                        use_container_width=True,
                    )

    # ── TAB 2 ──────────────────────────────────────────────
    with t2:
        if not st.session_state.segs:
            st.info("Senaryo girin ve onizleyin.")
        else:
            if not st.session_state.pres_html:
                st.session_state.pres_html = build_slide_html(st.session_state.segs)

            st.markdown("### Animasyonlu Slayt Sunumu")
            st.components.v1.html(st.session_state.pres_html, height=620, scrolling=False)

            st.markdown("---")
            st.caption("◀ ▶ ile gezinin | ▶ Oynat ile otomatik slayt gosterisi baslatin")

            if st.session_state.full_audio:
                st.markdown('<p class="sct">Ses Esligi</p>', unsafe_allow_html=True)
                st.caption("Sunumu Oynat konumuna getirin, ardindan sesi baslatin.")
                st.audio(st.session_state.full_audio, format="audio/mp3")

    # ── TAB 3 ──────────────────────────────────────────────
    with t3:
        st.markdown("### MP4 Video Olusturucu")

        vm = VideoMaker()

        missing = []
        if not vm.has_pil:
            missing.append("`pip install Pillow`")
        if not vm.has_ffmpeg:
            missing.append("FFmpeg kurulumu: https://ffmpeg.org")

        if missing:
            st.warning("Video olusturmak icin su adimlar gerekli:\n\n" + "\n\n".join(missing))

        if vm.ready() and st.session_state.audio_segs:
            total_dur = sum(s.get("duration", 3) for s in st.session_state.audio_segs)
            st.info(
                f"**{len(st.session_state.audio_segs)}** segment hazir — "
                f"Tahmini süre: **{total_dur:.1f} sn**"
            )

            if st.button("🎬 Video Olustur", type="primary", use_container_width=True):
                sph = st.empty()
                pph = st.progress(0)

                def cb(v, m):
                    pph.progress(v, m)
                    sph.markdown(f"⚙️ {m}")

                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                    op = tmp.name

                ok = vm.make(st.session_state.audio_segs, op, cb)

                if ok and os.path.exists(op):
                    with open(op, "rb") as f:
                        vb = f.read()
                    os.unlink(op)
                    st.success("✅ Video hazir!")
                    st.video(vb)
                    st.download_button(
                        "⬇️ MP4 Indir", vb,
                        "3soru3dakika.mp4", "video/mp4",
                        use_container_width=True,
                    )
                else:
                    st.error("Video olusturulamadi. FFmpeg kurulu mu?")

        elif not st.session_state.audio_segs:
            st.info("Once Senaryo & Ses sekmesinde sesleri olusturun.")

        if st.session_state.history:
            st.markdown("---")
            st.markdown('<p class="sct">Gecmis</p>', unsafe_allow_html=True)
            for h in reversed(st.session_state.history[-5:]):
                st.markdown(f"🎬 *{h['preview']}* — {h['n']} satir")


if __name__ == "__main__":
    main()
