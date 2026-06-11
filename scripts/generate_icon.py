"""Generate a network monitor app icon.

Creates a 1024x1024 PNG icon with a network/signal theme,
then generates all required sizes for .icns format.
"""

import os, subprocess, struct, shutil
from PIL import Image, ImageDraw, ImageFont


def create_icon_png(size=1024):
    """Create a network monitor icon at the given size."""
    img = Image.new('RGBA', (size, size), (13, 17, 23, 255))  # #0d1117
    draw = ImageDraw.Draw(img)

    cx = cy = size // 2
    # Line widths / sizes scaled to size
    r = size * 0.38
    gap = 180 if size > 200 else 120

    # === Grid rings (faint) ===
    ring_colors = [
        (48, 54, 61, 80),   # outer
        (48, 54, 61, 100),
        (48, 54, 61, 130),
    ]
    for i, color in enumerate(ring_colors):
        radius = r * (i + 1) / 3
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            outline=color, width=max(2, size // 150)
        )

    # === Crosshair lines ===
    for angle in [0, 60, 120]:
        rad = angle * 3.14159 / 180
        x = cx + r * 0.95 * __import__('math').cos(rad)
        y = cy + r * 0.95 * __import__('math').sin(rad)
        draw.line([(cx, cy), (x, y)], fill=(48, 54, 61, 120), width=max(1, size // 200))

    # === Network nodes (dots connected by lines) ===
    import math, random
    random.seed(42)  # deterministic

    # Position nodes
    nodes = []
    angles = sorted([random.random() * 360 for _ in range(7)])
    for i, a in enumerate(angles):
        rad = a * math.pi / 180
        dist = r * (0.25 + random.random() * 0.55)
        nx = cx + dist * math.cos(rad)
        ny = cy + dist * math.sin(rad)
        online = random.random() > 0.2
        nodes.append({'x': nx, 'y': ny, 'online': online})

    # Add center hub
    nodes.insert(0, {'x': cx, 'y': cy, 'online': True})

    # Draw connection lines
    for i, n1 in enumerate(nodes):
        for j, n2 in enumerate(nodes):
            if j <= i:
                continue
            dx = n1['x'] - n2['x']
            dy = n1['y'] - n2['y']
            dist = math.sqrt(dx*dx + dy*dy)
            if dist < r * 0.65 and random.random() > 0.4:
                if n1['online'] and n2['online']:
                    line_color = (63, 185, 80, int(160 * (1 - dist / r)))
                else:
                    line_color = (139, 148, 158, 60)
                draw.line(
                    [(n1['x'], n1['y']), (n2['x'], n2['y'])],
                    fill=line_color, width=max(1, size // 200)
                )

    # Draw device nodes
    for node in nodes:
        if node['online']:
            color = (63, 185, 80)  # green
            fill = (13, 17, 23)
            dot_r = max(6, size // 45)
        else:
            color = (139, 148, 158)
            fill = (48, 54, 61)
            dot_r = max(4, size // 55)

        # Glow for online nodes
        if node['online'] and node != nodes[0]:
            for g in range(3, 0, -1):
                glow_r = dot_r + g * max(3, size // 80)
                alpha = 30 - g * 8
                draw.ellipse(
                    [node['x'] - glow_r, node['y'] - glow_r,
                     node['x'] + glow_r, node['y'] + glow_r],
                    fill=(63, 185, 80, alpha) if alpha > 0 else None
                )

        # Dot
        draw.ellipse(
            [node['x'] - dot_r, node['y'] - dot_r,
             node['x'] + dot_r, node['y'] + dot_r],
            fill=color, outline=(255, 255, 255, 40) if node['online'] else None
        )

    # Center hub (larger, with pulsing look)
    hub_r = max(10, size // 25)
    for g in range(4, 0, -1):
        glow_r = hub_r + g * max(4, size // 60)
        draw.ellipse(
            [cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r],
            fill=(88, 166, 255, 25 - g * 5)
        )
    draw.ellipse(
        [cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r],
        fill=(88, 166, 255), outline=(255, 255, 255, 60)
    )

    # === Bottom label ===
    label_y = int(size * 0.88)
    try:
        # Try to load a font; fall back to default
        font = ImageFont.truetype("/System/Library/Fonts/SFNSDisplay.ttf", max(14, size // 18))
    except (IOError, OSError):
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", max(14, size // 18))
        except (IOError, OSError):
            font = ImageFont.load_default()

    draw.text((cx, label_y), "NETMON", fill=(139, 148, 158, 200),
              font=font, anchor="mm")

    return img


def create_iconset(source_png, output_dir):
    """Create an iconset directory from a source PNG."""
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    sizes = {
        "icon_16x16": 16, "icon_16x16@2x": 32,
        "icon_32x32": 32, "icon_32x32@2x": 64,
        "icon_128x128": 128, "icon_128x128@2x": 256,
        "icon_256x256": 256, "icon_256x256@2x": 512,
        "icon_512x512": 512, "icon_512x512@2x": 1024,
    }

    for name, size in sizes.items():
        resized = source_png.resize((size, size), Image.LANCZOS)
        out_path = os.path.join(output_dir, f"{name}.png")
        resized.save(out_path, "PNG")
        print(f"  🖼️  {name}.png  ({size}x{size})")

    return output_dir


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    resources_dir = os.path.join(project_root, "NetworkMonitor.app", "Contents", "Resources")

    print("🎨 生成网络监控图标...")
    # Create the high-res source
    img_1024 = create_icon_png(1024)
    src_path = os.path.join(resources_dir, "icon_source.png")
    img_1024.save(src_path, "PNG")
    print(f"  ✅ 源图标: {src_path}")

    # Create iconset
    iconset_dir = os.path.join(resources_dir, "NetworkMonitor.iconset")
    create_iconset(img_1024, iconset_dir)

    # Convert to .icns
    icns_path = os.path.join(resources_dir, "icon.icns")
    subprocess.run([
        "iconutil", "-c", "icns", iconset_dir,
        "-o", icns_path
    ], check=True)
    print(f"  ✅ .icns: {icns_path}")

    # Cleanup
    os.remove(src_path)
    shutil.rmtree(iconset_dir)
    print(f"\n🎉 图标生成完成!")


if __name__ == "__main__":
    main()
