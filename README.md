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

---

## 🔓 Why Open-Source AI Wins Here

### ✅ Runs on a laptop with NO internet
Ollama + Llama 3.2 runs **100% locally** on your machine. No WiFi needed. Perfect for:
- Students in hostels with bad internet
- Using on a flight before an interview
- Remote areas with no connectivity

```bash
# Once set up, works completely offline:
ollama serve          # local model server
streamlit run app.py  # local web app
```

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

### 🎛️ Fine-tune for your specific industry
With open weights, you can:
```bash
# Fine-tune Llama on industry-specific data
ollama create tech-resume-expert -f ./Modelfile

# Modelfile example:
FROM llama3.2
SYSTEM "You are a senior SWE at FAANG who has reviewed 50,000 software engineer resumes..."
```

Closed APIs don't let you do this. Open-source means you own the behavior.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- 8GB RAM minimum (16GB recommended)
- ~3GB disk space for the model

### 1. One-command setup
```bash
git clone <repo>
cd RoastMyResume
python setup.py
```

### 2. Start the app
```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Run the app
streamlit run app.py
```

### 3. Open in browser
```
http://localhost:8501
```

### Manual installation (if setup.py fails)
```bash
pip install -r requirements.txt
brew install ollama          # Mac
ollama pull llama3.2
ollama serve
streamlit run app.py
```

---

## 🧱 Architecture

```
RoastMyResume/
├── app.py                    # Streamlit UI (4 tabs)
├── core/
│   ├── resume_parser.py      # PDF/DOCX → text (PDFPlumber, local)
│   ├── jd_scraper.py         # LinkedIn/Naukri/Indeed scraper (BeautifulSoup)
│   ├── roaster.py            # Ollama LLM calls (streaming + JSON)
│   └── scorer_viz.py         # Plotly charts (gauge, radar, bar, donut)
├── prompts/
│   └── prompts.py            # All LLM prompt templates
├── requirements.txt
├── setup.py                  # One-command installer
└── README.md
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

**Zero data leaves the machine at any point.**

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

*Built with ❤️ using Ollama + Llama 3.2 + Streamlit*
*"The best career advice comes from someone who cares enough to be honest."*
