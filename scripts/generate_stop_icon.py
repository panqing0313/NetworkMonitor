"""Generate stop icon for the Quit app."""
import os, subprocess, shutil
from PIL import Image, ImageDraw, ImageFont


def create_stop_icon(size=512):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    cx = cy = size // 2
    r = size * 0.42
    
    # Outer circle
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], 
                 fill=(248, 81, 73),  # red
                 outline=(255, 255, 255, 60), width=max(2, size // 80))
    
    # Inner white square (stop icon)
    sq = size * 0.22
    draw.rounded_rectangle(
        [cx - sq, cy - sq, cx + sq, cy + sq],
        radius=max(4, size // 30),
        fill=(255, 255, 255, 240)
    )
    
    # Label
    try:
        font = ImageFont.truetype("/System/Library/Fonts/SFNSDisplay.ttf", max(12, size // 16))
    except:
        font = ImageFont.load_default()
    draw.text((cx, int(size * 0.85)), "QUIT", fill=(248, 81, 73, 180), font=font, anchor="mm")
    
    return img


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    resources_dir = os.path.join(project_root, "stop.app", "Contents", "Resources")
    os.makedirs(resources_dir, exist_ok=True)
    
    img = create_stop_icon(1024)
    src = os.path.join(resources_dir, "source.png")
    img.save(src)
    
    iconset = os.path.join(resources_dir, "stop.iconset")
    os.makedirs(iconset, exist_ok=True)
    
    sizes = {
        "icon_16x16": 16, "icon_16x16@2x": 32,
        "icon_32x32": 32, "icon_32x32@2x": 64,
        "icon_128x128": 128, "icon_128x128@2x": 256,
        "icon_256x256": 256, "icon_256x256@2x": 512,
        "icon_512x512": 512, "icon_512x512@2x": 1024,
    }
    for name, s in sizes.items():
        resized = img.resize((s, s), Image.LANCZOS)
        resized.save(os.path.join(iconset, f"{name}.png"))
    
    icns = os.path.join(resources_dir, "stop_icon.icns")
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns], check=True)
    
    os.remove(src)
    shutil.rmtree(iconset)
    print(f"✅ Stop icon: {icns}")


if __name__ == "__main__":
    main()
