# 🔥 RoastMyResume

> **Brutally honest AI career coach for your friend who keeps getting rejected.**
> Built for the "Build for a Friend" challenge — Open-Source AI at its core.

---

## 🎯 The Problem

My friend Arjun kept applying to internships and getting rejected. He'd send me his resume and I'd say "looks great!" — because I didn't want to hurt his feelings. He needed someone to tell him the truth.

So I built an AI that would.

**RoastMyResume** gives the brutal, honest feedback that friends are too polite to give — but in a constructive way that actually fixes the problem.

---

## ✨ Features

| Feature | What it does |
|---|---|
| 🔥 **The Roast** | Section-by-section brutal honest feedback in Gen Z voice |
| ⏱️ **4-Second Test** | Simulates exactly what a recruiter sees in 4 seconds |
| 📊 **Rejection Risk Score** | 0-100 score per section with visual charts |
| 🎯 **JD Match Analysis** | Compares resume against actual job description |
| 🔑 **Keyword Gap Finder** | Shows missing ATS keywords you need to add |
| ✏️ **AI Rewriter** | Rewrites any section to be stronger and JD-matched |
| ❓ **Interview Prep** | Predicts hardest interview questions based on resume gaps |
| 🔊 **Voice Roast** *(optional)* | Reads the roast aloud with ElevenLabs TTS |

---

## 🚀 Quick Start (5 minutes)

### Prerequisites

