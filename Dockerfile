FROM apache/airflow:2.9.1-python3.11
 
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
 
USER airflow
 
# Install postgres provider the Airflow-safe way
RUN pip install --no-cache-dir \
    "apache-airflow-providers-postgres" \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.9.1/constraints-3.11.txt"
 
# Install our extra packages (no version pins — let pip resolve)
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
 
# Download TextBlob language data
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('averaged_perceptron_tagger')"