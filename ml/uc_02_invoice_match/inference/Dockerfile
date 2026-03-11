# UC-02 Invoice Three-Way Match — Inference Container
# SAP AI Core compatible stub

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ML code
COPY ../../common/ ./ml/common/
COPY ../../data_processing/ ./ml/data_processing/
COPY ../feature_engineering/feature_functions.py ./ml/uc_02_invoice_match/feature_engineering/
COPY serve.py ./

# SAP AI Core mount points
# /app/model/ — trained model artifact
# /app/data/  — input data for scoring
ENV MODEL_PATH=/app/model/best_model.joblib
ENV DATA_DIR=/app/data

ENTRYPOINT ["python", "serve.py", \
    "--model", "/app/model/best_model.joblib", \
    "--csv-dir", "/app/data"]
