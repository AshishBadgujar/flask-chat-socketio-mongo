from flask import Flask,render_template,request,redirect,url_for,flash
from flask_socketio import SocketIO,join_room,leave_room
from flask_login import LoginManager,login_user,logout_user,login_required,current_user
from db import get_user,save_user,save_room,add_room_member,is_room_admin,is_room_member,add_room_members,remove_room_members,get_rooms_for_user,get_room_members,get_room,update_room,save_message,get_messages
from pymongo.errors import DuplicateKeyError

app=Flask(__name__)
socketio=SocketIO(app)
app.secret_key="my secret key"

login_manager=LoginManager()
login_manager.init_app(app)
login_manager.login_view='login'

@app.route('/')
def home():
    rooms=[]
    if current_user.is_authenticated:
        rooms=get_rooms_for_user(current_user.username)
    return render_template('index.html',rooms=rooms)


@app.route('/signup',methods=['GET',"POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method=='POST':
        username=request.form.get('username')
        email=request.form.get('email')
        password_input=request.form.get('password')
        try:
            save_user(username,email,password_input)
            flash('user created successfully !','success')
            return redirect(url_for('login'))
        except DuplicateKeyError:
            flash('user already exist !','danger')
    return render_template('signup.html')



@app.route('/login',methods=['GET',"POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method=='POST':
        username=request.form.get('username')
        password_input=request.form.get('password')
        user=get_user(username)

        if user and user.check_password(password_input):
            login_user(user)
            flash('You are logged in successfully !','success')
            return redirect(url_for('home'))

        else:
            flash('log in error !','danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/create-room',methods=['GET','POST'])
@login_required
def create_room():
    if request.method=='POST':
        room_name=request.form.get('room_name')
        usernames=[ username.strip() for username in request.form.get('members').split(',')]
        created_by=current_user.username
        if len(room_name) and len(usernames):
            room_id=save_room(room_name,created_by)

            if current_user.username in usernames:
                usernames.remove(current_user.username)
            add_room_members(room_id,room_name,usernames,current_user.username)
            flash('Room is created !','success')
            return redirect(url_for('view_room',room_id=room_id))
        else:
            flash('failed to create a room !','danger')
    return render_template('create_room.html')


@app.route('/rooms/<room_id>')
@login_required
def view_room(room_id):
    room=get_room(room_id)
    if room and is_room_member(room_id,current_user.username):
        room_members=get_room_members(room_id)
        admin=is_room_admin(room_id,current_user.username)
        messages=get_messages(room_id)
        return render_template('view_room.html',username=current_user.username,room=room,room_members=room_members,is_admin=admin,messages=messages)
    else:
        return 'room not found',404


@app.route('/rooms/<room_id>/edit',methods=['GET','POST'])
@login_required
def edit_room(room_id):
    room=get_room(room_id)
    if room and is_room_admin(room_id,current_user.username):
        existing_room_members=[member['_id']['username'] for member in get_room_members(room_id)]
       
        if request.method=='POST':
            room_name=request.form.get('room_name')
            room['name']=room_name
            update_room(room_id,room_name)

            new_members=[ username.strip() for username in request.form.get('members').split(',')]
            members_to_add=list(set(new_members)-set(existing_room_members))
            members_to_remove=list(set(existing_room_members)-set(new_members))

            if len(members_to_add):
                add_room_members(room_id,room_name,members_to_add,current_user.username)
            
            if len(members_to_remove):
                remove_room_members(room_id,members_to_remove)
            flash('Room edited successfully !','success')
            room_members_str=",".join(new_members)
        
        room_members_str=",".join(existing_room_members)
        return render_template('edit_room.html',room=room,room_members_str=room_members_str)



@socketio.on('join_room')
def handle_join_room_event(data):
    join_room(data['room'])
    socketio.emit('join_room_announcement',data)


@socketio.on('send_message')
def handle_send_message_event(data):
    save_message(data['room'],data['message'],data['username'])
    socketio.emit('receive_message',data,room=data['room'])


@socketio.on('leave_room')
def handle_leave_room_event(data):
    leave_room(data['room'])
    socketio.emit('leav_room_announcement',data)




@login_manager.user_loader
def load_user(username):
    return get_user(username)


if __name__ == "__main__":
    socketio.run(app, debug=True)