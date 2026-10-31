"""Part D (tasks 1-3): chunk policy documents, TF-IDF retrieval, grounded answer."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mock_llm  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.metrics.pairwise import cosine_similarity  # noqa: E402

POLICY_DIR = os.path.join("data", "policies")

SYSTEM_PROMPT = (
    "You are a POLICY ASSISTANT for a grocery delivery company. "
    "Answer only from the supplied context. "
    "If the answer is not in the context, say that you could not find the information."
)


def load_documents():
    docs = {}
    for name in sorted(os.listdir(POLICY_DIR)):
        if name.endswith(".txt"):
            with open(os.path.join(POLICY_DIR, name), encoding="utf-8") as f:
                docs[name] = f.read()
    return docs


def chunk_document(text, size=40, overlap=10):
    words = text.split()
    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        end = start + size
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
    return chunks


def build_chunks(size=40, overlap=10):
    chunks = []
    for name, text in load_documents().items():
        for c in chunk_document(text, size, overlap):
            chunks.append({"source": name, "text": c})
    return chunks


class PolicyIndex:
    def __init__(self, size=40, overlap=10):
        self.chunks = build_chunks(size, overlap)
        self.vectorizer = TfidfVectorizer()
        self.matrix = self.vectorizer.fit_transform([c["text"] for c in self.chunks])

    def retrieve(self, query, k=3):
        q = self.vectorizer.transform([query])
        scores = cosine_similarity(q, self.matrix)[0]
        order = np.argsort(-scores, kind="stable")[:k]
        return [{"source": self.chunks[i]["source"],
                 "score": float(scores[i]),
                 "text": self.chunks[i]["text"]} for i in order]


DEFAULT_INDEX = PolicyIndex()


def retrieve(query, k=3):
    return DEFAULT_INDEX.retrieve(query, k)


def answer(question, index=None):
    idx = index or DEFAULT_INDEX
    hits = idx.retrieve(question, k=3)
    context = "\n".join(f"[{h['source']}]\n{h['text']}" for h in hits)
    user_msg = f"CONTEXT:\n{context}\nQUESTION:\n{question}"
    resp = mock_llm.chat([{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": user_msg}])
    return resp.choices[0].message.content, [h["source"] for h in hits]