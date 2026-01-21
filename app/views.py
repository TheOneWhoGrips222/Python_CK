from datetime import date
from urllib import request

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse
from .ai_search import find_similar_questions_ai
from django.shortcuts import redirect, get_object_or_404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django import forms
from django.core.paginator import Paginator

from django.urls import reverse
from django.utils import timezone



from .models import Question, Answer, Tag , Vote,Report
from django.db.models import Count
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .ai_search import find_similar_questions_ai


User = get_user_model()

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
        'questions': questions,  # Bây giờ 'questions' đã có thuộc tính .has_other_pages
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

def question_detail(request, id):
    question = get_object_or_404(Question, id=id)
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')

        if question.accepted_answer:
            return redirect('question_detail', id=id)

        content = request.POST.get('content')
        if content:
            Answer.objects.create(
                question=question,
                body=content,
                own_user=request.user
            )
            return redirect('question_detail', id=id)
    return render(request, 'app/question.html', {'question': question})

@login_required(login_url='login')
def add_question(request):
    # 1. Kiểm tra đăng nhập
    if not request.user.is_authenticated:
        return redirect('login')

    if request.method == 'POST':
        title = request.POST.get('title')
        body = request.POST.get('body')
        tag_data = request.POST.get('tags')

        if title and body:

            question = Question.objects.create(
                title=title,
                body=body,
                own_user=request.user,
                creation_date= timezone.now()
            )


            if tag_data:

                tag_list = [t.strip().lower() for t in tag_data.replace(',', ' ').split() if t.strip()]

                raw_string = ""

                for tag_name in tag_list[:5]:

                    tag_obj, created = Tag.objects.get_or_create(name=tag_name)


                    question.tags.add(tag_obj)


                    raw_string += f"<{tag_name}>"

                # 4. Cập nhật lại trường tags_raw vào câu hỏi
                question.tags_raw = raw_string
                question.save()

            return redirect('quest-page')

    return render(request, 'app/AddQuestion.html')


def tags_view(request):
    tags = Tag.objects.annotate(num_questions=Count('questions')).order_by('-num_questions')
    tag_count = Tag.objects.count();
    paginator = Paginator(tags, 15)
    page_number = request.GET.get('page')
    tags = paginator.get_page(page_number)
    return render(request, 'app/tag.html', {'tags': tags,'tagcount':tag_count})


def users_view(request):
    users = User.objects.all()
    user_count = User.objects.count();
    items_per_page = 20
    paginator = Paginator(users, items_per_page)
    page_number = request.GET.get('page')
    users = paginator.get_page(page_number)
    context = {'users': users,
               'usercount': user_count}
    return render(request, 'app/user.html', context)

@login_required(login_url='login')
def user_profile(request, username):
    # Lấy thông tin user dựa trên username từ URL
    profile_user = get_object_or_404(User, username=username)

    # --- TÍNH TOÁN ĐIỂM ---

    q_score_sum = Question.objects.filter(own_user=profile_user).aggregate(Sum('score'))['score__sum'] or 0


    a_score_sum = Answer.objects.filter(own_user=profile_user).aggregate(Sum('score'))['score__sum'] or 0

    # Tính tổng Reputation
    profile_user.reputation = (q_score_sum * 5) + (a_score_sum * 10)



    likes = Vote.objects.filter(question__own_user=profile_user, value=1).count() + \
            Vote.objects.filter(answer__own_user=profile_user, value=1).count()

    dislikes = Vote.objects.filter(question__own_user=profile_user, value=-1).count() + \
               Vote.objects.filter(answer__own_user=profile_user, value=-1).count()


    profile_user.likes_count = likes
    profile_user.dislikes_count = dislikes
    profile_user.save()

    # Lấy danh sách câu hỏi của user này
    user_questions = Question.objects.filter(own_user=profile_user).order_by('-creation_date')

    context = {
        'profile_user': profile_user,
        'user_questions': user_questions,
    }
    return render(request, 'app/ManageUser.html', context)

def question_page(request):
    questions = Question.objects.all().order_by('-creation_date').prefetch_related('tags')
    tag_count = Tag.objects.count();
    paginator = Paginator(questions, 15)  # Mỗi trang 15 câu
    page_number = request.GET.get('page')
    questions = paginator.get_page(page_number)  # Gán lại vào biến 'questions'
    user_count = User.objects.all().count()
    question_count = Question.objects.all().count()

    context = {'questions': questions,
               'user_count': user_count,
               'question_count': question_count,
               'tagcount' : tag_count
               }

    return render(request, 'app/question-list.html',context)


