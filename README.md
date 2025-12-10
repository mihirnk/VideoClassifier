# Setup and Run Backend + Frontend

```bash
# -------------------------
# Backend Setup
# -------------------------
# create and activate virtual environment
python3 -m venv venv
source venv/bin/activate    # macOS/Linux
# venv\Scripts\activate     # Windows

# install backend dependencies
pip install -r requirements.txt

# run the backend
cd CoCrChallenge
python3 api.py

# -------------------------
# Frontend Setup
# -------------------------
# install frontend dependencies
npm install

# navigate to frontend and start dev server
cd frontend
npm run dev

# The localhost and port will be shown in the terminal, allowing you to access the application