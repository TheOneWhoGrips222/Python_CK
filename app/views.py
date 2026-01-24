from datetime import date
import datetime  # Đã gộp từ nhánh mới
from urllib import request

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django import forms
from django.core.paginator import Paginator
from django.utils import timezone
from .models import Question, Answer, Tag, Vote, Report
from django.db.models import Count, Sum, Q
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .ai_search import find_similar_questions_ai
from .ai_tagging import suggest_tags_ai  # Giữ lại AI tagging
import html
from django.utils.html import strip_tags



User = get_user_model()


def cap_nhat_reputation_he_thong(user, hanh_dong, nguoi_thuc_hien=None):
    """
    hanh_dong: 'up_q', 'down_q', 'up_a', 'down_a', 'accept', 'unaccept', 'cancel_vote'
    """
    if not user: return

    # BẢNG ĐIỂM QUY ĐỊNH
    bang_diem = {
        'up_q': 5,  # like câu hỏi
        'up_a': 10,  # like câu trả lời
        'down_q': -2,  # Bị dislike câu hỏi
        'down_a': -2,  # Bị dislike câu trả lời
        'accept': 15,  # Được chọn là câu trả lời đúng
        'unaccept': -15,  # Bị bỏ chọn câu trả lời đúng
    }

    diem_thay_doi = bang_diem.get(hanh_dong, 0)

    # 1. Cập nhật cho người Đặt
    user.reputation = max(0, user.reputation + diem_thay_doi)
    user.save(update_fields=['reputation'])

    # 2. Logic phụ cho người trả lời
    if nguoi_thuc_hien and nguoi_thuc_hien != user:
        if hanh_dong in ['down_q', 'down_a']:
            nguoi_thuc_hien.reputation = max(0, nguoi_thuc_hien.reputation - 1)  # Phạt người downvote
        elif hanh_dong == 'accept':
            nguoi_thuc_hien.reputation += 2  # Thưởng người chọn vì đã giúp cộng đồng
        nguoi_thuc_hien.save(update_fields=['reputation'])

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")

    class Meta:
        model = User
        fields = ("username", "email")


