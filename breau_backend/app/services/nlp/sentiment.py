from functools import lru_cache
from transformers import pipeline

@lru_cache(maxsize=1)
def _pipe():
    # Robust sentiment with POSITIVE/NEGATIVE/NEUTRAL
    return pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment-latest")

def analyze_sentiment(text: str):
    res = _pipe()(text)[0]  # {'label': 'POSITIVE', 'score': 0.99}
    label = res["label"].lower()
    if label.startswith("pos"):
        label = "positive"
    elif label.startswith("neg"):
        label = "negative"
    else:
        label = "neutral"
    return {"label": label, "score": float(res["score"])}
