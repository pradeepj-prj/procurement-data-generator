# UC-02 Invoice Three-Way Match — Training Container
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
COPY train.py config.yaml ./

# SAP AI Core mount points (data and model output)
# /app/data/  — input data (CSV or DB credentials)
# /app/model/ — output model artifacts
ENV DATA_DIR=/app/data
ENV MODEL_DIR=/app/model

ENTRYPOINT ["python", "train.py", \
    "--data-source", "csv", \
    "--csv-dir", "/app/data", \
    "--output-model", "/app/model/best_model.joblib"]
