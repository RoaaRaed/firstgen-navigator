import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("intfloat/multilingual-e5-small")

# A local database saved in the folder chroma_db (already in .gitignore)
client = chromadb.PersistentClient(path="chroma_db")

# Start fresh on every run so the test is repeatable
try:
    client.delete_collection("test_kb")
except Exception:
    pass
collection = client.create_collection(
    "test_kb", metadata={"hnsw:space": "cosine"}  # distance = 1 - similarity
)

# Small fake knowledge base, just for testing (not real facts for the product)
docs = [
    ("fafsa-1", "The FAFSA is the form students fill out to apply for federal financial aid for college.", "federal"),
    ("map-1", "The Illinois MAP grant is need-based state financial aid for students attending Illinois colleges.", "state"),
    ("altapp-1", "The Alternative Application for Illinois Financial Aid is for students who cannot file the FAFSA.", "state"),
    ("ccc-1", "To apply to City Colleges of Chicago, complete the online application and submit proof of residency.", "institution"),
    ("cafe-1", "The cafeteria is open from 8 a.m. to 3 p.m. and serves hot lunch.", "institution"),
]

texts = ["passage: " + t for _, t, _ in docs]
embeddings = model.encode(texts, normalize_embeddings=True).tolist()

collection.add(
    ids=[i for i, _, _ in docs],
    documents=[t for _, t, _ in docs],
    embeddings=embeddings,
    metadatas=[{"layer": layer} for _, _, layer in docs],
)
print("Stored", collection.count(), "documents\n")


def ask(question, n=3, layer=None):
    q = model.encode("query: " + question, normalize_embeddings=True).tolist()
    kwargs = {"where": {"layer": layer}} if layer else {}
    res = collection.query(query_embeddings=[q], n_results=n, **kwargs)
    print("Q:", question, "| filter:", layer)
    for id_, dist, text in zip(res["ids"][0], res["distances"][0], res["documents"][0]):
        print(f"  {1 - dist:.3f}  [{id_}]  {text[:70]}")
    print()


ask("ما هي منحة MAP؟")
ask("كيف أقدّم طلب التحاق بكليات مدينة شيكاغو؟")
ask("أنا ما بقدر أعبّي FAFSA، في مساعدة مالية ثانية؟")
ask("أنا ما بقدر أعبّي FAFSA، في مساعدة مالية ثانية؟", layer="state")