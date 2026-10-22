from sentence_transformers import SentenceTransformer

model = SentenceTransformer("intfloat/multilingual-e5-small")

# This model needs prefixes: "query: " for questions, "passage: " for documents
query = "query: كيف أقدّم على المساعدة المالية للجامعة؟"
passages = [
    "passage: The FAFSA is the form students fill out to apply for federal financial aid for college.",
    "passage: The cafeteria is open from 8 a.m. to 3 p.m. and serves hot lunch.",
]

q = model.encode(query, normalize_embeddings=True)
p = model.encode(passages, normalize_embeddings=True)

scores = p @ q  # similarity: higher = closer in meaning
for text, score in zip(passages, scores):
    print(round(float(score), 3), text)