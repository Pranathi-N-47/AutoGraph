# ⚡ AutoGraph

**AutoGraph** is an AI-powered visualization tool designed to automate the conversion of unstructured text into professional process diagrams.

![Project Status](https://img.shields.io/badge/Status-Active-success)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Stack](https://img.shields.io/badge/Stack-Streamlit%20%7C%20FastAPI%20%7C%20Llama3-orange)

## 📖 What It Is

Recognizing that manual diagramming is often time-consuming, AutoGraph leverages Large Language Models (LLMs) to perform **semantic logic extraction**—parsing complex paragraphs to identify actionable steps, conditional branches, and recurring loops. 

By translating natural language directly into strict **Mermaid.js** syntax, AutoGraph allows users to instantly visualize Standard Operating Procedures (SOPs), technical guides, and algorithms, transforming dense documentation into clear, interactive flowcharts.

## 🚀 What It Does
* **Zero-Shot Logic Extraction:** Instantly converts text to flowcharts without training.
* **Intelligent Parsing:** Distinguishes between Actions (`[]`) and Decisions (`{}`) automatically.
* **Loop Detection:** Identifies "retry" logic and draws recursive arrows instead of duplicate nodes.
* **Microservices Architecture:** Decoupled Frontend (Streamlit) and Backend (FastAPI).
* **Live Editor:** Modify the generated code in real-time and see the updates instantly.
* **Export Ready:** One-click export to Mermaid.live for high-res downloading.

## 🛠️ What It Has

* **Frontend:** [Streamlit](https://streamlit.io/) (UI, State Management)
* **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (API Endpoints, Validation)
* **AI Engine:** [Groq Cloud](https://groq.com/) (Running Llama-3-8b-Instant)
* **Visualization:** [Mermaid.js](https://mermaid.js.org/)

## 📂 How It Is

```text
AutoGraph-Pro/
├── backend.py        # FastAPI Server (Business Logic & AI)
├── frontend.py       # Streamlit App (UI & Rendering)
├── requirements.txt  # Project Dependencies
├── .gitignore        # Git configuration
└── README.md         # Documentation

```

## ⚡ How to Set It UP

### Prerequisites

* Python 3.11 or higher
* A free API Key from [Groq Console](https://console.groq.com/)

### 1. Clone the Repository

```bash
git clone [https://github.com/YOUR_USERNAME/AutoGraph-Pro.git](https://github.com/YOUR_USERNAME/AutoGraph-Pro.git)
cd AutoGraph-Pro

```

### 2. Create a Virtual Environment

It is recommended to use a virtual environment to keep dependencies clean.

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate

```

**Mac/Linux:**

```bash
python3 -m venv venv
source venv/bin/activate

```

### 3. Install Dependencies

Create a file named `requirements.txt` with the following content (or use the provided one):

```text
fastapi
uvicorn
streamlit
streamlit-mermaid
requests
groq
pydantic

```

Then install them:

```bash
pip install -r requirements.txt

```

## 🏃‍♂️ How to Run

This application follows a **Client-Server architecture**, so you must run the Backend and Frontend in **two separate terminals**.

### Step 1: Start the Backend (Terminal 1)

This runs the AI processing server locally.

```bash
python backend.py

```

*You should see a message: `Uvicorn running on http://127.0.0.1:8000*`

### Step 2: Start the Frontend (Terminal 2)

Open a new terminal window (keep the first one running!) and launch the UI.

```bash
streamlit run frontend.py

```

*The app will open automatically in your browser at `http://localhost:8501*`

## 🧪 Test It Yourself

Try pasting these text blocks into the app to test the logic engine:

**1. Simple Linear Flow**

> "Wake up at 7 AM. Eat breakfast. Brush teeth. Go to work."

**2. Branching Logic (Decisions)**

> "Check the server status. If it is Online, start the backup. If it is Offline, restart the service. If the restart fails, alert the admin."

**3. Looping Logic (Recursion)**

> "Check the water temperature. If it is below 100 degrees, wait 10 seconds and **check again**. If it is 100 degrees, add the pasta."

## 🔮 What Next

* **Computer Vision Integration:** Upload a photo of a whiteboard sketch to digitize it.
* **Multi-Diagram Support:** Automatic detection to switch between Flowcharts, Sequence Diagrams, and Gantt charts.
* **Agentic Validators:** A secondary AI agent that critiques the flowchart for "dead ends" before showing it to the user.

## 📄 License

This project is open-source and available under the MIT License.
