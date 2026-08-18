# ZEN: Personal Voice-First AI Computer Assistant

[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6.svg)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**ZEN** is an intelligent, voice-first AI computer assistant engineered for **Windows** using **Python 3.14** modern async architecture. It blends autonomous tool execution, persistent 6-tier memory, real-time web intelligence, deep system diagnostics, an autonomous coding loop with self-debugging, and hands-free voice interaction—while maintaining strict safety boundaries and low resource utilization on laptop hardware.

---

## 🌟 Key Features

1. **Voice-First & Natural Conversations**
   - Natural spoken responses powered by **Edge-TTS** (pure Python neural voices) with instant offline **Windows SAPI5** fallback.
   - Hands-free wake phrase detection (`"Hey Zen"`).
   - Audio capture via `sounddevice` / `speech_recognition` (zero fragile C-compilation / no PyAudio requirement).

2. **Autonomous Coding Agent & Self-Debugging Loop**
   - Receives high-level requests: *"Zen, build a CLI tool in Python that does X"*.
   - Plans project architecture, scaffolds directories in sandboxed `workspace/`, creates isolated virtual environments (`.venv`), installs dependencies, runs tests (`pytest`), analyzes tracebacks, applies surgical auto-fixes, and verifies.

3. **6-Tier Persistent Memory System**
   - Strict separation between core code and learned memory (ZEN never modifies its own core engine).
   - 1. User Preferences
   - 2. Project Context
   - 3. Corrections & Learned Rules
   - 4. Verified Learned Facts with Certainty Scoring (0.0 to 1.0)
   - 5. Conversation History
   - 6. Session Scratchpad
   - Backed by an optimized **SQLite WAL** database.

4. **Deep PC Performance Diagnostics & Control**
   - Real-time CPU, RAM, disk, network, battery, and uptime metrics.
   - Runaway process detection and intelligent bottleneck explanations.
   - Safe app launcher (Notepad, Calculator, VS Code, Browser, Spotify, Explorer, Settings).
   - VS Code bridge for opening files at specific lines.

5. **Multi-Source Web Intelligence**
   - Search the internet via **DuckDuckGo / DDGS** without API keys.
   - Asynchronous webpage scraping & article extraction.
   - Multi-source synthesis with exact URL citations.

6. **Pluggable Multi-Provider AI Brain**
   - Out-of-the-box support for **Google Gemini (3.6 Flash & Pro)**, **OpenAI (GPT-4o)**, **Anthropic (Claude 3.5 Sonnet)**, and offline local **Ollama (Qwen 2.5 Coder / Llama 3)**.

7. **Strict Safety & Permissions Guardrails**
   - Tiered tool risk levels: `READ_ONLY`, `SAFE_EXECUTE`, `CONFIRM_NEEDED`, `RESTRICTED`.
   - Path traversal shields (preventing unauthorized system access).
   - Destructive command blocker (`format`, `rmdir /s /q`, etc.).
   - Full append-only security audit log in `data/audit.log`.

---

## 📁 Architecture Overview

```
d:\ZEN\
├── config/              # Typed Pydantic settings & global constants
├── zen/
│   ├── core/            # Central event bus, session context, orchestrator & logger
│   ├── brain/           # Swappable AI providers (Gemini, OpenAI, Anthropic, Ollama)
│   ├── voice/           # Voice capture, STT, Edge-TTS & SAPI fallback
│   ├── memory/          # SQLite 6-tier memory manager & certainty engine
│   ├── tools/           # Tool registry, permissions, and security guardrails
│   ├── computer/        # Diagnostics, system monitoring, app launcher, VS Code bridge
│   ├── research/        # Web search, scraper, and multi-source summarizer
│   └── coding/          # Autonomous project builder, virtualenv manager & self-debugging
├── workspace/           # Sandboxed project development directory
├── data/                # SQLite memory database (memory.db) and audit logs
├── tests/               # Unit and integration test suite
└── zen.py               # Main CLI entrypoint
```

---

## 🚀 Quick Start

### 1. Installation

Clone and install dependencies:

```powershell
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and insert your API key:

```powershell
cp .env.example .env
```

Edit `.env`:
```env
ZEN_AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Usage

#### Interactive Chat Mode
```powershell
python zen.py chat
```

#### Hands-Free Voice Assistant Mode
```powershell
python zen.py voice
```

#### Run Instant PC Performance Diagnostics
```powershell
python zen.py diagnose
```

#### Inspect Assistant Configuration
```powershell
python zen.py info
```

---

## 🧪 Running Tests

Execute the automated test suite with pytest:

```powershell
python -m pytest tests -v
```

---

## 🔒 Security Policy
- **Zero Self-Modifying Code**: Core logic inside `zen/` and `config/` is strictly read-only to AI tools.
- **Confirmation Interceptor**: Sensitive operations require interactive user approval (`[Y/N]`).
- **Audit Logging**: Every tool execution is recorded with parameters and status in `data/audit.log`.
