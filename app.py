"""
PPTX + Ses -> Senkronize MP4 | v6.2 | Streamlit Cloud uyumlu
Widget key prefix: wu_   Session state prefix: ss_   HICBIR KEY CAKISMASI YOK
"""

import streamlit as st
import io, os, math, base64, tempfile, subprocess, shutil
import numpy as np

# ── Bundled ffmpeg ─────────────────────────────────────────────────────────
def _get_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

FFMPEG = _get_ffmpeg()
os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import imageio.v3 as iio
    IMAGEIO_OK = True
except ImportError:
    IMAGEIO_OK = False

try:
    from pptx import Presentation
    PPTX_OK = True
except ImportError:
    PPTX_OK = False

LO_OK  = os.path.exists("/usr/bin/libreoffice") or os.path.exists("/usr/bin/soffice")
PPM_OK = os.path.exists("/usr/bin/pdftoppm")

VIDEO_W, VIDEO_H, VIDEO_FPS = 1280, 720, 24
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
]


def _font(size):
    if not PIL_OK:
        return None
    for p in FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def audio_duration_sec(data):
    if not data:
        return 3.0
    return max(1.0, len(data) / 16_000)


def pptx_to_images(pptx_bytes):
    tmp = tempfile.mkdtemp()
    try:
        pptx_path = os.path.join(tmp, "pres.pptx")
        with open(pptx_path, "wb") as f:
            f.write(pptx_bytes)
        r = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmp, pptx_path],
            capture_output=True, text=True, timeout=90,
        )
        pdfs = [f for f in os.listdir(tmp) if f.endswith(".pdf")]
        if not pdfs:
            raise RuntimeError(f"LibreOffice basarisiz:\n{r.stderr[:300]}")
        pdf_path = os.path.join(tmp, pdfs[0])
        img_prefix = os.path.join(tmp, "sl")
        subprocess.run(["pdftoppm", "-jpeg", "-r", "150", pdf_path, img_prefix],
                       capture_output=True, timeout=60)
        files = sorted([os.path.join(tmp, f) for f in os.listdir(tmp)
                        if f.startswith("sl") and f.endswith(".jpg")])
        if not files:
            raise RuntimeError("Slayt goruntuleri uretilemedi.")
        return [Image.open(p).convert("RGB").resize((VIDEO_W, VIDEO_H), Image.LANCZOS) for p in files]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def read_pptx_notes(pptx_bytes):
    prs = Presentation(io.BytesIO(pptx_bytes))
    notes = []
    for slide in prs.slides:
        txt = ""
        try:
            txt = slide.notes_slide.notes_text_frame.text.strip()
        except Exception:
            pass
        notes.append(txt)
    return notes


def render_frame(slide_img, slide_idx, total, t, has_audio):
    frame = slide_img.copy()
    draw = ImageDraw.Draw(frame)
    w, h = frame.size
    prog_w = int(w * (slide_idx + t) / max(total, 1))
    draw.rectangle([0, h - 5, w, h], fill=(18, 18, 36))
    draw.rectangle([0, h - 5, prog_w, h], fill=(201, 168, 76))
    fn = _font(14)
    draw.text((w - 90, h - 28), f"{slide_idx+1} / {total}", font=fn, fill=(190, 190, 210))
    if has_audio:
        bc, bw, bg = 9, 6, 4
        bx0 = w - bc * (bw + bg) - 14
        by = h - 8
        for bi in range(bc):
            bh = int(5 + 20 * abs(math.sin(t * math.pi * 3.5 + bi * 0.8)))
            bx = bx0 + bi * (bw + bg)
            draw.rounded_rectangle([bx, by - bh, bx + bw, by], radius=2, fill=(201, 168, 76))
    return np.array(frame)


