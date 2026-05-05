import io
import os
import asyncio
import httpx
import base64
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor

# ================= ADJUSTMENT SETTINGS =================
AVATAR_ZOOM = 1.35
AVATAR_SHIFT_Y = 5
AVATAR_SHIFT_X = 0

BANNER_START_X = 0.20
BANNER_START_Y = 0.25
BANNER_END_X = 0.85
BANNER_END_Y = 0.70
# ======================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await client.aclose()
    process_pool.shutdown()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

INFO_API_URL = "https://mahir-info-api.vercel.app/player-info"

BASE64 = "aHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L2doL1NoYWhHQ3JlYXRvci9pY29uQG1haW4vUE5H"
info_URL = base64.b64decode(BASE64).decode("utf-8")

FONT_FILE = "arial_unicode_bold.otf"
FONT_CHEROKEE = "NotoSansCherokee.ttf"

client = httpx.AsyncClient(
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=10.0,
    follow_redirects=True
)

process_pool = ThreadPoolExecutor(max_workers=4)

# ================= HELPERS =================
def load_unicode_font(size, font_file=FONT_FILE):
    try:
        font_path = os.path.join(os.path.dirname(__file__), font_file)
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
    except:
        pass
    return ImageFont.load_default()

async def fetch_image_bytes(item_id):
    if not item_id or str(item_id) == "0" or str(item_id) == "None":
        return None
    try:
        resp = await client.get(f"{info_URL}/{item_id}.png")
        if resp.status_code == 200:
            return resp.content
    except:
        pass
    return None

def bytes_to_image(img_bytes):
    if img_bytes:
        return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    return Image.new("RGBA", (100, 100), (0, 0, 0, 0))

# ================= IMAGE PROCESS =================
def process_banner_image(data, avatar_bytes, banner_bytes, pin_bytes):
    avatar_img = bytes_to_image(avatar_bytes)
    banner_img = bytes_to_image(banner_bytes)
    pin_img = bytes_to_image(pin_bytes)

    level = str(data.get("level") or "0")
    name = str(data.get("name") or "Unknown")
    guild = str(data.get("guild") or "")

    TARGET_HEIGHT = 550  # Perfect size like 2nd picture

    # Process Avatar with better quality
    zoom_size = int(TARGET_HEIGHT * AVATAR_ZOOM)
    avatar_img = avatar_img.resize((zoom_size, zoom_size), Image.LANCZOS)

    c = zoom_size // 2
    h = TARGET_HEIGHT // 2
    avatar_img = avatar_img.crop((
        c - h - AVATAR_SHIFT_X,
        c - h - AVATAR_SHIFT_Y,
        c + h - AVATAR_SHIFT_X,
        c + h - AVATAR_SHIFT_Y
    ))

    # Process Banner with quality preservation
    banner_img = banner_img.rotate(3, expand=True, resample=Image.BICUBIC)
    bw, bh = banner_img.size
    banner_img = banner_img.crop((
        bw * BANNER_START_X,
        bh * BANNER_START_Y,
        bw * BANNER_END_X,
        bh * BANNER_END_Y
    ))

    bw, bh = banner_img.size
    target_width = int(TARGET_HEIGHT * (bw / bh) * 2)
    banner_img = banner_img.resize((target_width, TARGET_HEIGHT), Image.LANCZOS)

    # Create final image
    final = Image.new("RGBA", (avatar_img.width + banner_img.width, TARGET_HEIGHT))
    final.paste(avatar_img, (0, 0))
    final.paste(banner_img, (avatar_img.width, 0))

    draw = ImageDraw.Draw(final)

    # Better font sizes for clarity
    font_big = load_unicode_font(110)
    font_big_c = load_unicode_font(110, FONT_CHEROKEE)
    font_small = load_unicode_font(75)
    font_small_c = load_unicode_font(75, FONT_CHEROKEE)
    font_lvl = load_unicode_font(55)

    def is_cherokee(c):
        return 0x13A0 <= ord(c) <= 0x13FF or 0xAB70 <= ord(c) <= 0xABBF

    def draw_text(x, y, text, f_main, f_alt, stroke):
        text = text or ""
        cx = x
        for ch in text:
            f = f_alt if is_cherokee(ch) else f_main
            # Thicker stroke for better visibility
            for dx in range(-stroke, stroke + 1):
                for dy in range(-stroke, stroke + 1):
                    draw.text((cx + dx, y + dy), ch, font=f, fill="black")
            draw.text((cx, y), ch, font=f, fill="white")
            cx += f.getlength(ch)

    # Draw text with better positioning (like 2nd picture)
    draw_text(avatar_img.width + 55, 35, name, font_big, font_big_c, 4)
    draw_text(avatar_img.width + 55, 190, guild, font_small, font_small_c, 3)

    # Pin icon positioned like 2nd picture (bottom-left corner)
    if pin_img.size != (100, 100):
        pin_img = pin_img.resize((120, 120), Image.LANCZOS)
        final.paste(pin_img, (15, TARGET_HEIGHT - 130), pin_img)

    # Level badge with better design (like 2nd picture)
    lvl = f"Lv.{level}"
    # Get text dimensions
    bbox = draw.textbbox((0, 0), lvl, font=font_lvl)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Add padding
    padding = 25
    badge_width = text_width + padding * 2
    badge_height = text_height + padding
    
    # Position at bottom-right with margin
    margin = 30
    badge_x = final.width - badge_width - margin
    badge_y = TARGET_HEIGHT - badge_height - margin
    
    # Draw rounded rectangle background (sleek design)
    draw.rectangle(
        [badge_x, badge_y, badge_x + badge_width, badge_y + badge_height],
        fill="black",
        outline=None
    )
    
    # Draw level text centered
    text_x = badge_x + (badge_width - text_width) // 2
    text_y = badge_y + (badge_height - text_height) // 2
    draw.text((text_x, text_y), lvl, font=font_lvl, fill="white")

    out = io.BytesIO()
    final.save(out, "PNG", optimize=False)
    out.seek(0)
    return out

# ================= ROUTES =================
@app.get("/")
async def home():
    return {"status": "Banner API Running", "endpoint": "/banner?uid=UID"}

@app.get("/banner")
async def get_banner(uid: str):
    url = f"{INFO_API_URL}?uid={uid}"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise HTTPException(502, f"Info API returned {resp.status_code}")
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch player info: {str(e)}")

    data = resp.json()

    basic_info = data.get("basicInfo") or {}
    clan_info = data.get("clanBasicInfo") or {}

    name = basic_info.get("nickname")
    level = basic_info.get("level")
    guild = clan_info.get("clanName")
    avatar_id = basic_info.get("headPic")
    banner_id = basic_info.get("bannerId")
    pin_id = basic_info.get("pinId")

    if not name:
        raise HTTPException(404, "Account not found or invalid response from info API")

    avatar, banner, pin = await asyncio.gather(
        fetch_image_bytes(avatar_id),
        fetch_image_bytes(banner_id),
        fetch_image_bytes(pin_id),
    )

    img = await asyncio.get_event_loop().run_in_executor(
        process_pool,
        process_banner_image,
        {
            "level": level,
            "name": name,
            "guild": guild,
        },
        avatar, banner, pin
    )

    return Response(img.getvalue(), media_type="image/png")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
