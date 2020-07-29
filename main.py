import os
import flask
from flask_cors import CORS
import pyqrcode
import socket
import webbrowser
import filetype
from threading import Thread
from time import sleep


class AnyShare(flask.Flask):
	def __init__(self):
		flask.Flask.__init__(self, "AnyShare")
		self.share_type = None
		self.file = None
		self.was_downloaded = False
		self.was_uploaded = False
		self.file_dir = os.path.join(os.path.expanduser("~"), "any_share_files")
		self.stop_all_services = True
		self.port = 5000
		self.is_reset = False
		self.start_success = False
		self.cancel_receive_upload = False
		self.cancel_download = False
		self.ip_address = self.get_local_ip()

		if not os.path.isdir(self.file_dir):
			os.mkdir(self.file_dir)

	def reset(self):
		self.is_reset = True
		self.share_type = None
		self.file = None
		self.was_downloaded = False
		self.was_uploaded = False
		self.stop_all_services = True
		self.open_start_page()

	def run(self):
		self.register_services()
		Thread(target=self.open_start_page).start()

		while True:
			try:
				self.start_success = True
				flask.Flask.run(
					self,
					host="0.0.0.0",
					port=self.port,
					debug=False,
					use_reloader=False
				)
			except:
				print(f"Port {self.port} unavailable - trying the next port")
				self.start_success = False
				self.port += 1

	def register_services(self):
		@self.route("/", methods=["GET"])
		def main_page():
			if "share_type" in flask.request.args:
				self.share_type = flask.request.args.get('share_type')

				if self.share_type == "send":
					self.stop_all_services = False
					return flask.redirect(flask.url_for("start"))
				elif self.share_type == "receive":
					self.stop_all_services = False
					Thread(target=self.check_upload_status).start()
					return flask.redirect(flask.url_for("share"))
				elif self.share_type == "exit":
					self.stop_all_services = True
					Thread(target=self.exit_delay).start()
					return f"""
					<h2>Thanks For Using AnyShare!</h2>
					<h3>Shutting down..</h3>
					{self.inject_close_check_javascript()}
					"""

			else:
				header = "Welcome to AnyShare!"
				if self.is_reset:
					header = "AnyShare Again!"
				return f"""
					<html>
					<head>
						<script>
							function openAndClose(urlToOpen){{
								window.open(urlToOpen);
								window.close();
							}}
						</script>
					</head>
					<body>
					<h2>{header}</h2>
					<h3>Selected a share type to get started</h3>
					<button onclick="openAndClose('http://{self.ip_address}:{self.port}/?share_type=send')">Send</button>
					<button onclick="openAndClose('http://{self.ip_address}:{self.port}/?share_type=receive')">Receive</button>
					<button onclick="openAndClose('http://{self.ip_address}:{self.port}/?share_type=exit')">Exit</button>
					</body>
					</html>
				"""

		@self.route("/upload/", methods=["POST"])
		def upload_file():
			f = flask.request.files['file']

			if not f:
				return flask.redirect(flask.url_for("start"))

			f.save(os.path.join(self.file_dir, f.filename))
			self.was_uploaded = True
			self.file = f.filename

			if self.stop_all_services:
				return "Any Share Complete, re-start to send again"

			if self.share_type == "send":
				return flask.redirect(flask.url_for("share"))
			elif self.share_type == "receive":
				return "<h2>File sent!</h2>" + self.inject_close_check_javascript()

		@self.route("/share/", methods=["GET"])
		def share():
			if self.share_type == "send":
				url = f"http://{self.ip_address}:{self.port}/download/"
			elif self.share_type == "receive":
				url = f"http://{self.ip_address}:{self.port}/start/"
			else:
				return "<h2>I don't think you're supposed to do that..</h2>"

			html_cancel_mod = f"""
						<head>
							<script>
								function cancelAndClose(){{
									alert("After proceeding, please wait up to 3 seconds for cancellation to complete"); 
									window.open("http://{self.ip_address}:{self.port}/upload_cancel/?share_type={self.share_type}");
									window.close();
								}}
							</script>
						</head>
						<button onclick="cancelAndClose()">Cancel</button>"""

			html = f"""
			{html_cancel_mod}
			<img src="http://{self.ip_address}:{self.port}/share/QR/" alt="qr code">
			<h2>{url}</h2>
			{self.inject_close_check_javascript()}
			"""
			return html

		@self.route("/share/QR/", methods=["GET"])
		def share_qr():
			print(f"Generating QR code for share_type: {self.share_type}")

			qr_path = os.path.join(self.file_dir, f"qr_{self.port}.svg")

			if self.share_type == "send":
				url = pyqrcode.create(f"http://{self.ip_address}:{self.port}/download/")
				url.svg(qr_path, scale=15)
				Thread(target=self.check_download_status).start()
			elif self.share_type == "receive":
				url = pyqrcode.create(f"http://{self.ip_address}:{self.port}/start/")
				url.svg(qr_path, scale=15)

			if self.stop_all_services:
				return "Any Share Complete, re-start to send again"

			return flask.send_file(qr_path, cache_timeout=1)

		@self.route("/start/")
		def start():
			if self.stop_all_services:
				return "Any Share Complete, re-start to send again"

			share_type_mod = ""

			if self.share_type == "send":
				share_type_mod = f"""<button onclick="openAndClose('http://{self.ip_address}:{self.port}/')">Back</button>"""

			return f"""
				<html>
				<head>
					<script>
						function openAndClose(urlToOpen){{
							window.open(urlToOpen);
							window.close();
						}}
					</script>
				</head>
				<body>
				{share_type_mod}
				<form action = "http://{self.ip_address}:{self.port}/upload/" method = "POST"
				enctype = "multipart/form-data">
				<input type = "file" name = "file" />
				<input type = "submit"/>
				</form>
				</body>
				</html>
			"""

		@self.route("/download/", methods=["GET"])
		def download():
			if self.stop_all_services:
				return "Any Share Complete, re-start to send again"

			return f"""
			<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js"></script>
			<script>
				function download_file() {{
					$.ajax({{url: 'http://{self.ip_address}:{self.port}/download/file/', 
						xhrFields: {{
							responseType: 'blob'
						}},
						success: function (data) {{
							var a = document.createElement('a');
							var url = window.URL.createObjectURL(data);
							a.href = url;
							a.download = '{self.file}';
							document.body.append(a);
							a.click();
							a.remove();
							window.URL.revokeObjectURL(url);
							document.getElementById("main_text").innerHTML = "Download Complete";
							setTimeout(window.close, 6000);
						}},
						error: function() {{
							location.replace("http://{self.ip_address}:{self.port}/download/file/");
							document.getElementById("main_text").innerHTML = "Download Complete";
							alert("Hmm.. for some reason AnyShare is not able to close this window. You may need to close it manually.");
							setTimeout(window.close, 3000);
						}}
					}})
				}}
			</script>
			<body onload="setTimeout(download_file, 1000)">
			<h2 id="main_text">File download starting</h2>
			"""

		@self.route("/download/file/", methods=["GET"])
		def download_file():
			if self.file:
				self.was_downloaded = True
				self.stop_all_services = True
				print("Setting download status to True")
				file_path = os.path.join(self.file_dir, self.file)
				return flask.send_file(file_path, as_attachment=True, cache_timeout=1)
			else:
				return "Waiting for file upload"

		@self.route("/close_check/", methods=["GET"])
		def close_check():
			return str(self.stop_all_services)

		@self.route("/upload_cancel/", methods=["GET"])
		def upload_cancel():
			share_type = flask.request.args.get('share_type')

			if share_type == "receive":
				self.cancel_receive_upload = True
				sleep(3)
				self.reset()
			elif share_type == "send":
				self.cancel_download = True
				sleep(3)
				self.reset()

			return """
			<body onload="setTimeout(window.close(), 3000)"></body>
			<h2>Resetting...</h2>
			"""

	def inject_close_check_javascript(self): # todo
		return f"""
		<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js"></script>
		<script>
			function close_check() {{
				$.ajax({{url: 'http://{self.ip_address}:{self.port}/close_check/', 
					success: function(result){{
						if(result === "True"){{
							window.open('','_parent',''); 
    						window.close();
						}}
						setTimeout(close_check, 3000);
					}},
					error: function() {{
						window.open('','_parent',''); 
    					window.close();
					}}
				}})
			}}
		</script>
		<body onload="setTimeout(close_check, 3000)">
		"""

	def open_start_page(self):
		check_ct = 0
		while check_ct < 2:
			if self.start_success:
				check_ct += 1
			else:
				check_ct = 0
		sleep(1)

		webbrowser.open_new_tab(f"http://localhost:{self.port}/")
		return

	def get_local_ip(self):
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		try:
			s.connect(('google.com', 80))
			ip = s.getsockname()[0]
			s.close()
		except:
			ip = 'N/A'
		return ip

	def check_download_status(self):
		while True:
			if self.was_downloaded:
				print("download detected")
				sleep(5)
				print("cleaning up!")
				for f in os.listdir(self.file_dir):
					os.remove(os.path.join(self.file_dir, f))
				print("Any Share Complete!")
				self.reset()
				return
			if self.cancel_download:
				print("Cancelling Download")
				self.cancel_download = False
				return

			print("No download detected")
			sleep(1)

	def check_upload_status(self):
		while True:
			if self.was_uploaded:
				print("Starting download detection")
				Thread(target=self.check_download_status).start()
				sleep(.2)
				print("Upload detected - opening download page")
				webbrowser.open_new_tab(f"http://localhost:{self.port}/download/")
				return
			if self.cancel_receive_upload:
				print("Cancelling Upload")
				self.cancel_receive_upload = False
				return

			print("No upload detected")
			sleep(1)

	def exit_delay(self):
		sleep(5)
		os._exit(1)


any_share_app = AnyShare()
cors = CORS(any_share_app)
any_share_app.run()
