
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone


# 1. Bảng User
# Columns: Id, DisplayName, CreationDate, Reputation, llike, DisLike
class User(AbstractUser):

    display_name = models.CharField(max_length=100, blank=True, null=True, help_text="DisplayName trong CSV")
    reputation = models.IntegerField(default=0, help_text="Reputation trong CSV")

    likes_count = models.IntegerField(default=0, help_text="Tổng số like nhận được (llike)")
    dislikes_count = models.IntegerField(default=0, help_text="Tổng số dislike nhận được (DisLike)")

    profile_image_url = models.URLField(max_length=255, blank=True, null=True)
    about_me = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.username or self.display_name or "User"


# 2. Bảng Tag
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# 3. Bảng Question
# Columns: Id, Title, Body, CreationDate, Tags, Score, AnswerCount, ViewCount, FavoriteCount, AcceptedAnswerId, ClosedDate, OwnerUserId
class Question(models.Model):
    title = models.CharField(max_length=255)  # Title
    body = models.TextField()  # Body
    creation_date = models.DateTimeField(default=timezone.now)  # CreationDate

    score = models.IntegerField(default=0)  # Score
    view_count = models.IntegerField(default=0)  # ViewCount
    favorite_count = models.IntegerField(default=0)  # FavoriteCount
    answer_count = models.IntegerField(default=0)  # AnswerCount (Có thể tính dynamic nhưng lưu cứng để query nhanh)

    closed_date = models.DateTimeField(null=True, blank=True)  # ClosedDate

    # Tags (Dạng chuỗi gốc từ CSV, ví dụ: <python><pandas>)
    tags_raw = models.CharField(max_length=255, blank=True, null=True)
    # Tags (Quan hệ ManyToMany để lọc và tìm kiếm)
    tags = models.ManyToManyField(Tag, related_name='questions', blank=True)

    # OwnerUserId -> Liên kết với bảng User
    own_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                 related_name='questions')

    # AcceptedAnswerId -> Liên kết 1-1 với Answer
    accepted_answer = models.OneToOneField('Answer', on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='accepted_for_question')

    @property
    def get_status_display(self):
        # Import local để tránh vòng lặp import
        from .models import Report, Answer

        # 1. Kiểm tra báo cáo (Ưu tiên cao nhất)
        if Report.objects.filter(question=self).exists():
            return 'reported'

        # 2. Kiểm tra thực tế xem có câu trả lời nào không
        if Answer.objects.filter(question=self).exists():
            return 'answered'

        # 3. Mặc định
        return 'pending'


# 4. Bảng Answer
# Columns: AnswerId, QuestionId, AnswerDate, AnswerScore, AnswerBody, OwnerUserId
class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')  # QuestionId
    body = models.TextField()  # AnswerBody
    creation_date = models.DateTimeField(default=timezone.now)  # AnswerDate
    score = models.IntegerField(default=0)  # AnswerScore

    # OwnerUserId
    own_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='answers')

    # Trường bổ sung để hỗ trợ hiển thị nhanh
    is_accepted = models.BooleanField(default=False)

    is_hidden = models.BooleanField(default=False, help_text="Đánh dấu ẩn (do admin ẩn hoặc bị report)")

    class Meta:
        ordering = ['-is_accepted', '-score', 'creation_date']

    def __str__(self):
        return f"Answer {self.id} for {self.question.title}"

    def get_status_display(self):
        # False là hiển thị -> Hoạt động
        if not self.is_hidden:
            return 'active'

        # True là đang ẩn -> reported (để khớp với class red của bạn)
        return 'hidden'


# 5. Bảng Vote
class Vote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, null=True, blank=True, related_name='votes')
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, null=True, blank=True, related_name='votes')

    VOTE_TYPES = (
        (1, 'Upvote'),
        (-1, 'Downvote'),
    )
    value = models.SmallIntegerField(choices=VOTE_TYPES)
    creation_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ('user', 'question'),
            ('user', 'answer')
        ]


# 6. Bảng Report
class Report(models.Model):
    own_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')

    reason = models.TextField(help_text="Lý do báo cáo")
    status = models.CharField(max_length=20, default='Pending',
                              choices=[('Pending', 'Chờ xử lý'), ('Resolved', 'Đã xử lý')])
    creation_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):

        return f"Report by {self.own_user}"



