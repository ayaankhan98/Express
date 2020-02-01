import os
import secrets
from flask import render_template, url_for, flash, redirect, request, abort
from express import app, db, bcrypt, mail
from flask_mail import Message
from PIL import Image
from express.forms import (RegistrationForm, LoginForm, UpdateAccountForm, PostForm,
                             RequestResetForm, ResetPasswordForm)
from express.models import User, Post
from flask_login import login_user, current_user, logout_user, login_required


@app.route('/')
@app.route('/index')
def index():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.date_posted.desc()).paginate(page=page,per_page=5)
    return render_template("index.html",posts=posts)

@app.route('/about')
def about():
    return render_template("about.html",title="About")


@app.route('/register', methods=["POST","GET"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data,email=form.email.data,password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash(f'Account Created for {form.username.data}!, You can now LogIn','success')
        return redirect(url_for('login'))
    return render_template('register.html',title="Registration", form=form)

@app.route('/login',methods=["POST","GET"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password,form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash(f'Successfully Logged In as {form.email.data}!','success')
            return redirect(url_for('account')) if next_page else redirect(url_for('index'))
        else:
            flash('Login Unsuccessfull, Please check Email and Password !','danger')
    return render_template('login.html',title="Login", form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/pics', picture_fn)
    
    output_size = (125,125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path) 
    
    return picture_fn


@app.route('/account',methods=["GET","POST"])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!','success')
        return redirect(url_for('account'))
    elif request.method == "GET":
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename=f'pics/{current_user.image_file}')
    return render_template("account.html",image_file=image_file, form=form)

@app.route('/new/post',methods=["GET","POST"])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data,content=form.content.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Post created succesfully','success')
        return redirect(url_for('index'))
    return render_template('new_post.html',title="New Post",legend = 'New Post',form=form)

@app.route('/post/<int:post_id>')
def post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', title=post.title, post=post)

@app.route('/update/<int:post_id>/post',methods=["GET","POST"])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        flash('Your post has been updated Succesfully !','success')
        return redirect(url_for('post', post_id=post.id))
    elif request.method=="GET":
        form.title.data = post.title
        form.content.data = post.content
    return render_template('new_post.html',title='Update Post', legend = 'Update Post', form=form)

@app.route('/delete/<int:post_id>/post',methods=["POST"])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!','success')
    return redirect(url_for('index'))

@app.route('/user_post/<string:username>')
def user_post(username):
    page = request.args.get('page',1,type=int)
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).paginate(page=page,per_page=2)
    return render_template('user_post.html',posts=posts,title=current_user.username,user=user)


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                    sender='noreply@demo.com',
                    recipients=[user.email])
    msg.body = f'''This is a password reset email requested
    by you from FlaskBlog, To reset your password visi the follow link
    {url_for('reset_token', token=token, _external=True)}
    '''
    mail.send(msg)

@app.route('/reset_password',methods=["GET","POST"])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('A password reset email has been sent to your registered email id','info')
        return redirect(url_for('login'))
    return render_template('reset_request.html',form=form, title="Reset Password")


@app.route('/reset_password/<token>',methods=["GET","POST"])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_token(token)
    if not user:
        flash('Verification Failed Invald or Expired Token','warning')
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Your password has been successfully updated! You can log in now','success')
        return redirect(url_for('login'))
    return render_template('reset_token.html',title="Reset Password",form=form)