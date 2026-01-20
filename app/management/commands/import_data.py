import pandas as pd
import os
import random
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, is_naive
from app.models import User, Question, Answer, Tag


class Command(BaseCommand):
    help = 'Nạp 1000 dòng dữ liệu, xử lý triệt để lỗi khóa ngoại và timezone'

    def safe_date(self, date_str):
        dt = parse_datetime(str(date_str))
        if dt and is_naive(dt):
            return make_aware(dt)
        return dt

    def handle(self, *args, **kwargs):
        base_path = settings.BASE_DIR

        # 1. Đọc dữ liệu
        print("Đang chuẩn bị dữ liệu...")
        q_df = pd.read_csv(os.path.join(base_path, 'Cauhoi_cleaned.csv'), nrows=1000)
        q_ids = set(q_df['Id'].astype(int))
        ans_df_full = pd.read_csv(os.path.join(base_path, 'CautraLoi_cleaned.csv'))
        ans_df = ans_df_full[ans_df_full['QuestionId'].isin(q_ids)]

        # Lấy danh sách ID người dùng từ cả câu hỏi và câu trả lời
        user_ids_in_csv = set(q_df['OwnerUserId'].dropna().astype(int).astype(str))
        user_ids_in_csv.update(ans_df['OwnerUserId'].dropna().astype(int).astype(str))

        # 2. Nạp Users
        print(f"Đang kiểm tra và nạp người dùng...")
        user_df_full = pd.read_csv(os.path.join(base_path, 'user_cleaned.csv'))
        # Chỉ lấy những user thực sự có trong file user_cleaned.csv
        relevant_users = user_df_full[user_df_full['Id'].astype(str).isin(user_ids_in_csv)]

        valid_user_ids = set()
        for _, row in relevant_users.iterrows():
            uid = str(int(row['Id']))
            display_name = str(row['DisplayName']) if pd.notnull(row['DisplayName']) else f"User_{uid}"
            reputation = int(row['Reputation']) if pd.notnull(row['Reputation']) and row[
                'Reputation'] != 0 else random.randint(10, 1000)

            user, created = User.objects.get_or_create(
                id=uid,
                defaults={
                    'username': f"{''.join(filter(str.isalnum, display_name))}_{uid}",
                    'display_name': display_name,
                    'reputation': reputation,
                    'likes_count': int(row['llike'] or 0),
                    'dislikes_count': int(row['DisLike'] or 0),
                    'date_joined': self.safe_date(row['CreationDate'])
                }
            )
            valid_user_ids.add(uid)

        # 3. Nạp Questions
        print("Đang nạp câu hỏi (chỉ nạp nếu có User hợp lệ)...")
        for _, row in q_df.iterrows():
            owner_id = str(int(row['OwnerUserId'])) if pd.notnull(row['OwnerUserId']) else None

            # KIỂM TRA QUAN TRỌNG: Nếu không có user trong DB thì bỏ qua câu hỏi này
            if owner_id not in valid_user_ids:
                continue

            score = int(row['Score']) if pd.notnull(row['Score']) and row['Score'] != 0 else random.randint(1, 50)
            views = int(row['ViewCount']) if pd.notnull(row['ViewCount']) and row['ViewCount'] != 0 else random.randint(
                100, 5000)

            question, _ = Question.objects.get_or_create(
                id=int(row['Id']),
                defaults={
                    'title': row['Title'],
                    'body': row['Body'],
                    'creation_date': self.safe_date(row['CreationDate']),
                    'score': score,
                    'view_count': views,
                    'own_user_id': owner_id
                }
            )

            # Gán Tags
            tags_raw = str(row['Tags_List']).strip("[]").replace("'", "").split(",")
            for t_name in tags_raw:
                t_name = t_name.strip()
                if t_name and t_name != 'nan':
                    tag_obj, _ = Tag.objects.get_or_create(name=t_name)
                    question.tags.add(tag_obj)

        # 4. Nạp Answers
        print("Đang nạp câu trả lời...")
        for _, row in ans_df.iterrows():
            owner_id = str(int(row['OwnerUserId'])) if pd.notnull(row['OwnerUserId']) else None
            q_id = int(row['QuestionId'])

            # Kiểm tra cả User và Question phải tồn tại mới nạp Answer
            if owner_id in valid_user_ids and Question.objects.filter(id=q_id).exists():
                ans_score = int(row['AnswerScore']) if pd.notnull(row['AnswerScore']) and row[
                    'AnswerScore'] != 0 else random.randint(0, 30)

                Answer.objects.get_or_create(
                    id=int(row['AnswerId']),
                    defaults={
                        'question_id': q_id,
                        'own_user_id': owner_id,
                        'body': row['AnswerBody'],
                        'creation_date': self.safe_date(row['AnswerDate']),
                        'score': ans_score,
                    }
                )

        self.stdout.write(self.style.SUCCESS('Xong! Dữ liệu đã sạch và không còn lỗi khóa ngoại.'))