| What | Why | Where |
|---|---|---|
| **Python 3.9–3.12** | Runs the app | [python.org/downloads](https://www.python.org/downloads/) |
| **Ollama** | Runs the AI model locally | [ollama.com/download](https://ollama.com/download) |
| **8 GB RAM** (16 GB recommended) | The model runs in memory | — |
| **~2.5 GB disk space** | Llama 3.2 model download | — |

> 💡 No GPU needed — it runs on CPU. Slower, but works.

### Step 1 — Clone the repo

```bash
git clone https://github.com/<your-username>/RoastMyResume.git
cd RoastMyResume
```

### Step 2 — Create a virtual environment *(recommended)*

This keeps the project's packages separate from your system Python. Skip it only if you know what you're doing.

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### Step 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Install Ollama (if not already installed)

```bash
# macOS (Homebrew)
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows → download the installer from https://ollama.com/download
```

### Step 5 — Download the AI model

```bash
ollama pull llama3.2
```

### Step 6 — The `.env` file (OPTIONAL — only for the voice feature)

The app works 100% without this. You only need it if you want the 🔊 voice-roast button.

1. In the **project root** (the same folder as `app.py`), create a file named exactly `.env`
2. Easiest way — copy the template:
   ```bash
   # macOS / Linux
   cp .env.example .env

   # Windows (PowerShell)
   Copy-Item .env.example .env
   ```
3. Open `.env` and put your ElevenLabs API key in it:
   ```
   ELEVENLABS_API_KEY="your_elevenlabs_api_key_here"
   ```
4. **How to get the key:** sign up free at [elevenlabs.io](https://elevenlabs.io) → dashboard → **API Keys** → copy your key. The free tier is enough to try it.

> ⚠️ `.env` is in `.gitignore` — never commit it or share it. It contains a secret.

### Step 7 — Run the app

```bash
# Terminal 1: start the Ollama server
ollama serve

# Terminal 2: start the app (run this from the project root!)
streamlit run app.py
```

Then open **http://localhost:8501** in your browser. 🎉

> 💡 `ollama serve` only needs to run once per session — after that it stays in the background. If you installed Ollama via the desktop app, it's already running, so skip Terminal 1.

### Alternative: one-command setup

```bash
python setup.py
```

This installs the Python deps, checks/installs Ollama, pulls `llama3.2`, and creates a `.env` from the template for you. It will suggest a virtual environment if you're not in one.

---

## ⚠️ Troubleshooting

| Error / symptom | Fix |
|---|---|
| `externally-managed-environment` on macOS/Linux | You skipped Step 2. Create the venv first, then `pip install` again |
| `Connection refused` / "Ollama error" in the app | Ollama isn't running — run `ollama serve` in a separate terminal (or open the Ollama desktop app) |
| `model 'llama3.2' not found` | Run `ollama pull llama3.2` |
| Port 8501 already in use | `streamlit run app.py --server.port 8502` |
| Voice button does nothing | You don't have a `.env` with a valid `ELEVENLABS_API_KEY` — see Step 6. Everything else still works |
| PDF upload fails | Max file size is 10 MB (see `.streamlit/config.toml`). Scanned/image-only PDFs need OCR first |
| App behaves oddly after editing `.env` | Restart `streamlit run app.py` — the key is read at startup |
| `AttributeError: module 'hashlib' has no attribute 'blake2b'` on startup | Your Python build is missing the `_blake2` extension module, which Streamlit's file watcher needs. Reinstall that interpreter (e.g. `pyenv uninstall 3.11.8 && pyenv install 3.11.8`) or use a different Python for the venv. Installing `watchdog` does **not** work around it |

---

## 🧪 Running the tests

```bash
python -m unittest discover tests
```

105 tests, no network or model calls required — they cover the resume parser
(including two-column DOCX layouts), JD parsing and role-title detection, the
score visualisations, and the diff renderer.

---

## 🔧 Configuration

- **Swap models** in the sidebar — `llama3.2` (default), `mistral`, `gemma2`, `phi3`, `llama3.1`. Pull any model first with `ollama pull <name>`
- **Pick a persona** — Brutal friend, Gentle mentor, FAANG recruiter, Startup founder, Indian market expert, HR professional
- **Fine-tune behavior** for your industry:
  ```bash
  ollama create tech-resume-expert -f ./Modelfile
  ```
  ```
  # Modelfile
  FROM llama3.2
  SYSTEM "You are a senior SWE at FAANG who has reviewed 50,000 software engineer resumes..."
  ```

---

## 🧱 Architecture

```
RoastMyResume/
├── app.py                    # Streamlit UI (5 tabs: review, scorecard, rewrite, interview prep, Q&A)
├── core/
│   ├── resume_parser.py      # PDF/DOCX → text (PDFPlumber, local)
│   ├── jd_scraper.py         # LinkedIn/Naukri/Indeed scraper (BeautifulSoup)
│   ├── roaster.py            # Ollama LLM calls (streaming + JSON)
│   ├── scorer_viz.py         # Plotly charts (gauge, radar, bar, donut)
│   ├── exporter.py           # Download as DOCX or Markdown
│   └── tts.py                # ElevenLabs voice roast (optional, uses .env key)
├── ui/
│   ├── styles.css            # App theme styles
│   ├── __init__.py           # Shared UI helpers
│   └── diff.py               # Word-level diff renderer (escaped)
├── prompts/
│   └── prompts.py            # All LLM prompt templates
├── tests/                    # Unit tests (run: python -m unittest discover tests)
├── .streamlit/config.toml    # Theme + 10 MB upload limit
├── .env.example              # Template for your .env (voice feature)
├── setup.py                  # One-command installer
└── requirements.txt
```

### Data Flow

```
User uploads PDF
       ↓
PDFPlumber (local) → raw text
       ↓
Ollama (local LLM) ← JD text (scraped locally)
       ↓
Streaming roast output → Streamlit UI
       ↓
JSON scores → Plotly charts
       ↓
Section rewriter → Download
```

**Zero data leaves the machine at any point** (except the optional ElevenLabs voice feature, which sends only the roast text).

---

## 🛠️ Tech Stack

| Component | Technology | Why Open-Source? |
|---|---|---|
| LLM | Ollama + Llama 3.2 | Local inference, swap models, free |
| PDF Parsing | PDFPlumber | Fully local, no cloud OCR |
| JD Scraping | BeautifulSoup | No paid scraping API needed |
| UI | Streamlit | Fast to build, looks great |
| Charts | Plotly | Interactive, local rendering |
| DOCX | python-docx | Local doc parsing |
| Voice *(optional)* | ElevenLabs TTS | Free tier, only for voice roasts |

---

## 🔓 Why Open-Source AI Wins Here

### ✅ Runs on a laptop with NO internet
Ollama + Llama 3.2 runs **100% locally** on your machine. No WiFi needed for the core analysis. Perfect for:
- Students in hostels with bad internet
- Using on a flight before an interview
- Remote areas with no connectivity

```bash
# Once set up, works completely offline:
ollama serve          # local model server
streamlit run app.py  # local web app
```

*(First-time setup obviously needs internet for `pip install` and `ollama pull`. JD scraping also needs internet, obviously.)*

### 🔒 Your resume NEVER touches a server you don't control
This is the biggest difference from closed solutions (Grammarly, Kickresume, Resume.io):

| Tool | Where does your resume go? |
|---|---|
| Grammarly | Their cloud servers (used for training) |
| Kickresume | Their servers (requires account) |
| **RoastMyResume** | **Nowhere. Stays on your laptop.** |

For a job seeker, their resume contains: name, phone, address, employment history, GPA, projects. This is sensitive data. Open-source means it never leaves.

### 🔄 Swap models without changing a single line of code
```python
# In settings, switch instantly between:
model = "llama3.2"    # Default, 3B params
model = "mistral"     # Better reasoning
model = "phi3"        # Faster on weaker laptops
model = "gemma2"      # Google's open model
model = "llama3.1"    # Larger, more nuanced
```

Closed APIs (ChatGPT, Claude) lock you into one model and one pricing tier. Open-source means you pick what's right for your hardware.

### 🆓 Costs ZERO to run
```
OpenAI GPT-4o: ~$0.005 per resume analysis
Running 100 analyses: $0.50/day → $15/month
Running 1000 analyses: $5/day

RoastMyResume: $0.00 forever.
```

For a college student with no income, this matters enormously.

---

## 💙 Built For

This was built for my friend who applied to 47 internships and heard back from 3.

After he used RoastMyResume, he rewrote his resume in 2 hours. The AI told him:

> *"Your bullet points read like a job description, not an achievement list. 'Worked on Django backend' tells me nothing. Did you build it? Fix it? Optimize it? How much? What happened because you did it?"*

That single insight changed everything.

He got an interview at his dream company 2 weeks later.

---

## 🌟 Open-Source Matters Here Because

1. **Privacy**: A resume is one of the most personal documents you own. It should never train someone else's model.
2. **Access**: Students in India, Nigeria, Vietnam shouldn't need \$20/month subscriptions to get career help.
3. **Customization**: Every industry has different resume norms. Open models let you tune for that.
4. **Reliability**: No API outages, no rate limits, no deprecations. Your tool works when you need it.

---

## 📄 License

See [LICENSE](LICENSE).

---

*Built with ❤️ using Ollama + Llama 3.2 + Streamlit*
*"The best career advice comes from someone who cares enough to be honest."*
