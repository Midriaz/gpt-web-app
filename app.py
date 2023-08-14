from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc
from functools import wraps
import openai
from flask_migrate import Migrate
from flaskext.markdown import Markdown
import config


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WHITELISTED_IPS = os.getenv("WHITELISTED_IPS").split(',')
OPENAI_ORGANIZATION = os.getenv("OPENAI_ORGANIZATION")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gpt.db')
app.secret_key = os.getenv("FLASK_SECRET_KEY")
db = SQLAlchemy(app)
migrate = Migrate(app, db)
# db.init_app(app)
# db.create_all()

Markdown(app, extensions=['fenced_code', 'tables'])

openai.organization = OPENAI_ORGANIZATION
openai.api_key = OPENAI_API_KEY


class Conversation(db.Model):
    __tablename__ = "conversation"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50), nullable=False)
    messages = db.relationship('Message', backref='conversation', lazy=True)

    # This is the display name for the model when queried
    def __repr__(self):
        return f"{self.name}"

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)

def limit_ip_access(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        # if request.remote_addr not in WHITELISTED_IPS:
        #     abort(403)  # Forbidden
        return func(*args, **kwargs)
    return decorated


def get_response(conversation, prompt):
    # Format the messages for the OpenAI API
    messages = [{"role": message.role, "content": message.content} for message in conversation.messages]
    messages.append({"role": "user", "content": prompt})

    response = openai.ChatCompletion.create(
      model=config.MODEL,
      messages=messages
    )
    return response['choices'][0]['message']['content']


def render_home(id = None, new = False):
    # order by the newest message
    conversations = db.session.query(Conversation)\
        .join(Message, Conversation.id == Message.conversation_id)\
        .order_by(desc(Message.id)).all()

    if id:
        conversation = Conversation.query.get(id)
    elif len(conversations) > 0 and not new:
        conversation = conversations[0]
    else:
        # Create a new Conversation object
        conversation = Conversation(title="Untitled Conversation")
        db.session.add(conversation)
        db.session.commit()

        # Add the system message at the beginning
        message = Message(role='system', content="You are a helpful assistant.", conversation_id=conversation.id)
        db.session.add(message)
        # Save the changes to the database
        db.session.commit()
    return render_template('home.html', conversations=conversations, conversation=conversation) 


@app.route('/')
@limit_ip_access
def main_menu():
    return render_home()

@app.route('/chat/<int:id>')
@limit_ip_access
def view_chat(id):
    return render_home(id=id)

@app.route('/chat/new', methods=['GET'])
@limit_ip_access
def new_chat():
    return render_home(new=True)


@app.route('/chat/<int:id>/regenerate', methods=['POST'])
@limit_ip_access
def regenerate_response(id):
    conversation = Conversation.query.get(id)

    # Get the last assistant's message and delete it
    last_assistant_message = Message.query.filter_by(conversation_id=id, role='assistant').order_by(Message.id.desc()).first()
    db.session.delete(last_assistant_message)

    # Get the last user's message
    last_user_message = Message.query.filter_by(conversation_id=id, role='user').order_by(Message.id.desc()).first()

    # Generate a new response using the OpenAI API
    new_response = get_response(conversation, last_user_message.content)

    # Create a new Message object for the assistant's response
    new_assistant_message = Message(role="assistant", content=new_response, conversation_id=id)
    db.session.add(new_assistant_message)

    # Save the changes to the database
    db.session.commit()

    # Redirect back to the chat view
    return redirect(url_for('view_chat', id=id))



@app.route('/chat/<int:id>/send', methods=['POST'])
@limit_ip_access
def send_message(id):
    # Get the conversation
    conversation = Conversation.query.get(id)

    # Get the message from the form data
    message = request.form.get('message')

    # Create a new Message object for the user's message
    user_message = Message(role="user", content=message, conversation_id=id)
    db.session.add(user_message)

    # Generate a response using the OpenAI API
    response = get_response(conversation, message)

    # Create a new Message object for the assistant's response
    assistant_message = Message(role="assistant", content=response, conversation_id=id)
    db.session.add(assistant_message)

     # Save the changes to the database
    db.session.commit()

    # If this is the first user message, update the conversation title
    if len(conversation.messages) == 3:
        messages = [
            {"role": "user", "content": user_message.content}, 
            {"role": "assistant", "content": assistant_message.content},
            {"role": "user", "content": "Name our conversation (max 50 chars)"} 
        ]
        response = openai.ChatCompletion.create(
            model=config.MODEL,
            messages=messages
        )
        title = response['choices'][0]['message']['content']
        title = title.replace('"', '')
        conversation.title = title[:50]
        db.session.commit()

    # Redirect back to the chat view
    return redirect(url_for('view_chat', id=id))

@app.route('/myip', methods=['get'])
def show_ip():
    return request.remote_addr
