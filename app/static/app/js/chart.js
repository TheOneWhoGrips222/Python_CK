<script>
    // 1. Cấu hình Biểu đồ Đường (Tăng trưởng nội dung)
    const ctxLine = document.getElementById('lineChart').getContext('2d');
    new Chart(ctxLine, {
        type: 'line',
        data: {
            labels: {{ days|safe }}, // Nhận dữ liệu từ Django
            datasets: [{
                label: 'Câu hỏi mới',
                data: {{ counts|safe }}, // Nhận dữ liệu từ Django
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                borderWidth: 3,
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } }
        }
    });

    // 2. Cấu hình Biểu đồ Tròn (Tỷ lệ dữ liệu)
    const ctxPie = document.getElementById('pieChart').getContext('2d');
    new Chart(ctxPie, {
        type: 'doughnut',
        data: {
            labels: ['Câu hỏi', 'Trả lời', 'Báo cáo'],
            datasets: [{
                data: [{{ question_count }}, {{ answer_count }}, {{ report_count }}],
                backgroundColor: ['#f48225', '#10b981', '#dc2626'],
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%'
        }
    });
</script>