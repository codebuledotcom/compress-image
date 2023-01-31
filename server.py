import os, datetime, bson, mimetypes, hashlib, schedule
from flask import Flask, request, send_file, make_response, redirect, render_template, jsonify
from PIL import Image
from flask_cors import CORS
from fakeredis import FakeStrictRedis
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
redis = FakeStrictRedis()

CORS(app, origins='*')

app.config['SECONDS'] 				= int(os.environ.get('EXPIRES', 2419200))  # 30 day
app.config['SECRET_KEY'] 			= os.environ.get('SECRET_KEY', '-w@8sp$gcafk*+sqis#+356smh%a1xs^ff^zz8b4%%e7i8t!wo')
app.config['UPLOAD_FOLDER'] 		= os.environ.get('UPLOAD_FOLDER', 'temp/')
app.config['ALLOWED_EXTENSIONS'] 	= {'.png', '.jpg', '.webp', '.svg', '.gif', '.bmp'}
app.config['MAX_FILE_SIZE'] 		= int(os.environ.get('MAX_FILE_SIZE', 20 * 1024 * 1024)) 
app.config['SCHEME'] 				= os.environ.get('SCHEME', 'http')
app.config['S3']					= os.environ.get('S3', 'False')

def getall_file():
	if app.config['S3'] == 'True':
		response = s3.list_objects(Bucket=bucket_name)
		if 'Contents' in response:
			objects = response['Contents']
			for obj in objects:
				# Download the image from S3
				EXTENSIONS = os.path.splitext(obj['Key'])
				if EXTENSIONS and not (EXTENSIONS[1] in {'.svg', '.gif'}):
					image_data = s3.get_object(Bucket=bucket_name, Key=obj['Key'])['Body'].read()
					if image_data[0:6] != b'redire':
						# Create a new SHA-256 hash object
						hash_object = hashlib.sha256()
						# Update the hash object with the video file data
						hash_object.update(image_data)
						# Get the hexadecimal representation of the hash
						hex_hash = hash_object.hexdigest()
						value = redis.get(hex_hash)
						if value is None:
							redis.set(hex_hash, obj['Key'])
						else:
							s3.put_object(Bucket=bucket_name, Key=obj['Key'], Body='redirect:' + value.decode())
							
	else:
		files = os.listdir(app.config['UPLOAD_FOLDER'])
		for filename in files:
			# Open the file
			FULL = app.config['UPLOAD_FOLDER'] +  filename
			with open(FULL, 'rb+') as file: # rbw
				# Read the contents of the file
				contents = file.read()
				if contents[0:6] != b'redire':
					hash_object = hashlib.sha256()
					hash_object.update(contents)
					hex_hash = hash_object.hexdigest()
					value = redis.get(hex_hash)
					if value is None:
						redis.set(hex_hash, filename)
					else:
						w_value = "redire:"+value.decode()
						file.close()
						with open(FULL, 'wb') as file:
							file.write(w_value.encode())
		
schedule.every().day.at("10:00").do(getall_file)

def file_remove(full_file_name):
    if os.path.exists(full_file_name):
        os.remove(full_file_name)

def compress_image(full_file_name, EXTENSIONS):
	if EXTENSIONS == '.gif':
		return True
	elif EXTENSIONS == '.svg':
		return True
	else:
		try:
			image = Image.open(full_file_name)
			image.save(full_file_name, 'webp')
			return True
		except IOError:
			print('compress_image :', IOError)
			file_remove(full_file_name)
			return False

def has_cache_other(full_file_name, file_name):
    # Create a new SHA-256 hash object
    hash_object = hashlib.sha256()
    with open(full_file_name, "rb") as file:
        file_data = file.read()
    # Update the hash object with the video file data
    hash_object.update(file_data)
    # Get the hexadecimal representation of the hash
    hex_hash = hash_object.hexdigest()
    value = redis.get(hex_hash)
    if value is None:
        redis.set(hex_hash, file_name)
    else:
        return value.decode()
			
