"""
tools/search.py — Serper-backed Google search

Single function used by the character chat agent to fetch real-time information
about anime/game/film characters.  Supports zh-cn, en, and ja so the agent can
do multi-language searches and cross-validate facts across sources.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

SERPER_URL = "https://google.serper.dev/search"
SERPER_IMAGES_URL = "https://google.serper.dev/images"

_LANG_PARAMS = {
    "zh-cn": {"hl": "zh-cn", "gl": "cn"},
    "en":    {"hl": "en",    "gl": "us"},
    "ja":    {"hl": "ja",    "gl": "jp"},
}


def web_search(query: str, num: int = 5, lang: str = "zh-cn") -> str:
    """
    Search via Serper and return a formatted result string.

    The returned string is fed directly into the LLM as tool output, so it uses
    a human-readable format: "[lang]\\n- title: snippet\\n..." rather than JSON.
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return "搜索不可用：未配置 SERPER_API_KEY"

    lang_params = _LANG_PARAMS.get(lang, _LANG_PARAMS["zh-cn"])
    resp = requests.post(
        SERPER_URL,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": num, **lang_params},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    results = [f"[{lang}]"]
    for item in data.get("organic", [])[:num]:
        title   = item.get("title", "")
        snippet = item.get("snippet", "")
        results.append(f"- {title}: {snippet}")

    return "\n".join(results) if len(results) > 1 else f"[{lang}] 未找到相关结果"


def image_search(query: str, num: int = 10, lang: str = "ja") -> list[dict]:
    """
    Image search via Serper. Returns structured results (unlike web_search's
    formatted string) because callers need the raw imageUrl to download/pick:
      [ { imageUrl, thumbnailUrl, title, source, width, height }, ... ]
    Empty list if the key is missing or nothing is found.
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return []

    lang_params = _LANG_PARAMS.get(lang, _LANG_PARAMS["zh-cn"])
    resp = requests.post(
        SERPER_IMAGES_URL,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": num, **lang_params},
        timeout=15,
    )
    resp.raise_for_status()

    out = []
    for im in resp.json().get("images", [])[:num]:
        url = im.get("imageUrl")
        if not url:
            continue
        out.append({
            "imageUrl":     url,
            "thumbnailUrl": im.get("thumbnailUrl", ""),
            "title":        im.get("title", ""),
            "source":       im.get("source", ""),
            "width":        im.get("imageWidth") or 0,
            "height":       im.get("imageHeight") or 0,
        })
    return out
