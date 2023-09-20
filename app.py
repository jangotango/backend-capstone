from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from datetime import datetime
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from sqlalchemy.orm import joinedload

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.sqlite'
app.config['SECRET_KEY'] = 'darkchaos'
app.config['JWT_SECRET_KEY'] = 'darkchaos'  # Add a secret key for JWT


db = SQLAlchemy(app)
ma = Marshmallow(app)
jwt = JWTManager(app) 

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

    def __init__(self, email, password):
        self.email = email
        self.password = password
    
    posts = db.relationship("Post", backref="user")

class Post(db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __init__(self, user_id, content):
        self.user_id = user_id
        self.content = content

class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User

user_schema = UserSchema()
users_schema = UserSchema(many=True)

class PostSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Post

    user_email = ma.Method("get_user_email")

    def get_user_email(self, post):
        return post.user.email if post.user else None # Assuming User has an 'email' field

post_schema = PostSchema()
posts_schema = PostSchema(many=True)


@app.route('/register', methods=["POST"])
def register_user():
    try:
        email = request.json['email']
        password = request.json['password']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({"message": "Email address already registered"}), 400

        new_user = User(email=email, password=password)

        db.session.add(new_user)
        db.session.commit()

        return user_schema.jsonify(new_user)
    except Exception as e:
        app.logger.exception(f"Error in /register: {e}")
        return jsonify({"message": "Registration failed"}), 500

@app.route('/login', methods=["POST"])
def login_route():
    email = request.json['email']
    password = request.json['password']

    user = User.query.filter_by(email=email, password=password).first()

    if user:
        access_token = create_access_token(identity=user.id)
        return jsonify({"message": "Login successful", "token": access_token})
    else:
        return jsonify({"message": "Login failed"}), 401

@app.route('/get_posts', methods=["GET"])
def get_posts():
    posts = Post.query.options(joinedload(Post.user)).all()  # Fetch posts from the database
    return jsonify(posts_schema.dump(posts))

@app.route('/create_post', methods=["POST"])
@jwt_required()
def create_post():
    try:
        user_id = get_jwt_identity()  # Get the user ID from the JWT token
        content = request.json['content']
        
        new_post = Post(user_id=user_id, content=content)  # Use user_id parameter

        db.session.add(new_post)
        db.session.commit()

        return jsonify({
            "message": "Post created successfully",
            "post": {
                "id": new_post.id,
                "content": new_post.content,
                "timestamp": new_post.timestamp
            }
        }), 201
    except Exception as e:
        app.logger.exception(f"Error in /create_post: {e}")
        return jsonify({"message": "Failed to create post"}), 500

@app.route('/delete_post/<int:post_id>', methods=["DELETE"])
@jwt_required()
def delete_post(post_id):
    try:
        post = Post.query.get(post_id)
        if not post:
            return jsonify({"message": "Post not found"}), 404
        
        user_id = get_jwt_identity()
        if post.user_id != user_id:
            return jsonify({"message": "You do not have permission to delete this post"}), 403
        
        db.session.delete(post)
        db.session.commit()
        
        return jsonify({"message": "Post deleted successfully"}), 200
    except Exception as e:
        app.logger.exception(f"Error in /delete_post: {e}")
        return jsonify({"message": "Failed to delete post"}), 500


@app.after_request
def after_request(response):
    response.headers.set('Access-Control-Allow-Origin', 'http://localhost:3000')
    response.headers.set('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.set('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


if __name__ == '__main__':
    app.run(debug=True)