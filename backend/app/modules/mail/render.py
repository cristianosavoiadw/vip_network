"""Markdown + ``{{ variables }}`` → the HTML and text of an e-mail (same rules as the editor
preview in Admin › E-mails: ``**bold**``, a line with only ``[Text](link)`` is a button)."""

from __future__ import annotations

import html
import re

import markdown as md

from app.core.config import get_settings

VAR = re.compile(r"\{\{\s*(\w+)\s*\}\}")
BUTTON = re.compile(r"^\[([^\]]+)\]\(([^)]*)\)$")

NAVY = "#0B1630"
GOLD = "#C9A14A"


def fill(text: str, variables: dict[str, object], *, escape: bool) -> str:
    def sub(m: re.Match[str]) -> str:
        value = variables.get(m.group(1))
        if value is None:
            return ""
        s = str(value)
        return html.escape(s) if escape else s

    return VAR.sub(sub, text)


def subject(template: str, variables: dict[str, object]) -> str:
    return fill(template, variables, escape=False).strip()[:200]


def _button(label: str, url: str) -> str:
    return (
        f'<p style="margin:22px 0"><a href="{html.escape(url, quote=True)}" '
        f'style="background:{GOLD};color:#1A1306;font-weight:700;padding:12px 22px;'
        f'border-radius:8px;text-decoration:none;display:inline-block">{html.escape(label)}</a></p>'
    )


def body_html(body_md: str, variables: dict[str, object]) -> str:
    parts: list[str] = []
    for block in re.split(r"\n{2,}", body_md.strip()):
        line = block.strip()
        m = BUTTON.match(line)
        if m:
            url = fill(m.group(2), variables, escape=False) or get_settings().frontend_url
            parts.append(_button(fill(m.group(1), variables, escape=False), url))
            continue
        filled = fill(line, variables, escape=True)
        if filled.strip():
            parts.append(md.markdown(filled))
    return "\n".join(parts)


def body_text(body_md: str, variables: dict[str, object]) -> str:
    out: list[str] = []
    for block in re.split(r"\n{2,}", body_md.strip()):
        line = block.strip()
        m = BUTTON.match(line)
        if m:
            url = fill(m.group(2), variables, escape=False)
            out.append(f"{fill(m.group(1), variables, escape=False)}: {url}")
            continue
        text = fill(line, variables, escape=False).replace("**", "")
        if text.strip():
            out.append(text)
    return "\n\n".join(out) + "\n"


def wrap(inner: str, *, preheader: str, footer: str) -> str:
    base = get_settings().frontend_url.rstrip("/")
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#EEF0F5;font-family:Arial,Helvetica,sans-serif;color:#0E1930">
<span style="display:none;max-height:0;overflow:hidden">{html.escape(preheader)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">
<tr><td style="background:{NAVY};padding:18px 24px">
<img src="{base}/logo-dark.png" alt="VIP Network" height="30" style="display:block;height:30px"></td></tr>
<tr><td style="background:#FFFFFF;padding:28px 28px 12px;font-size:15px;line-height:1.6">{inner}</td></tr>
<tr><td style="padding:16px 24px;font-size:12px;color:#5D6780">{footer}</td></tr>
</table></td></tr></table></body></html>"""