def home(request):
    sort = request.GET.get('sort', 'newest')
    questions = Question.objects.all()

    if sort == 'hot':
        questions = questions.order_by('-score', '-creation_date')
    elif sort == 'views':
        questions = questions.order_by('-view_count', '-creation_date')
    else:
        questions = questions.order_by('-creation_date')

    # Bước 2: Thiết lập phân trang
    items_per_page = 15
    paginator = Paginator(questions, items_per_page)
    page_number = request.GET.get('page')

    questions = paginator.get_page(page_number)

    context = {
        'questions': questions,
        'current_sort': sort
    }
    return render(request, 'app/home.html', context)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                if user.is_superuser or user.is_staff:
                    return redirect('admin_dashboard')
                else:
                    return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'app/login.html', {'form': form})


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = SignUpForm()
    return render(request, 'app/register.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('home')


from django.db.models import Q


def question_detail(request, id):
    question = get_object_or_404(Question, id=id)

    # Logic tăng lượt xem (giữ nguyên của bạn)
    viewed_questions = request.session.get('viewed_questions', [])
    if id not in viewed_questions:
        question.view_count += 1
        question.save()
        viewed_questions.append(id)
        request.session['viewed_questions'] = viewed_questions


    question.likes = question.votes.filter(value=1).count()
    question.dislikes = question.votes.filter(value=-1).count()
    question.score = question.likes - question.dislikes  # Điểm = Like - Dislike

    # Trạng thái nút bấm của user
    question.user_vote = 0
    if request.user.is_authenticated:
        user_q_vote = question.votes.filter(user=request.user).first()
        if user_q_vote:
            question.user_vote = user_q_vote.value


    if request.user.is_staff:
        answers_list = question.answers.all().order_by('-creation_date')
    elif request.user.is_authenticated:
        answers_list = question.answers.filter(Q(is_hidden=False) | Q(own_user=request.user)).order_by('-creation_date')
    else:
        answers_list = question.answers.filter(is_hidden=False).order_by('-creation_date')

    paginator = Paginator(answers_list, 5)
    page_number = request.GET.get('page')
    answers = paginator.get_page(page_number)

    # TÍNH TOÁN ĐIỂM CHO TỪNG CÂU TRẢ LỜI
    for answer in answers:
        answer.likes = answer.votes.filter(value=1).count()
        answer.dislikes = answer.votes.filter(value=-1).count()
        answer.score = answer.likes - answer.dislikes  # Điểm = Like - Dislike

        answer.user_vote = 0
        if request.user.is_authenticated:
            user_a_vote = answer.votes.filter(user=request.user).first()
            if user_a_vote:
                answer.user_vote = user_a_vote.value

    # Logic POST answer (giữ nguyên)
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')
        if question.accepted_answer:
            return redirect('question_detail', id=id)
        content = request.POST.get('content')
        if content:
            Answer.objects.create(question=question, body=content, own_user=request.user)
            return redirect('question_detail', id=id)

    return render(request, 'app/question.html', {
        'question': question,
        'answers': answers,
        'total_answers_count': answers_list.count()
    })

@login_required(login_url='login')
def add_question(request):
    if request.method == 'POST':
        title = (request.POST.get('title') or "").strip()
        body = (request.POST.get('body') or "").strip()
        tag_data = (request.POST.get('tags') or "").strip()  # user có thể bỏ trống

        if not title or not body:
            return render(request, 'app/AddQuestion.html', {"error": "Vui lòng nhập tiêu đề và nội dung."})

        if Question.objects.filter(title__iexact=title).exists():
            return render(request, 'app/AddQuestion.html',{
                "error": "Câu hỏi này đã tồn tại trên hệ thống. Vui lòng sử dụng tính năng tìm kiếm hoặc đặt một tiêu đề khác.",
                "old_title": title,
                "old_body": body,
            })

        # 1) Tạo câu hỏi trước
        question = Question.objects.create(
            title=title,
            body=body,
            own_user=request.user,
            creation_date=timezone.now()
        )

        # 2) Manual tags (user nhập)
        manual_tags = []
        if tag_data:
            manual_tags = [t.strip().lower() for t in tag_data.replace(',', ' ').split() if t.strip()]

        # 3) Clean text trước khi AI (loại HTML + unescape)
        clean_title = strip_tags(html.unescape(title)).strip()
        clean_body = strip_tags(html.unescape(body)).strip()

        # 4) AI tags (tự gán)
        ai_suggestions = suggest_tags_ai(
            clean_title,
            clean_body,
            top_k=12,
            threshold=0.15
        )
        ai_tags = [name for name, _score in ai_suggestions]

        # 5) Merge manual + AI (unique)
        merged = []
        for t in manual_tags + ai_tags:
            t = (t or "").strip().lower()
            if t and t not in merged:
                merged.append(t)

        # số tag tối đa lưu/hiển thị (bạn muốn nhiều hơn 5 thì tăng lên)
        MAX_TAGS = 5
        merged = merged[:MAX_TAGS]

        # 6) Save M2M + tags_raw
        raw_string = ""
        for tag_name in merged:
            tag_obj, _ = Tag.objects.get_or_create(name=tag_name)
            question.tags.add(tag_obj)
            raw_string += f"<{tag_name}>"

        question.tags_raw = raw_string if raw_string else None
        question.save()

        return redirect('quest-page')

    return render(request, 'app/AddQuestion.html')


def tags_view(request):
    query = request.GET.get('search', '')
    tags = Tag.objects.all()

    if query:
        tags = tags.filter(name__icontains=query)

    tags = tags.annotate(num_questions=Count('questions')).order_by('-num_questions')
    tag_count = tags.count()

    paginator = Paginator(tags, 15)
    page_number = request.GET.get('page')
    tags = paginator.get_page(page_number)

    return render(request, 'app/tag.html', {
        'tags': tags,
        'tagcount': tag_count,
        'query': query
    })


def users_view(request):
    users = User.objects.all()
    user_count = User.objects.count()
    items_per_page = 20
    paginator = Paginator(users, items_per_page)
    page_number = request.GET.get('page')
    users = paginator.get_page(page_number)
    context = {'users': users,
               'usercount': user_count}
    return render(request, 'app/user.html', context)


@login_required(login_url='login')
def user_profile(request, username):
    profile_user = get_object_or_404(User, username=username)

    likes = Vote.objects.filter(question__own_user=profile_user, value=1).count() + \
            Vote.objects.filter(answer__own_user=profile_user, value=1).count()

    dislikes = Vote.objects.filter(question__own_user=profile_user, value=-1).count() + \
               Vote.objects.filter(answer__own_user=profile_user, value=-1).count()

    # Cập nhật vào database
    profile_user.likes_count = likes
    profile_user.dislikes_count = dislikes
    profile_user.save(update_fields=['likes_count', 'dislikes_count'])  # Lưu cụ thể 2 trường này

    user_questions = Question.objects.filter(own_user=profile_user).order_by('-creation_date')

    context = {
        'profile_user': profile_user,
        'user_questions': user_questions,
    }
    return render(request, 'app/ManageUser.html', context)


def question_page(request):
    questions = Question.objects.all().order_by('-creation_date').prefetch_related('tags')
    tag_count = Tag.objects.count()
    paginator = Paginator(questions, 15)
    page_number = request.GET.get('page')
    questions = paginator.get_page(page_number)
    user_count = User.objects.all().count()
    question_count = Question.objects.all().count()

    context = {'questions': questions,
               'user_count': user_count,
               'question_count': question_count,
               'tagcount': tag_count,

               }
    return render(request, 'app/question-list.html', context)


@staff_member_required(login_url='login')
def admin_dashboard(request):
    user_count = User.objects.count()
    question_count = Question.objects.count()
    answer_count = Answer.objects.count()
    report_count = Report.objects.count()
    tag_count = Tag.objects.count()

    today = datetime.date.today()
    days = []
    counts = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        days.append(d.strftime('%d/%m'))
        counts.append(Question.objects.filter(creation_date__date=d).count())

    resp_days = []
    resp_values = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        resp_days.append(d.strftime('%d/%m'))

        qs_day = Question.objects.filter(creation_date__date=d, answers__isnull=False).distinct()

        if qs_day.exists():
            total_seconds_day = 0
            for q in qs_day:
                first_ans = q.answers.order_by('creation_date').first()
                total_seconds_day += (first_ans.creation_date - q.creation_date).total_seconds()

            avg_h_day = round((total_seconds_day / qs_day.count()) / 3600, 1)
            resp_values.append(avg_h_day)
        else:
            resp_values.append(0)

    top_users = User.objects.all().order_by('-reputation')[:5]
    user_labels = [u.username for u in top_users]
    user_reps = [u.reputation if u.reputation else 0 for u in top_users]

    top_tags = Tag.objects.annotate(num_questions=Count('questions')).order_by('-num_questions')[:7]
    questions = Question.objects.all().order_by('-creation_date')[:5]

    context = {
        'user_count': user_count,
        'question_count': question_count,
        'answer_count': answer_count,
        'report_count': report_count,
        'tag_count': tag_count,
        'days': days,
        'counts': counts,
        'resp_days': resp_days,
        'resp_values': resp_values,
        'user_labels': user_labels,
        'user_reps': user_reps,
        'top_tags': top_tags,
        'questions': questions,
    }
    return render(request, 'app/admin.html', context)


def delete_question(request, id):
    Question.objects.filter(id=id).delete()
    return redirect('admin_question')


def admin_users(request):
    noi_dung_tim_kiem = request.GET.get('search', '')
    list_user = User.objects.all()

    if noi_dung_tim_kiem != "":
        list_user = list_user.filter(username__icontains=noi_dung_tim_kiem)

    paginator = Paginator(list_user, 15)
    page_number = request.GET.get('page')
    users_paginated = paginator.get_page(page_number)
    context = {
        'users': users_paginated,
        'search_query': noi_dung_tim_kiem,
    }
    return render(request, 'app/admin_user.html', context)


def admin_question(request):
    questions_list = Question.objects.all().select_related('own_user')
    search_val = request.GET.get('search', '').strip()
    follow_val = request.GET.get('folow', 'DEF')
    time_val = request.GET.get('time', 'new')
    status_val = request.GET.get('status', 'default')

    if search_val:
        if follow_val == 'ID':
            questions_list = questions_list.filter(id__icontains=search_val)
        elif follow_val == 'USER':
            questions_list = questions_list.filter(own_user__username__icontains=search_val)
        elif follow_val == 'TAG':
            questions_list = questions_list.filter(tags_raw__icontains=f"<{search_val}>")
        elif follow_val == 'TITLE':
            questions_list = questions_list.filter(title__icontains=search_val)

    if status_val == 'answered':
        questions_list = questions_list.filter(answers__isnull=False).distinct()
    elif status_val == 'notans':
        questions_list = questions_list.filter(answers__isnull=True)
    elif status_val == 'report':
        questions_list = questions_list.filter(reports__isnull=False).distinct()

    questions_list = questions_list.order_by('creation_date' if time_val == 'old' else '-creation_date')

    paginator = Paginator(questions_list, 15)
    page_number = request.GET.get('page')
    questions_obj = paginator.get_page(page_number)

    context = {
        'questions': questions_obj,
        'search_val': search_val,
        'follow_val': follow_val,
        'time_val': time_val,
        'status_val': status_val,
    }
    return render(request, 'app/admin_question.html', context)


def delete_admin_question(request, id):
    Question.objects.filter(id=id).delete()
    return redirect('admin_question')


def toggle_staff(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.is_staff:
        user.is_staff = False
        messages.success(request, f"Đã hạ cấp quyền Staff của {user.username}")
    else:
        user.is_staff = True
        messages.success(request, f"Đã thăng cấp {user.username} lên làm Staff")
    user.save()
    return redirect('admin_users')


def toggle_active(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.is_active:
        user.is_active = False
        messages.warning(request, f"Đã khóa tài khoản {user.username}")
    else:
        user.is_active = True
        messages.success(request, f"Đã mở khóa tài khoản {user.username}")
    user.save()
    return redirect('admin_users')


def admin_tag(request):
    noi_dung_tim_kiem = request.GET.get('search', '')
    list_tag = Tag.objects.all().order_by('-id')
    if noi_dung_tim_kiem != "":
        list_tag = list_tag.filter(name__icontains=noi_dung_tim_kiem)

    paginator = Paginator(list_tag, 15)
    page_number = request.GET.get('page')
    tags_paginated = paginator.get_page(page_number)
    context = {
        'tags': tags_paginated,
        'search_query': noi_dung_tim_kiem,
    }
    return render(request, 'app/admin_tag.html', context)


def del_tag(request, id):
    Tag.objects.filter(id=id).delete()
    return redirect('admin_tag')


def admin_answer(request):
    answer_list = Answer.objects.all()
    search_val = request.GET.get('search', '').strip()
    follow_val = request.GET.get('folow', 'DEF')
    time_val = request.GET.get('time', 'new')
    status_val = request.GET.get('status', 'default')

    if search_val and follow_val == 'USER':
        answer_list = answer_list.filter(own_user__username__icontains=search_val)

    if status_val == 'hidden':
        answer_list = answer_list.filter(is_hidden=True)
    elif status_val == 'active':
        answer_list = answer_list.filter(is_hidden=False)

    answer_list = answer_list.order_by('creation_date' if time_val == 'old' else '-creation_date')

    paginator = Paginator(answer_list, 15)
    page_number = request.GET.get('page')
    answer_obj = paginator.get_page(page_number)

    context = {
        'answers': answer_obj,
        'search_val': search_val,
        'follow_val': follow_val,
        'time_val': time_val,
        'status_val': status_val,
    }
    return render(request, 'app/admin_answer.html', context)


def del_answer(request, id):
    Answer.objects.filter(id=id).delete()
    return redirect('admin_answer')


def toggle_answer(request, id):
    answer = get_object_or_404(Answer, id=id)
    answer.is_hidden = not answer.is_hidden
    answer.save()
    return redirect('admin_answer')



def admin_report(request):

    reports_list = Report.objects.all().select_related('own_user', 'question', 'answer')


    search_val = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', 'all')


    if search_val:
        reports_list = reports_list.filter(own_user__username__icontains=search_val)


    if status_filter != 'all':
        reports_list = reports_list.filter(status=status_filter)

    reports_list = reports_list.order_by('-creation_date')


    paginator = Paginator(reports_list, 15)
    page_number = request.GET.get('page')
    reports_obj = paginator.get_page(page_number)

    context = {
        'reports': reports_obj,
        'search_val': search_val,
        'status_filter': status_filter,
    }
    return render(request, 'app/admin_report.html', context)


def resolve_report(request, id):
    report = get_object_or_404(Report, id=id)
    report.status = 'Resolved'
    report.save()
    messages.success(request, f"Đã đánh dấu báo cáo #{id} là đã xử lý.")
    return redirect('admin_report')

@staff_member_required(login_url='login')
def toggle_hide_answer(request, id):
    answer = get_object_or_404(Answer, id=id)
    answer.is_hidden = not answer.is_hidden
    answer.save()
    status = "đã ẩn" if answer.is_hidden else "đã hiện lại"
    messages.success(request, f"Câu trả lời {status}.")
    return redirect('question_detail', id=answer.question.id)



@login_required
def accept_answer(request, id):
    answer = get_object_or_404(Answer, id=id)
    question = answer.question

    if request.user != question.own_user:
        return redirect('question_detail', id=question.id)

    # Gộp logic xử lý database và tính điểm vào một chỗ
    if question.accepted_answer == answer:
        question.accepted_answer = None
        question.save()
        cap_nhat_reputation_he_thong(answer.own_user, 'unaccept')
    else:
        question.accepted_answer = answer
        question.save()
        cap_nhat_reputation_he_thong(answer.own_user, 'accept', nguoi_thuc_hien=request.user)

    return redirect('question_detail', id=question.id)


def search_similar_questions(request):
    """API trả về JSON danh sách câu hỏi tương tự dùng AI"""
    query = request.GET.get('q', '')
    if len(query) > 5:
        all_questions = list(Question.objects.all().order_by('-creation_date')[:500])
        ai_results = find_similar_questions_ai(query, all_questions, top_k=5, threshold=0.5)
        results = []
        for item in ai_results:
            q = item['question']
            similarity_percent = round(item['score'] * 100)
            results.append({
                'title': q.title,
                'url': reverse('question_detail', args=[q.id]),
                'answers': q.answers.count(),
                'similarity': similarity_percent
            })
        return JsonResponse({'results': results})
    return JsonResponse({'results': []})


@login_required
def manage_account(request):
    user = request.user

    # Tính toán lại trước khi hiển thị
    user.likes_count = Vote.objects.filter(question__own_user=user, value=1).count() + \
                       Vote.objects.filter(answer__own_user=user, value=1).count()
    user.dislikes_count = Vote.objects.filter(question__own_user=user, value=-1).count() + \
                          Vote.objects.filter(answer__own_user=user, value=-1).count()
    user.save(update_fields=['likes_count', 'dislikes_count'])

    user_questions = Question.objects.filter(own_user=user).order_by('-creation_date')

    return render(request, 'app/ManageUser.html', {
        'profile_user': user,
        'user_questions': user_questions,
    })


@login_required(login_url='login')
def report_content(request, content_type, content_id):
    # content_type sẽ là 'question' hoặc 'answer'
    reason = request.POST.get('reason', 'Nội dung không phù hợp')

    if content_type == 'question':
        obj = get_object_or_404(Question, id=content_id)
        q_id = obj.id
        report_filter = {'question': obj}
    else:
        obj = get_object_or_404(Answer, id=content_id)
        q_id = obj.question.id
        report_filter = {'answer': obj}

    # Kiểm tra xem đã báo cáo chưa
    if Report.objects.filter(own_user=request.user, **report_filter).exists():
        messages.warning(request, "Bạn đã báo cáo nội dung này rồi!")
    else:
        Report.objects.create(
            own_user=request.user,
            reason=reason,
            status='Pending',
            **report_filter
        )

        # Logic tự động ẩn nếu bị báo cáo nhiều (áp dụng cho cả 2)
        report_count = Report.objects.filter(**report_filter).count()
        if report_count > 3:
            obj.is_hidden = True  # Đảm bảo Model Question cũng có trường is_hidden
            obj.save()
            messages.warning(request, "Nội dung đã bị ẩn do nhận nhiều báo cáo.")
        else:
            messages.success(request, f"Cảm ơn bạn đã báo cáo. (Hiện có {report_count} báo cáo)")

    return redirect('question_detail', id=q_id)


def toggle_lock_question(request, question_id):
    #Đóng mở câu trả lời
    question = get_object_or_404(Question, id=question_id)
    #Người dặt mới dc quyền
    if request.user == question.own_user:
        if question.accepted_answer:
            question.accepted_answer = None
            messages.success(request, "Đã mở khóa câu hỏi thành công.")
        else:
            messages.warning(request, "Bạn cần chọn một câu trả lời đúng để khóa thảo luận.")

        question.save()
    else:
        messages.error(request, "Bạn không có quyền thực hiện thao tác này.")

    return redirect('question_detail', id=question.id)


@login_required(login_url='login')

def vote(request, content_type, content_id, vote_type):
    if not request.user.is_authenticated:
        return redirect('login')

    model = Question if content_type == 'question' else Answer
    obj = get_object_or_404(model, id=content_id)
    value = 1 if vote_type == 'up' else -1

    existing_vote = obj.votes.filter(user=request.user).first()

    if existing_vote:
        if existing_vote.value == value:
            # Người dùng bấm lại nút cũ -> Xóa vote (Hủy vote)
            existing_vote.delete()
        else:

            existing_vote.value = value
            existing_vote.save()

    else:
        # CHỈ CỘNG ĐIỂM KHI VOTE MỚI HOÀN TOÀN
        obj.votes.create(user=request.user, value=value)

        if value == 1:
            hanh_dong = 'up_q' if content_type == 'question' else 'up_a'
            cap_nhat_reputation_he_thong(obj.own_user, hanh_dong)
        else:
            hanh_dong = 'down_q' if content_type == 'question' else 'down_a'
            cap_nhat_reputation_he_thong(obj.own_user, hanh_dong, nguoi_thuc_hien=request.user)

    question_id = obj.id if content_type == 'question' else obj.question.id
    return redirect('question_detail', id=question_id)


def edit_tag(request, tag_id):
    tag = get_object_or_404(Tag, id=tag_id)

    if request.method == "POST":
        new_description = request.POST.get('description', '').strip()
        tag.description = new_description
        tag.save()
        return redirect('admin_tag')

    return render(request, 'app/edit_tag.html', {'tag': tag})

def del_question_user(request, id):
    question = get_object_or_404(Question, id=id)
    question.delete()
    return redirect('manage_account')