@staff_member_required(login_url='login')
def admin_dashboard(request):
    current_username = request.user.username
    questions = Question.objects.all().order_by('-creation_date')[:10]
    user_count = User.objects.all().count()
    question_count = Question.objects.all().count()
    answer_count = Answer.objects.all().count()
    report_count = Report.objects.all().count()
    context = {'questions': questions,
               'user_count': user_count,
               'question_count': question_count,
               'answer_count': answer_count,
               'report_count': report_count,
               'username': current_username
               }
    return render(request, 'app/admin.html',context)

def delete_question(request, id):
    Question.objects.filter(id=id).delete()
    return redirect('admin_dashboard')


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

    return render(request, 'app/admin_user.html',context)
def admin_question(request):
    # 1. Khởi tạo QuerySet
    questions_list = Question.objects.all().select_related('own_user')

    # 2. Lấy dữ liệu từ GET
    search_val = request.GET.get('search', '').strip()
    follow_val = request.GET.get('folow', 'DEF')
    time_val = request.GET.get('time', 'new')
    status_val = request.GET.get('status', 'default')

    # 3. Logic Tìm kiếm
    if search_val:
        if follow_val == 'ID':
            questions_list = questions_list.filter(id__icontains=search_val)
        elif follow_val == 'USER':
            questions_list = questions_list.filter(own_user__username__icontains=search_val)
        elif follow_val == 'TAG':
            questions_list = questions_list.filter(tags_raw__icontains=f"<{search_val}>")
        elif follow_val == 'TITLE':
            questions_list = questions_list.filter(title__icontains=search_val)

    # 4. Logic Lọc trạng thái (Dùng cách này để không bị lỗi FieldError)
    if status_val == 'answered':
        questions_list = questions_list.filter(answers__isnull=False).distinct()
    elif status_val == 'notans':
        # Lấy những câu hỏi mà bảng Answer không có dữ liệu trỏ về
        questions_list = questions_list.filter(answers__isnull=True)
    elif status_val == 'report':
        questions_list = questions_list.filter(reports__isnull=False).distinct()

    # 5. Sắp xếp
    questions_list = questions_list.order_by('creation_date' if time_val == 'old' else '-creation_date')

    # 6. Phân trang
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


    if user.is_staff == True:
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




def search_similar_questions(request):
    """API trả về JSON danh sách câu hỏi tương tự cho tính năng Autocomplete"""
    query = request.GET.get('q', '')
    if len(query) > 2:
        # Tìm các câu hỏi có tiêu đề chứa từ khóa (không phân biệt hoa thường)
        questions = Question.objects.filter(title__icontains=query)[:5]
        results = []
        for q in questions:
            results.append({
                'title': q.title,
                'url': reverse('question_detail', args=[q.id]), # Tạo link đến câu hỏi đó
                'answers': q.answers.count() # Số câu trả lời hiện có
            })
        return JsonResponse({'results': results})
    return JsonResponse({'results': []})

# Yêu cầu đăng nhập
@login_required

def accept_answer(request, id):
    # Lấy câu trả lời theo id
    answer = get_object_or_404(Answer, id=id)
    question = answer.question

    # Kiểm tra bảo mật: chỉ người tạo câu hỏi mới được quyền chấp nhận
    if request.user != question.own_user:
        return redirect('question_detail', id=question.id)

    if question.accepted_answer == answer:
        question.accepted_answer = None
    else:
        question.accepted_answer = answer

    question.save()
    return redirect('question_detail', id=question.id)


def search_similar_questions(request):
    """API trả về JSON danh sách câu hỏi tương tự dùng AI"""
    query = request.GET.get('q', '')


    if len(query) > 5:

        # Lấy tất cả câu hỏi để so sánh
        all_questions = list(Question.objects.all().order_by('-creation_date')[:500])

        # Gọi hàm AI xử lý

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


@login_required
def manage_account(request):

    user = request.user


    user_questions = Question.objects.filter(own_user=user).order_by('-creation_date')


    if request.method == 'POST':

        new_email = request.POST.get('email')
        if new_email:
            user.email = new_email
            user.save()
            messages.success(request, "Cập nhật thông tin thành công!")
            return redirect('manage_account')

    context = {
        'profile_user': user,
        'user_questions': user_questions,
    }
    return render(request, 'app/ManageUser.html', context)