def build_video(slide_images, audio_list, durations, cb=None):
    all_frames = []
    all_audio = b""
    n = len(slide_images)
    total_f = sum(max(1, int(d * VIDEO_FPS)) for d in durations)
    done = 0
    for idx, (img, aud, dur) in enumerate(zip(slide_images, audio_list, durations)):
        nf = max(VIDEO_FPS, int(dur * VIDEO_FPS))
        all_audio += (aud or b"")
        for fi in range(nf):
            t = fi / max(nf - 1, 1)
            all_frames.append(render_frame(img, idx, n, t, bool(aud)))
            done += 1
            if cb and done % 10 == 0:
                cb(done / total_f * 0.74, f"Kare {done}/{total_f}")
    if cb:
        cb(0.76, "Video kodlaniyor...")
    tmp_v = tempfile.mktemp(suffix=".mp4")
    tmp_a = tempfile.mktemp(suffix=".mp3")
    tmp_f = tempfile.mktemp(suffix="_out.mp4")
    iio.imwrite(tmp_v, all_frames, fps=VIDEO_FPS, codec="libx264",
                output_params=["-crf", "22", "-preset", "fast", "-pix_fmt", "yuv420p"],
                plugin="FFMPEG")
    if cb:
        cb(0.88, "Ses ekleniyor...")
    if all_audio and len(all_audio) > 256:
        with open(tmp_a, "wb") as f:
            f.write(all_audio)
        cmd = [FFMPEG, "-y", "-i", tmp_v, "-i", tmp_a, "-c:v", "copy",
               "-c:a", "aac", "-b:a", "128k", "-shortest", tmp_f]
    else:
        cmd = [FFMPEG, "-y", "-i", tmp_v, "-c:v", "copy", tmp_f]
    subprocess.run(cmd, capture_output=True, timeout=300)
    for p in [tmp_v, tmp_a]:
        try:
            os.unlink(p)
        except Exception:
            pass
    if cb:
        cb(1.0, "Tamamlandi!")
    if os.path.exists(tmp_f):
        data = open(tmp_f, "rb").read()
        os.unlink(tmp_f)
        return data
    raise RuntimeError("MP4 olusturulamadi.")


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;600;700&display=swap');
:root{--gold:#C9A84C;--border:rgba(201,168,76,.18);}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.stApp{background:radial-gradient(ellipse at 20% 40%,#0d1525 0%,#06060f 65%);color:#e8e8f0;}
section[data-testid="stSidebar"]{background:rgba(6,6,18,.97);border-right:1px solid var(--border);}
.ph{text-align:center;padding:1.6rem 1rem 1rem;border-bottom:1px solid var(--border);margin-bottom:1.2rem;}
.ph h1{font-family:'DM Serif Display',serif;font-size:2.2rem;
  background:linear-gradient(90deg,#C9A84C,#f0d080,#C9A84C);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin:0 0 .2rem;}
.ph p{color:#556;font-size:.8rem;letter-spacing:.12em;text-transform:uppercase;}
.lbl{font-size:.62rem;letter-spacing:.16em;text-transform:uppercase;color:#445;margin:.9rem 0 .3rem;}
.scard{display:flex;align-items:flex-start;gap:.7rem;padding:.7rem .9rem;margin:.3rem 0;
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:10px;}
.snum{font-size:1rem;font-weight:700;color:var(--gold);min-width:1.8rem;padding-top:.1rem;}
.snote{font-size:.84rem;color:#aab;line-height:1.55;}
.srow{display:flex;gap:1rem;flex-wrap:wrap;padding:.5rem .85rem;margin:.5rem 0;
  background:rgba(201,168,76,.06);border:1px solid var(--border);border-radius:8px;
  font-size:.78rem;color:#778;}
.srow strong{color:var(--gold);}
.dep{font-size:.72rem;margin:.12rem 0;}
.ok{color:#7ec878;}.er{color:#e07b7b;}
audio{width:100%;border-radius:7px;margin:2px 0;}
.stProgress>div>div{border-radius:10px;}
hr{border-color:rgba(255,255,255,.06);}
</style>
"""


def init_state():
    defaults = {
        "ss_pptx_bytes":   None,
        "ss_slide_notes":  [],
        "ss_slide_images": [],
        "ss_audio_map":    {},
        "ss_global_audio": None,
        "ss_durations":    {},
        "ss_use_global":   True,
        "ss_video_bytes":  None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def render_sidebar():
    with st.sidebar:
        st.markdown(
            '<div style="text-align:center;padding:.8rem 0 .4rem;">'            '<div style="font-family:serif;font-size:1.15rem;color:#C9A84C;letter-spacing:.1em;">🎬 VIDEO STUDYO</div>'            '<div style="font-size:.62rem;color:#445;letter-spacing:.14em;text-transform:uppercase;margin-top:3px;">PPTX + Ses → MP4</div>'            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown('<p class="lbl">Sistem Durumu</p>', unsafe_allow_html=True)
        checks = [
            ("Pillow",      PIL_OK),
            ("imageio",     IMAGEIO_OK),
            ("python-pptx", PPTX_OK),
            ("LibreOffice", LO_OK),
            ("pdftoppm",    PPM_OK),
            ("ffmpeg",      True),
        ]
        for name, ok in checks:
            cls = "ok" if ok else "er"
            st.markdown(f'<div class="dep {cls}">{"🟢" if ok else "🔴"} {name}</div>',
                        unsafe_allow_html=True)
        if not LO_OK or not PPM_OK:
            st.caption("packages.txt:\n`libreoffice`\n`poppler-utils`")
        st.markdown("---")
        st.caption("v6.2")


def main():
    st.set_page_config(page_title="PPTX → MP4", page_icon="🎬", layout="wide",
                       initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    render_sidebar()

    st.markdown(
        '<div class="ph"><h1>🎬 PPTX + Ses → MP4</h1>'        '<p>PowerPoint sunumunuzu yukleyin · Ses ekleyin · Senkronize video alin</p></div>',
        unsafe_allow_html=True,
    )

    # ── ADIM 1: PPTX ─────────────────────────────────────────────────────────
    st.markdown('<p class="lbl">① PowerPoint Dosyasi</p>', unsafe_allow_html=True)
    col_a, col_b = st.columns([1, 1], gap="large")

    with col_a:
        pptx_file = st.file_uploader(
            "PPTX dosyasi", type=["pptx"], key="wu_pptx_file",
            label_visibility="collapsed",
        )
        if pptx_file is not None:
            raw = pptx_file.read()
            if raw != st.session_state.ss_pptx_bytes:
                st.session_state.ss_pptx_bytes   = raw
                st.session_state.ss_slide_images  = []
                st.session_state.ss_video_bytes   = None
                st.session_state.ss_audio_map     = {}
                st.session_state.ss_durations     = {}
                with st.spinner("PPTX okunuyor..."):
                    try:
                        st.session_state.ss_slide_notes = read_pptx_notes(raw)
                    except Exception as e:
                        st.error(f"PPTX okunamadi: {e}")
                        st.session_state.ss_slide_notes = []

        if st.session_state.ss_pptx_bytes:
            n = len(st.session_state.ss_slide_notes)
            st.success(f"Yuklendi — **{n}** slayt")

    with col_b:
        notes = st.session_state.ss_slide_notes
        if notes:
            st.markdown(f'<div class="srow"><span>📊 <strong>{len(notes)}</strong> slayt</span></div>',
                        unsafe_allow_html=True)
            for i, note in enumerate(notes[:5]):
                preview = (note[:85] + "…") if len(note) > 85 else (note or "—")
                st.markdown(
                    f'<div class="scard"><div class="snum">{i+1}</div>'                    f'<div class="snote">{preview}</div></div>',
                    unsafe_allow_html=True,
                )
            if len(notes) > 5:
                st.caption(f"...ve {len(notes)-5} slayt daha")

    st.markdown("---")

    # ── ADIM 2: SES ──────────────────────────────────────────────────────────
    st.markdown('<p class="lbl">② Ses Dosyalari</p>', unsafe_allow_html=True)

    if not st.session_state.ss_slide_notes:
        st.info("Once PPTX dosyasi yukleyin.")
    else:
        n_slides = len(st.session_state.ss_slide_notes)

        mode = st.radio(
            "Ses modu", ["🔊 Tek ses — tum sunuma", "🎙️ Her slayta ayri ses"],
            key="wu_mode_radio", horizontal=True, label_visibility="collapsed",
        )
        use_global = mode.startswith("🔊")
        st.session_state.ss_use_global = use_global

        if use_global:
            st.caption("Tek bir ses dosyasi yukleyin. Ses slaytlara otomatik bolunur.")
            gf = st.file_uploader(
                "Genel ses", type=["mp3", "wav", "m4a", "ogg"],
                key="wu_glob_upload", label_visibility="collapsed",
            )
            if gf is not None:
                ab = gf.read()
                st.session_state.ss_global_audio = ab
                total_dur = audio_duration_sec(ab)
                per_slide = total_dur / n_slides
                for i in range(n_slides):
                    st.session_state.ss_durations[i] = per_slide
                st.audio(ab, format="audio/mp3")
                st.caption(f"Toplam: ~{total_dur:.1f} sn  —  Slayt basi: ~{per_slide:.1f} sn")
        else:
            st.caption("Her slayt icin ayri ses dosyasi yukleyin.")
            per_row = min(n_slides, 4)
            col_grids = [st.columns(per_row) for _ in range(math.ceil(n_slides / per_row))]
            for i in range(n_slides):
                row, col = i // per_row, i % per_row
                with col_grids[row][col]:
                    st.markdown(f"**Slayt {i+1}**")
                    uf = st.file_uploader(
                        f"Slayt {i+1}", type=["mp3", "wav", "m4a", "ogg"],
                        key=f"wu_sl_{i}", label_visibility="collapsed",
                    )
                    if uf is not None:
                        ab = uf.read()
                        st.session_state.ss_audio_map[i] = ab
                        dur = audio_duration_sec(ab)
                        st.session_state.ss_durations[i] = dur
                        st.audio(ab, format="audio/mp3")
                        st.caption(f"~{dur:.1f} sn")
                    else:
                        if i not in st.session_state.ss_durations:
                            st.session_state.ss_durations[i] = 3.0
                        st.caption(f"Ses yok → {st.session_state.ss_durations[i]:.0f} sn")

        with st.expander("⚙️ Slayt surelerini manuel ayarla (opsiyonel)"):
            per_row2 = min(n_slides, 5)
            dur_grids = [st.columns(per_row2) for _ in range(math.ceil(n_slides / per_row2))]
            for i in range(n_slides):
                row, col = i // per_row2, i % per_row2
                with dur_grids[row][col]:
                    default = float(st.session_state.ss_durations.get(i, 3.0))
                    d = st.number_input(f"S{i+1} (sn)", min_value=0.5, max_value=120.0,
                                        value=default, step=0.5, key=f"wu_dur_{i}")
                    st.session_state.ss_durations[i] = d

    st.markdown("---")

    # ── ADIM 3: VIDEO ─────────────────────────────────────────────────────────
    st.markdown('<p class="lbl">③ Video Olustur</p>', unsafe_allow_html=True)

    can_go = (st.session_state.ss_pptx_bytes is not None
              and PIL_OK and IMAGEIO_OK and PPTX_OK and LO_OK and PPM_OK)

    if not can_go:
        if not st.session_state.ss_pptx_bytes:
            st.info("Once PPTX dosyasi yukleyin.")
        else:
            miss = [n for n, ok in [("Pillow", PIL_OK), ("imageio", IMAGEIO_OK),
                                     ("python-pptx", PPTX_OK), ("libreoffice", LO_OK),
                                     ("poppler-utils", PPM_OK)] if not ok]
            st.error("Eksik bagimlilik: " + ", ".join(miss))
    else:
        n_slides = len(st.session_state.ss_slide_notes)
        total_secs = sum(st.session_state.ss_durations.get(i, 3.0) for i in range(n_slides))
        mins, secs = divmod(int(total_secs), 60)
        st.markdown(
            f'<div class="srow">'            f'<span>🎞️ <strong>{n_slides}</strong> slayt</span>'            f'<span>⏱️ ~<strong>{mins}:{secs:02d}</strong></span>'            f'<span>📐 <strong>{VIDEO_W}x{VIDEO_H}</strong></span>'            f'<span>🎬 <strong>{VIDEO_FPS} FPS</strong></span>'            f'</div>', unsafe_allow_html=True,
        )
        c1, c2 = st.columns([3, 1])
        with c1:
            make_btn = st.button("🎬 Video Olustur", type="primary",
                                 use_container_width=True, key="wu_btn_make",
                                 disabled=(st.session_state.ss_video_bytes is not None))
        with c2:
            if st.button("🔄 Sifirla", use_container_width=True, key="wu_btn_reset"):
                st.session_state.ss_video_bytes = None
                st.rerun()

        if make_btn:
            prog = st.progress(0)
            stat = st.empty()

            def cb(pct, msg):
                prog.progress(min(float(pct), 1.0), msg)
                stat.markdown(f"⚙️ {msg}")

            try:
                cb(0.02, "Slaytlar isleniyor... (LibreOffice + pdftoppm)")
                slide_imgs = pptx_to_images(st.session_state.ss_pptx_bytes)
                n_actual = len(slide_imgs)
                cb(0.09, "Ses segmentleri hazirlaniyor...")
                global_audio = st.session_state.ss_global_audio
                cur_use_global = st.session_state.ss_use_global
                audio_list, dur_list = [], []
                if cur_use_global and global_audio:
                    chunk = len(global_audio) // n_actual
                    for i in range(n_actual):
                        s = i * chunk
                        e = s + chunk if i < n_actual - 1 else len(global_audio)
                        audio_list.append(global_audio[s:e])
                        dur_list.append(st.session_state.ss_durations.get(i, 3.0))
                else:
                    for i in range(n_actual):
                        audio_list.append(st.session_state.ss_audio_map.get(i))
                        dur_list.append(st.session_state.ss_durations.get(i, 3.0))
                video = build_video(slide_imgs, audio_list, dur_list, cb=cb)
                st.session_state.ss_video_bytes  = video
                st.session_state.ss_slide_images = slide_imgs
            except Exception as e:
                st.error(f"Hata: {e}")
                import traceback
                with st.expander("Detay"):
                    st.code(traceback.format_exc())

        if st.session_state.ss_video_bytes:
            vb = st.session_state.ss_video_bytes
            st.success(f"✅ Video hazir — **{len(vb)//1024:,} KB**")
            st.video(vb)
            st.download_button(
                label="⬇️ MP4 Indir", data=vb, file_name="sunum.mp4",
                mime="video/mp4", use_container_width=True, type="primary",
                key="wu_dl",
            )
            b64 = base64.b64encode(vb).decode()
            st.markdown(
                f'<a href="data:video/mp4;base64,{b64}" download="sunum.mp4" '                f'style="display:block;text-align:center;padding:9px;margin-top:6px;'                f'background:rgba(201,168,76,.12);border:1px solid rgba(201,168,76,.28);'                f'color:#C9A84C;border-radius:8px;font-weight:600;font-size:13px;'                f'text-decoration:none;">📥 Alternatif Indirme Linki</a>',
                unsafe_allow_html=True,
            )
            imgs = st.session_state.ss_slide_images
            if imgs:
                st.markdown("---")
                st.markdown('<p class="lbl">Slayt Onizlemeleri</p>', unsafe_allow_html=True)
                pc = st.columns(min(len(imgs), 4))
                for i, img in enumerate(imgs):
                    with pc[i % 4]:
                        st.image(img, caption=f"Slayt {i+1}", use_container_width=True)


if __name__ == "__main__":
    main()
