# app/ai_tagging.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
import functools


@dataclass(frozen=True)
class TagDef:
    name: str
    desc: str


# ====== Bộ tag cơ bản (bạn có thể thêm/bớt) ======
TAG_DEFS: List[TagDef] = [
    TagDef("java", "Java, OOP, class, interface, JVM, JDK, Spring, JSP, Servlet, Tomcat, Maven, Gradle, exception, ArrayList, HashMap"),
    TagDef("python", "Python, pip, venv, Django, Flask, pandas, numpy, script, module, virtual environment"),
    TagDef("sql", "SQL, database, MySQL, SQLite, PostgreSQL, SELECT, INSERT, UPDATE, DELETE, JOIN, GROUP BY, index, optimization"),
    TagDef("javascript", "JavaScript, JS, Node.js, npm, React, Vue, DOM, async await, fetch API"),
    TagDef("html-css", "HTML, CSS, layout, flex, grid, bootstrap, responsive UI, frontend"),
    TagDef("network", "socket, TCP, UDP, HTTP, REST, client server, port, packet, request response"),
    TagDef("ai", "machine learning, deep learning, NLP, embedding, transformer, model training, classification"),
]


@functools.lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


@functools.lru_cache(maxsize=1)
def _get_tag_embeddings():
    import numpy as np

    model = _get_model()
    texts = [t.desc for t in TAG_DEFS]
    emb = model.encode(texts, normalize_embeddings=True)
    return np.array(emb, dtype="float32")


def suggest_tags_ai(title: str, body: str, top_k: int = 3, threshold: float = 0.35) -> List[Tuple[str, float]]:
    """
    Trả về [(tag_name, score)] theo điểm similarity giảm dần.
    threshold: tăng lên (0.40-0.45) nếu tag bị gán bừa.
    """
    import numpy as np

    text = ((title or "").strip() + "\n" + (body or "").strip()).strip()
    if not text:
        return []

    model = _get_model()
    tag_emb = _get_tag_embeddings()

    q_emb = model.encode([text], normalize_embeddings=True)
    q_emb = np.array(q_emb, dtype="float32")[0]

    # cosine similarity vì đã normalize => dot product
    scores = tag_emb @ q_emb

    idx = scores.argsort()[::-1]
    out: List[Tuple[str, float]] = []
    for i in idx[:top_k]:
        sc = float(scores[i])
        if sc >= threshold:
            out.append((TAG_DEFS[i].name, sc))
    return out
