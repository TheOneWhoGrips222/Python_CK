// static/app/js/add.js
document.addEventListener("DOMContentLoaded", function() {
    // --- PHẦN 1: KHỞI TẠO QUILL EDITOR ---
    window.katex = katex;
    const toolbarOptions = [
        ['bold', 'italic', 'underline', 'strike'],
        ['blockquote', 'code-block'],
        [{ 'header': 1 }, { 'header': 2 }],
        [{ 'list': 'ordered'}, { 'list': 'bullet' }],
        ['link', 'formula'],
        ['clean']
    ];

    const quill = new Quill('#editor', {
        theme: 'snow',
        modules: {
            syntax: true,
            toolbar: toolbarOptions
        },
    });

    // --- PHẦN 2: LOGIC KIỂM TRA TƯƠNG ĐỒNG TIÊU ĐỀ ---
    const titleInput = document.getElementById('id_title');
    const submitBtn = document.querySelector('button[type="submit"]');
    const warningBox = document.getElementById('ai-warning-box');
    const resultsList = document.getElementById('similar-questions-list');
    const statusText = document.getElementById('title-check-status');

    let typingTimer;
    const doneTypingInterval = 500;

    if (titleInput) {
        titleInput.addEventListener('input', function() {
            clearTimeout(typingTimer);
            resetStatus();

            const query = this.value.trim();
            if (query.length >= 5) {
                statusText.innerHTML = '<i class="fas fa-spinner fa-spin"></i> AI đang kiểm tra độ trùng lặp...';
                typingTimer = setTimeout(() => {
                    checkTitleSimilarity(query);
                }, doneTypingInterval);
            }
        });
    }

    async function checkTitleSimilarity(title) {
        try {
            // URL này phải khớp với urls.py
            const response = await fetch(`/api/search_similar/?q=${encodeURIComponent(title)}`);
            const data = await response.json();

            if (data.results && data.results.length > 0) {
                let blockSubmission = false;
                resultsList.innerHTML = '';

                data.results.forEach(item => {
                    // Chặn nếu độ tương đồng >= 80%
                    if (item.similarity >= 80) {
                        blockSubmission = true;
                    }
                    const qItem = document.createElement('div');
                    qItem.style.marginBottom = '5px';
                    qItem.innerHTML = `• <a href="${item.url}" target="_blank" style="color: #0074cc;">${item.title}</a> (Giống ${item.similarity}%)`;
                    resultsList.appendChild(qItem);
                });

                if (blockSubmission) {
                    warningBox.style.display = 'block';
                    statusText.innerHTML = '<b style="color: #d32f2f;">Trạng thái: Bị chặn (Tiêu đề quá giống câu hỏi cũ)</b>';
                    submitBtn.disabled = true;
                    submitBtn.style.opacity = '0.5';
                    submitBtn.style.cursor = 'not-allowed';
                } else {
                    statusText.innerHTML = '<b style="color: #2e7d32;">Trạng thái: Tiêu đề hợp lệ</b>';
                }
            } else {
                statusText.innerHTML = '<b style="color: #2e7d32;">Trạng thái: Tiêu đề hợp lệ</b>';
            }
        } catch (error) {
            console.error('Lỗi API:', error);
        }
    }

function resetStatus() {
    const warningBox = document.getElementById('ai-warning-box');
    const submitBtn = document.querySelector('button[type="submit"]');
    const statusText = document.getElementById('title-check-status');

    if(warningBox) warningBox.style.display = 'none';
    if(submitBtn) {
        submitBtn.disabled = false; // Mở khóa nút
        submitBtn.style.opacity = '1';
        submitBtn.style.cursor = 'pointer';
    }
    if(statusText) statusText.innerHTML = '';
}