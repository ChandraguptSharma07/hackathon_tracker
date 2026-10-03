"""Detect well-known companies behind a hackathon from its text.

Patterns are case-sensitive on purpose: "Meta" the company, not "meta" the word.
"""

import re

from .models import Hackathon

SPONSOR_PATTERNS: dict[str, str] = {
    "OpenAI": r"\bOpenAI\b|\bChatGPT\b|\bGPT-\d",
    "Anthropic": r"\bAnthropic\b|\bClaude\b",
    "Google": r"\bGoogle\b|\bGemini\b|\bDeepMind\b|\bFirebase\b",
    "Amazon": r"\bAmazon\b|\bAWS\b|\bAlexa\b",
    "Microsoft": r"\bMicrosoft\b|\bAzure\b|\bGitHub Copilot\b",
    "Meta": r"\bMeta\b|\bLlama\b|\bPyTorch\b|\bExecuTorch\b",
    "NVIDIA": r"\bNVIDIA\b|\bNvidia\b",
    "AMD": r"\bAMD\b",
    "IBM": r"\bIBM\b|\bwatsonx\b",
    "Mistral": r"\bMistral\b",
    "xAI": r"\bxAI\b|\bGrok\b",
    "Apple": r"\bApple\b",
    "Qualcomm": r"\bQualcomm\b",
    "Intel": r"\bIntel\b",
    "Databricks": r"\bDatabricks\b",
    "Snowflake": r"\bSnowflake\b",
    "Cloudflare": r"\bCloudflare\b",
    "Vercel": r"\bVercel\b",
    "ElevenLabs": r"\bElevenLabs\b",
    "Hugging Face": r"\bHugging ?Face\b",
    "Ethereum": r"\bEthereum\b|\bETHGlobal\b",
    "Solana": r"\bSolana\b",
}

_COMPILED = {name: re.compile(p) for name, p in SPONSOR_PATTERNS.items()}


def detect(*texts: str | None) -> list[str]:
    blob = "\n".join(t for t in texts if t)
    return [name for name, rx in _COMPILED.items() if rx.search(blob)]


def tag(h: Hackathon) -> Hackathon:
    found = detect(h.title, h.organizer, h.description, " ".join(h.themes))
    h.sponsors = sorted(set(h.sponsors) | set(found))
    return h
