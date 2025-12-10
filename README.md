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

# Models required by the backend (download and place in the `CoCrChallenge` directory):
# - YOLO face model: download `yolov8s-face-lindevs.pt` from
#   https://github.com/lindevs/yolov8-face and place the `.pt` file in the `CoCrChallenge` folder.
# - Vosk small English model: download `vosk-model-small-en-us-0.15` from
#   https://alphacephei.com/vosk/models and extract the model directory into `CoCrChallenge/vosk-model-small-en-us-0.15`.

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