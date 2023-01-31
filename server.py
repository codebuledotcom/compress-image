import boto3, os, datetime
from flask import Flask, request, send_file, make_response, redirect, render_template, jsonify
from PIL import Image
from flask_cors import CORS

app = Flask(__name__)
session = boto3.session.Session()

app.config['SECONDS'] = int(os.environ.get('EXPIRES', 3600))  # 1 hour
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '-w@8sp$gcafk*+sqis#+356smh%a1xs^ff^zz8b4%%e7i8t!wo')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'temp/')
app.config['ALLOWED_EXTENSIONS'] = {'.png', '.jpg', '.webp', '.svg', '.gif', '.bmp'}
app.config['MAX_FILE_SIZE'] = int(os.environ.get('MAX_FILE_SIZE', 20 * 1024 * 1024)) 


# connect server s3
s3 = session.client(
    's3',
    endpoint_url = os.environ.get('ENDPOINT_URL', None),
    aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID', None),
    aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY', None),
)


def isimage():
	
	return True

@app.route("/", methods = ['GET'])
def index(): 
    return '', 200



@app.route('/robots.txt', methods=['get'])
def robots():
    expires = datetime.datetime.now() + datetime.timedelta(seconds=app.config['SECONDS'])
    response = make_response(send_file('robots.txt'))
    response.headers['Expires'] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
    response.headers['Cache-Control'] = 'max-age='+str(app.config['SECONDS'])
    return response
	
# /favicon.ico
@app.route('/favicon.ico', methods=['get'])
def favicon():
	_seconds = app.config['SECONDS'] * 2
	expires = datetime.datetime.now() + datetime.timedelta(seconds=_seconds)
	response = make_response(send_file('favicon.png'))
	response.headers['Expires'] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
	response.headers['Cache-Control'] = 'max-age='+str(_seconds)
	return response, 200
	
@app.errorhandler(404)
def page_not_found(e):
    return '', 404

if __name__ == "__main__":
	if not os.path.exists(app.config['UPLOAD_FOLDER']):
		os.mkdir(app.config['UPLOAD_FOLDER'])
	app.run(host="0.0.0.0", port=8080, debug=True)