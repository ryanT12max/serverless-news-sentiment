import io
import json
import requests
import oracledb
from datetime import datetime
from fdk import response
import os

# ── 1. EXTRACT ──────────────────────────────────────────────
def get_tech_news():
    api_key = os.environ.get("9664ab2097d54e88b15e03b147e9b0f0")
    url = (
        "https://newsapi.org/v2/top-headlines"
        f"?category=technology&language=en&pageSize=10&apiKey={9664ab2097d54e88b15e03b147e9b0f0}"
    )
    resp = requests.get(url)
    articles = resp.json().get("articles", [])
    return [
        {
            "headline": a.get("title", "")[:500],
            "source":   a.get("source", {}).get("name", "Unknown")[:100],
            "url":      a.get("url", "")[:1000],
            "published_at": a.get("publishedAt", "")[:50]
        }
        for a in articles
        if a.get("title")
    ]

# ── 2. TRANSFORM (AI Sentiment) ──────────────────────────────
def analyze_sentiment(headline):
    hf_token = os.environ.get("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")
    api_url = (
        "https://api-inference.huggingface.co/models/"
        "distilbert-base-uncased-finetuned-sst-2-english"
    )
    headers = {"Authorization": f"Bearer {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}"}
    payload = {"inputs": headline}

    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=10)
        result = resp.json()

        # HF returns [[{label, score}, {label, score}]]
        if isinstance(result, list) and len(result) > 0:
            scores = result[0]
            best = max(scores, key=lambda x: x["score"])
            return best["label"], round(best["score"], 4)
    except Exception as e:
        print(f"Sentiment error for '{headline[:50]}': {e}")

    return "UNKNOWN", 0.0

# ── 3. LOAD ──────────────────────────────────────────────────
def load_to_oracle(articles_with_sentiment):
    connection = oracledb.connect(
        user="ADMIN",
        password=os.environ.get("0n@stR8l1n3U"),
        dsn="Wallet_AviationDB",
        config_dir="/function/wallet",
        wallet_location="/function/wallet",
        wallet_password=os.environ.get("Tij79268*")
    )

    cursor = connection.cursor()
    sql = """
        INSERT INTO TECH_NEWS_SENTIMENT
            (HEADLINE, SOURCE, SENTIMENT, CONFIDENCE, URL, PUBLISHED_AT)
        VALUES (:1, :2, :3, :4, :5, :6)
    """

    for item in articles_with_sentiment:
        cursor.execute(sql, [
            item["headline"],
            item["source"],
            item["sentiment"],
            item["confidence"],
            item["url"],
            item["published_at"]
        ])

    connection.commit()
    cursor.close()
    connection.close()

# ── 4. HANDLER (OCI Entry Point) ─────────────────────────────
def handler(ctx, data: io.BytesIO = None):
    try:
        articles = get_tech_news()
        if not articles:
            return response.Response(
                ctx,
                response_data=json.dumps({"status": "No articles found"}),
                headers={"Content-Type": "application/json"}
            )

        enriched = []
        for article in articles:
            label, score = analyze_sentiment(article["headline"])
            enriched.append({**article, "sentiment": label, "confidence": score})

        load_to_oracle(enriched)

        return response.Response(
            ctx,
            response_data=json.dumps({
                "status": "Success",
                "articles_loaded": len(enriched)
            }),
            headers={"Content-Type": "application/json"}
        )

    except Exception as e:
        return response.Response(
            ctx,
            response_data=json.dumps({"error": str(e)}),
            headers={"Content-Type": "application/json"}
        )
