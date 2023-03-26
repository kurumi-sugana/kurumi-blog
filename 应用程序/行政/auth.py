import functools
from flask import Blueprint, flash, render_template, request, redirect, url_for, session, g
from werkzeug.security import check_password_hash, generate_password_hash
from RealProject import db
from ..models import User
from app.admin.forms import CreateUserForm
from ..forms import LoginForm, RegisterForm
from app.blog.models import Comment

bp = Blueprint('auth', __name__, url_prefix='/auth',
               static_folder='../static', template_folder='../templates')


@bp.before_app_request
def load_logged_in_user():
    # 每个请求之前都回去session中查看user_id来获取用户
    user_id = session.get('user_id')

    # 注册用户即非管理员用户允许登录后查看的url
    urls = ['/auth/']

    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(int(user_id))

        # 权限判断
        if g.user.is_super_user and g.user.is_active:
            g.user.has_perm = 1
        elif not g.user.is_super_user and g.user.is_active and not g.user.is_staff and request.path in urls:
            g.user.has_perm = 1
        elif g.user.is_active and not g.user.is_staff:
            g.user.has_perm = 1
        else:
            g.user.has_perm = 0


def login_required(view):
    # 限制必须登录才能访问的页面装饰器
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            redirect_to = f"{url_for('auth.login')}?redirect_to={request.path}"
            return redirect(redirect_to)

        # 登录成功后对权限进行判断处理
        if not g.user.has_perm:
            return '<h1>无权限查看！</h1>'
        return view(**kwargs)

    return wrapped_view


@bp.route('/login', methods=['GET', 'POST'])
def login():
    # 登录
    redirect_to = request.args.get('redirect_to')

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        session.clear()
        session['user_id'] = user.id
        if redirect_to is not None:
            return redirect(redirect_to)
        return redirect('/')
    return render_template('login.html', form=form)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    # 注册视图
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, password=generate_password_hash(form.password.data))
        db.session.add(user)
        db.session.commit()
        session.clear()
        session['user_id'] = user.id
        return redirect('/')
    return render_template('register.html', form=form)


@bp.route('/logout')
def logout():
    # 注销
    session.clear()
    return redirect('/')


@bp.route('/')
@login_required
def userinfo():
    # 用户中心
    return render_template('userinfo.html')


@bp.route('/user/comment')
@login_required
def usercomment():
    # 我的评论
    page = request.args.get('page', 1, type=int)
    pagination = Comment.query.order_by(-Comment.add_date).filter_by(user=g.user).paginate(
        page=page, per_page=10, error_out=False)
    comment_list = pagination.items
    return render_template('usercomment.html', comment_list=comment_list, pagination=pagination)


@bp.route('/userinfo/edit', methods=['GET', 'POST'])
@login_required
def userinfo_edit():
    # 修改个人信息
    user = User.query.get(g.user.id)
    form = CreateUserForm(
        username=user.username,
        password=user.password,
        avatar=user.avatar,
        # is_super_user=user.is_super_user,
        # is_active=user.is_active,
        # is_staff=user.is_staff,
        gexing=user.gexing,
        desc=user.desc,
        email=user.email,
        gender=user.gender,
        address=user.address
    )
    if form.validate_on_submit():
        # user.username = form.username.data
        # 修改如下则代表不允许修改用户名
        user.username = g.user.username
        if not form.password.data:
            user.password = user.password
        else:
            user.password = generate_password_hash(form.password.data)
            # 考虑，这里如果修改了密码就应该清理session中的用户信息，使其重新登录
            session.clear()
        from app.admin.utils import upload_file_path
        f = form.avatar.data
        if user.avatar == f:
            user.avatar = user.avatar
        else:
            avatar_path, filename = upload_file_path('avatar', f)
            f.save(avatar_path)
            user.avatar = f'avatar/{filename}'

        # 不允许修改自己的状态
        # user.is_super_user = form.is_super_user.data
        # user.is_active = form.is_active.data
        # user.is_staff = form.is_staff.data
        user.gexing = form.gexing.data
        user.desc = form.desc.data
        user.email = form.email.data
        user.gender = form.gender.data
        user.address = form.address.data

        db.session.add(user)
        db.session.commit()
        flash(f'{user.username}修改成功！')
        return redirect(url_for('auth.userinfo'))
    return render_template('userform.html', form=form)