@app.route('/', methods=['GET', 'POST'])
def upload():
	if request.method == 'POST':
		file = request.files['file']
		messages 	= 'No file found in the request'
		success		= False
		if file:
			EXTENSIONS 		= os.path.splitext(file.filename)[1]
			file_name 		= str(bson.ObjectId()) + EXTENSIONS
			full_file_name 	= app.config['UPLOAD_FOLDER'] + file_name
			file.save(full_file_name)
			
			if compress_image(full_file_name, EXTENSIONS):
				value = has_cache_other(full_file_name, file_name)
				if value is not None:
					file_remove(full_file_name)
					messages = app.config['SCHEME'] + '://' + request.host + '/media/'+ value
				else:
					messages = app.config['SCHEME'] + '://' + request.host + '/media/'+ file_name
				success  = True
			else:
				messages = 'do not use image files'
		
		return jsonify({'success': success, 'messages':messages})
	else:
		response = make_response(render_template('upload.html', max_file_size=app.config['MAX_FILE_SIZE'] ) )
		expires = datetime.datetime.now() + datetime.timedelta(seconds=app.config['SECONDS'])
		response.headers['Expires'] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
		response.headers['Cache-Control'] = 'max-age='+str(app.config['SECONDS'])
		response.headers['content-security-policy'] = "default-src 'self'; script-src 'self' https://trusted.com"
		return response


def is_support_webp(accept_header):
    return (("*/*" in accept_header) or ("webp" in accept_header))
		
		
########## cdn ###########
@app.route('/media/<url>', methods=['get'])
def index(url):
	if len(request.args) > 0:
		response	= make_response(redirect("/media/" + url))
		expires 	= datetime.datetime.now() + datetime.timedelta(seconds=app.config['SECONDS'])
		response.headers['Expires'] 		= expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
		response.headers['Cache-Control'] 	= 'max-age='+str(app.config['SECONDS'])
		return response
    
	if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], url)):
		support_webp = is_support_webp(request.headers.get("Accept"))
		if support_webp:
			with open(os.path.join(app.config['UPLOAD_FOLDER'], url), 'rb') as file:
				# Read the contents of the file
				contents = file.read()
				file.close()
				if contents[0:6] == b'redire':
					response 	= make_response(redirect("/media/" + contents[7:].decode()))
					expires 	= datetime.datetime.now() + datetime.timedelta(seconds=app.config['SECONDS'])
					response.headers['Expires'] 		= expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
					response.headers['Cache-Control'] 	= 'max-age='+str(app.config['SECONDS'])
					return response
			mime_type, encoding = mimetypes.guess_type(os.path.join(app.config['UPLOAD_FOLDER'], url))
			response = make_response(send_file(os.path.join(app.config['UPLOAD_FOLDER'], url), mimetype=mime_type))
			expires = datetime.datetime.now() + datetime.timedelta(seconds=app.config['SECONDS'])
			response.headers['Expires'] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
			response.headers['Cache-Control'] = 'max-age='+str(app.config['SECONDS'])
			return response
		else:
			response	= make_response(send_file('templates/webp.png', mimetype='image/webp'))
			expires 	= datetime.datetime.now() + datetime.timedelta(seconds=seconds)
			response.headers['Expires'] 		= expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
			response.headers['Cache-Control'] 	= 'max-age='+str(seconds)
			return response
	
	expires 	= datetime.datetime.now() + datetime.timedelta(seconds=600)
	response 	= make_response('Bad URL hash', 404)
	response.headers['Expires'] 		= expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
	response.headers['Cache-Control'] 	= 'max-age='+str(600)
	return response

	
@app.route('/robots.txt', methods=['get'])
def robots():
    expires 	= datetime.datetime.now() + datetime.timedelta(seconds=app.config['SECONDS'])
    response 	= make_response(send_file('robots.txt'))
    response.headers['Expires'] 		= expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
    response.headers['Cache-Control'] 	= 'max-age='+str(app.config['SECONDS'])
    return response
	
# /favicon.ico
@app.route('/favicon.ico', methods=['get'])
def favicon():
	_seconds 	= app.config['SECONDS'] * 2
	expires 	= datetime.datetime.now() + datetime.timedelta(seconds=_seconds)
	response 	= make_response(send_file('favicon.png'))
	response.headers['Expires'] 		= expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
	response.headers['Cache-Control'] 	= 'max-age='+str(_seconds)
	return response, 200

@app.before_request
def limit_content_length():
    request.enforce_content_length = app.config['MAX_FILE_SIZE']
	
@app.errorhandler(404)
def page_not_found(e):
	expires 	= datetime.datetime.now() + datetime.timedelta(seconds=app.config['SECONDS'])
	response 	= make_response('', 404)
	response.headers['Expires'] 		= expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
	response.headers['Cache-Control'] 	= 'max-age='+str(app.config['SECONDS'])
	return response

if __name__ == "__main__":
	if not os.path.exists(app.config['UPLOAD_FOLDER']):
		os.mkdir(app.config['UPLOAD_FOLDER'])
	getall_file()
	app.run(host="0.0.0.0", port=8080, debug=True)

	
	