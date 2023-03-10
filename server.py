import os, datetime, bson, mimetypes, hashlib, schedule, boto3, io
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
app.config['ALLOWED_EXTENSIONS'] 	= {'.png', '.jpg', '.webp', '.svg', '.gif', '.bmp', '.ico'}
app.config['MAX_FILE_SIZE'] 		= int(os.environ.get('MAX_FILE_SIZE', 50 * 1024 * 1024)) 
app.config['SCHEME'] 				= os.environ.get('SCHEME', 'http')
app.config['S3']					= os.environ.get('S3', 'False')
app.config['BUCKET_NAME'] = os.environ.get('BUCKET_NAME', None)

if app.config['S3'] == 'True':
	session = boto3.session.Session()
	s3 = session.client(
		's3',
		endpoint_url = os.environ.get('ENDPOINT_URL', None),
		aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID', None),
		aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY', None),
	)

########### s3 ###########
def upload_to_s3(full_file_name, file_name, extra_args = {}):
	try:
		s3.head_object(Bucket=app.config['BUCKET_NAME'], Key=file_name)
		file_remove(full_file_name)
		return True
	except s3.exceptions.ClientError as e:
		error_code = e.response['Error']['Code']
		if error_code == '404':
			s3.upload_file(full_file_name, app.config['BUCKET_NAME'], file_name, extra_args)
			file_remove(full_file_name)
			return True
		else:
			print('Error bucket', app.config['BUCKET_NAME'])
			file_remove(full_file_name)
			return False
	except Exception as e:
		file_remove(full_file_name)
		print(f"An error occurred: {e}")
		return False
	
def getall_file():
	if app.config['S3'] == 'True':
		response = s3.list_objects(Bucket=app.config['BUCKET_NAME'])
		if 'Contents' in response:
			objects = response['Contents']
			for obj in objects:
				# Download the image from S3
				EXTENSIONS = os.path.splitext(obj['Key'])
				if EXTENSIONS and not (EXTENSIONS[1] in {'.svg', '.gif'}):
					image_data = s3.get_object(Bucket=app.config['BUCKET_NAME'], Key=obj['Key'])['Body'].read()
					if image_data[0:8] != b'redirect':
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
							s3.put_object(Bucket=app.config['BUCKET_NAME'], Key=obj['Key'], Body='redirect:' + value.decode())
							
	else:
		files = os.listdir(app.config['UPLOAD_FOLDER'])
		for filename in files:
			# Open the file
			FULL = app.config['UPLOAD_FOLDER'] +  filename
			with open(FULL, 'rb+') as file: # rbw
				# Read the contents of the file
				contents = file.read()
				if contents[0:8] != b'redirect':
					hash_object = hashlib.sha256()
					hash_object.update(contents)
					hex_hash = hash_object.hexdigest()
					value = redis.get(hex_hash)
					if value is None:
						redis.set(hex_hash, filename)
					else:
						w_value = "redirect:"+value.decode()
						file.close()
						with open(FULL, 'wb') as file:
							file.write(w_value.encode())
		
schedule.every().day.at("10:00").do(getall_file)

def file_remove(full_file_name):
    if os.path.exists(full_file_name):
        os.remove(full_file_name)

def compress_image(full_file_name, EXTENSIONS):
	if EXTENSIONS in {'.gif', '.svg'}:
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
					success  = True
				else:
					if app.config['S3'] == 'True':
						if upload_to_s3(full_file_name, file_name, extra_args = {
                            'ContentType': file.content_type,
                            'CacheControl': str(app.config['SECONDS']),
                            'Metadata': {
                                'ip': request.headers.get("Do-Connecting-Ip") or request.remote_addr,
                                'datetime': datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S')
                            }
                        }):
							messages = app.config['SCHEME'] + '://' + request.host + '/media/'+ file_name
							success  = True
						else:
							messages = 'error upload to s3'
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
				if contents[0:8] == b'redirect':
					response 	= make_response(redirect("/media/" + contents[9:].decode()))
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
	elif app.config['S3'] == 'True':
		response = s3.get_object(Bucket=app.config['BUCKET_NAME'], Key=url)
		image_data = response['Body'].read()
		if image_data[0:8] == b'redirect': # redirect
			response = make_response(redirect("/media/" + image_data[9:].decode()))
			expires = datetime.datetime.now() + datetime.timedelta(seconds=app.config['SECONDS'])
			response.headers['Expires'] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
			response.headers['Cache-Control'] = 'max-age='+str(app.config['SECONDS'])
			return response
		else:
			file_object = io.BytesIO(image_data)
			file_object.seek(0)
			response = make_response(send_file(file_object, mimetype=response['ContentType']))
			expires = datetime.datetime.now() + datetime.timedelta(seconds=app.config['SECONDS'])
			response.headers['Expires'] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
			response.headers['Cache-Control'] = 'max-age='+str(app.config['SECONDS'])
			return response
	
	expires 	= datetime.datetime.now() + datetime.timedelta(seconds=300)
	response 	= make_response('Bad URL hash', 404)
	response.headers['Expires'] 		= expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
	response.headers['Cache-Control'] 	= 'max-age='+str(300)
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
	response 	= make_response(send_file('templates/favicon.png'))
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

	
	