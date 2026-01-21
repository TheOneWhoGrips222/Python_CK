import pandas as pd
import random
import re
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from app.models import User, Question, Answer, Vote, Report, Tag
from datetime import datetime


class Command(BaseCommand):
    help = 'Import 1000 records with full Tags, Users, Answers, and Votes'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Đang bắt đầu import dữ liệu kèm Tag...'))

        try:
            df_user = pd.read_csv('user_cleaned.csv')
            df_question = pd.read_csv('Cauhoi_cleaned.csv')
            df_answer = pd.read_csv('CautraLoi_cleaned.csv')
        except FileNotFoundError as e:
            self.stdout.write(self.style.ERROR(f'Lỗi: {e}'))
            return

        df_question = df_question.dropna(subset=['OwnerUserId'])
        df_question['OwnerUserId'] = df_question['OwnerUserId'].astype(int)
        df_user['Id'] = df_user['Id'].astype(int)

        merged_df = pd.merge(df_question, df_user, left_on='OwnerUserId', right_on='Id')
        df_final = merged_df.head(1000)

        count = 0
        with transaction.atomic():
            for _, row in df_final.iterrows():
                # 1. Xử lý User
                user_id = int(row['Id_y'])
                display_name = row['DisplayName'] if pd.notna(row['DisplayName']) else f"User_{user_id}"
                safe_username = "".join(x for x in display_name if x.isalnum()) + str(user_id)

                user, _ = User.objects.get_or_create(
                    id=user_id,
                    defaults={
                        'username': safe_username,
                        'display_name': display_name,
                        'email': f"{safe_username.lower()}@devcommunity.com",
                    }
                )

                # 2. Xử lý Question
                q_date = row['CreationDate_x']
                if pd.isna(q_date):
                    q_date = timezone.now()
                else:
                    try:
                        q_date = timezone.make_aware(datetime.strptime(str(q_date), '%Y-%m-%d %H:%M:%S'))
                    except:
                        q_date = timezone.now()

                q = Question.objects.create(
                    id=int(row['Id_x']),
                    title=row['Title'],
                    body=row['Body'],
                    own_user=user,
                    creation_date=q_date,
                    score=row['Score'] if pd.notna(row['Score']) else 0,
                    tags_raw=row['Tags'] if pd.notna(row['Tags']) else ""
                )

                # --- PHẦN XỬ LÝ TAG ---
                tags_str = row['Tags'] if pd.notna(row['Tags']) else ""
                # Dùng Regex để tìm nội dung giữa các dấu <>: <python><django> -> ['python', 'django']
                tag_names = re.findall(r'<(.*?)>', tags_str)

                tag_objects = []
                for name in tag_names:
                    tag_obj, _ = Tag.objects.get_or_create(name=name)
                    tag_objects.append(tag_obj)

                if tag_objects:
                    q.tags.set(tag_objects)  # Lưu vào bảng ManyToMany
                # ----------------------

                # 3. Tạo 1 Answer ngẫu nhiên để test status "Đã trả lời"
                ans_sample = df_answer.sample(1).iloc[0]
                Answer.objects.create(
                    question=q,
                    body=ans_sample['AnswerBody'],
                    own_user=user,
                    creation_date=timezone.now()
                )
                q.answer_count = 1

                # 4. Tạo Vote (Dùng update_or_create để tránh lỗi UNIQUE)
                Vote.objects.update_or_create(
                    user=user,
                    question=q,
                    defaults={'value': random.choice([1, -1])}
                )

                # 5. Tạo Report (10% ngẫu nhiên)
                if random.random() < 0.1:
                    Report.objects.create(
                        own_user=user,
                        question=q,
                        reason="Báo cáo mẫu",
                        status='Pending'
                    )

                q.save()
                count += 1
                if count % 100 == 0:
                    self.stdout.write(f"Đã import {count} câu hỏi kèm Tag...")

        self.stdout.write(self.style.SUCCESS(f'Xong! Đã import {count} bản ghi đầy đủ Tag.'))