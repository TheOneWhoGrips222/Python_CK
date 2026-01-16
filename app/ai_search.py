from sentence_transformers import SentenceTransformer, util
import torch

print("Đang tải model AI... Vui lòng đợi")
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
print("Đã tải xong model AI!")

def find_similar_questions_ai(user_query, all_questions, top_k = 5, threshold = 0.5):
    """
        user_query: Câu người dùng đang gõ
        all_questions: QuerySet chứa tất cả câu hỏi trong DB
        top_k: Số lượng kết quả trả về tối đa
        threshold: Độ chính xác tối thiểu (0.5 nghĩa là giống 50%)
    """
    if not all_questions:
        return []

    titles = [q.title for q in all_questions]

    # Mã hóa tiêu đề và câu truy vấn thành Vector
    corpus_embeddings = model.encode(titles, convert_to_tensor=True)
    query_embeddings = model.encode(user_query, convert_to_tensor=True)

    # Sử dụng Cosine Similarity để tìm câu giống nhất
    hits = util.semantic_search(query_embeddings, corpus_embeddings, top_k=top_k)[0]

    results = []
    for hit in hits:
        score = hit['score']
        if score >= threshold:
            idx = hit['corpus_id']
            question_obj = all_questions[idx]
            results.append({
                'question': question_obj,
                'score': score,
            })
    return results