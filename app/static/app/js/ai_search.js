
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('global-search-input');
    const searchResults = document.getElementById('global-search-results');
    let searchTimeout = null;

    if (!searchInput || !searchResults) return; // Nếu không tìm thấy element thì dừng

    // Bắt sự kiện khi gõ phím
    searchInput.addEventListener('input', function() {
        const query = this.value.trim();

        // Xóa timeout cũ (Debounce)
        clearTimeout(searchTimeout);

        if (query.length < 2) {
            searchResults.style.display = 'none';
            return;
        }

        // Đợi 300ms sau khi ngừng gõ mới gọi API
        searchTimeout = setTimeout(() => {
            fetch(`/api/search_similar/?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    searchResults.innerHTML = ''; // Xóa kết quả cũ

                    if (data.results && data.results.length > 0) {
                        // Hiển thị tiêu đề
                        const header = document.createElement('div');
                        header.style.padding = '8px 15px';
                        header.style.fontSize = '11px';
                        header.style.fontWeight = 'bold';
                        header.style.color = '#6a737c';
                        header.style.backgroundColor = '#f8f9f9';
                        header.innerText = 'GỢI Ý TỪ AI';
                        searchResults.appendChild(header);

                        // Hiển thị từng kết quả
                        data.results.forEach(item => {
                            const div = document.createElement('div');
                            div.className = 'nav-search-item';
                            div.innerHTML = `
                                <span class="nav-item-title">${item.title}</span>
                                <div class="nav-item-meta">
                                    <span><i class="fas fa-check-circle" style="color: ${item.answers > 0 ? '#2e7d32' : '#ccc'}"></i> ${item.answers} trả lời</span>
                                    <span style="color: #e67e22;">Độ giống: ${item.similarity}%</span>
                                </div>
                            `;

                            // Click thì chuyển trang
                            div.addEventListener('click', () => {
                                window.location.href = item.url;
                            });

                            searchResults.appendChild(div);
                        });
                        searchResults.style.display = 'block';
                    } else {
                        // Nếu không tìm thấy gì
                        searchResults.innerHTML = '<div style="padding:15px; text-align:center; color:#6a737c;">Không tìm thấy kết quả phù hợp</div>';
                        searchResults.style.display = 'block';
                    }
                })
                .catch(error => console.error('Error:', error));
        }, 300);
    });

    // Ẩn khi click ra ngoài
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.style.display = 'none';
        }
    });

    // Hiện lại khi focus vào ô input
    searchInput.addEventListener('focus', function() {
        if (this.value.length >= 2 && searchResults.innerHTML !== '') {
            searchResults.style.display = 'block';
        }
    });
});
