"""A tiny one-page PDF (no extra dependency) used as the example company presentation in the
demo data. Text in WinAnsi so pt-BR accents render with the standard Helvetica font."""

from __future__ import annotations

import textwrap


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _enc(text: str) -> bytes:
    return text.encode("cp1252", errors="replace")


def presentation_pdf(
    company: str, segment: str, city: str, description: str, offers: list[str]
) -> bytes:
    lines: list[tuple[str, int, str]] = [  # (font, size, text)
        ("F2", 26, company),
        ("F1", 13, f"{segment} · {city}" if city else segment),
        ("F1", 11, ""),
        ("F2", 14, "Quem somos"),
    ]
    for chunk in textwrap.wrap(description or "Apresentação institucional.", 88):
        lines.append(("F1", 11, chunk))
    if offers:
        lines += [("F1", 11, ""), ("F2", 14, "O que oferecemos")]
        lines += [("F1", 11, f"• {o}") for o in offers[:8]]
    lines += [("F1", 11, ""), ("F1", 9, "Apresentação de exemplo · VIP Network")]

    y = 760
    ops = ["BT", "0.043 0.086 0.188 rg"]
    for font, size, text in lines:
        ops.append(f"/{font} {size} Tf 56 {y} Td ({_esc(text)}) Tj 0 0 Td")
        ops.append(f"-56 {-y} Td")
        y -= int(size * 1.6) if text else 10
    ops.append("ET")
    # a gold bar at the top
    stream = _enc("0.788 0.631 0.29 rg 0 800 612 42 re f\n" + "\n".join(ops))

    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def logo_png(name: str, initials: str, color: str) -> bytes:
    """Example logo for the demo companies: a rounded badge in the company colour with its
    initials and the name below (transparent background)."""
    import io

    from PIL import Image, ImageDraw, ImageFont

    def font(size: int) -> ImageFont.ImageFont:
        for f in (
            "arialbd.ttf",
            "Arial Bold.ttf",
            "DejaVuSans-Bold.ttf",
            "LiberationSans-Bold.ttf",
        ):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                continue
        return ImageFont.load_default(size=size)

    img = Image.new("RGBA", (640, 640), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((150, 40, 490, 380), radius=84, fill=color)
    d.rounded_rectangle((170, 330, 470, 350), radius=10, fill=(201, 161, 74, 255))
    f_big = font(150)
    w = d.textlength(initials, font=f_big)
    d.text(((640 - w) / 2, 105), initials, font=f_big, fill="white")
    words = name.split()
    line1 = " ".join(words[:2]) if len(" ".join(words[:2])) <= 18 else words[0]
    line2 = " ".join(words[len(line1.split()) :])[:22]
    for i, text in enumerate([line1, line2]):
        if not text:
            continue
        f = font(54 if i == 0 else 40)
        tw = d.textlength(text, font=f)
        d.text(
            ((640 - tw) / 2, 420 + i * 72),
            text,
            font=f,
            fill=(14, 25, 48, 255) if i == 0 else (93, 103, 128, 255),
        )
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
