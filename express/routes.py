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


# Home route
@app.route('/')
@app.route('/index')
def index():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.date_posted.desc()).paginate(page=page,per_page=5)
    return render_template("index.html",posts=posts)

# route invoked when user cliks the About button in the Top Navbar
@app.route('/about')
def about():
    return render_template("about.html",title="About")

# route invoked when a new user register
@app.route('/register', methods=["POST","GET"])
def register():
    # if a user is already logged in
        # redirect to home 
    # else
        # create a new registration form instance and render it
        # On submit form 
            # validate the form 
            # hash the password
            # Add user to database
            # display a message 
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

# route invoked when user goes to login option
@app.route('/login',methods=["POST","GET"])
def login():
    # if user is already logged in
        # redirect the user to Home
    # else
        # render the login form to get details of user
        # validate the login form
        # on successful validation of login form 
            # make user login
        # if login unsuccessful
            # redirect back to login page
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

# route triggerd when a user clicks logout button
@app.route('/logout')
def logout():
    # logout the current user
    # redirect to Home Page
    logout_user()
    return redirect(url_for('index'))

# function to upload the profile picture of user
def save_picture(form_picture):
    # generate a random hex value for picture name
    random_hex = secrets.token_hex(8)
    # get the extension of image uploaded by the user
    _, f_ext = os.path.splitext(form_picture.filename)
    # merging the extension with the random name of picture
    picture_fn = random_hex + f_ext
    # getting the path where this image is to be saved
    picture_path = os.path.join(app.root_path, 'static/pics', picture_fn)
    
    # resizing the picture so that it will not take much space
    output_size = (125,125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)

    # save the new resized picture
    i.save(picture_path) 
    
    # return the picture name with extension (file name)
    return picture_fn


# route invoked when user visits the account page
@app.route('/account',methods=["GET","POST"])
@login_required   # render this route only when the user is logged in
def account():
    # provide form to update existing user information
        # create instance of update form
        # if form successfully validate on submit
        # update the changes in the database
        # display a suitable message
        # redirect user to account page with newly updated user information
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

# route invoked when a user creates a new post
@app.route('/new/post',methods=["GET","POST"])
@login_required
def new_post():
    # render the create post form
    # on submission of form if form validates
        # add the new post to the database
        # display a suitable flash message
        # redirect user to the home Page
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data,content=form.content.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Post created succesfully','success')
        return redirect(url_for('index'))
    return render_template('new_post.html',title="New Post",legend = 'New Post',form=form)

# route invoked when a user visits a particular post
@app.route('/post/<int:post_id>')
def post(post_id):
    # query for the clicked post with post id
        # if post exist 
            # display post
        # else
            # return 404 error
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', title=post.title, post=post)

# route invoked when a user tries to update the existing post
@app.route('/update/<int:post_id>/post',methods=["GET","POST"])
@login_required   # user must be logged in before updating the post
def update_post(post_id):
    # query for the post which is to be updated
    post = Post.query.get_or_404(post_id)
    # update the post only if the owner of the post tries to update the post
    # if person other then owner clicks the post
        # just show the post content only
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

# route invoked when post owner tries to delete the post
@app.route('/delete/<int:post_id>/post',methods=["POST"])
# user must be loggedin in order to delete the post
@login_required
def delete_post(post_id):
    # query for the post if the post exist
        # delete the post
        # show a suitable message
    # else
        # abort the action of delete
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!','success')
    return redirect(url_for('index'))

# route invoked to show all post of a particular user
@app.route('/user_post/<string:username>')
def user_post(username):
    page = request.args.get('page',1,type=int)
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).paginate(page=page,per_page=2)
    return render_template('user_post.html',posts=posts,title=current_user.username,user=user)

# function which sends the reset password email
# when the user chooses forgot password option
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

# route invoked when user chooses reset password option
@app.route('/reset_password',methods=["GET","POST"])
def reset_request():
    # render the reset password from to get the user whose password is to be reset
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('A password reset email has been sent to your registered email id','info')
        return redirect(url_for('login'))
    return render_template('reset_request.html',form=form, title="Reset Password")

# route invoked for taking input of the new password after reseting the password
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