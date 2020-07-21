import os
import flask
import pyqrcode
import socket
import webbrowser
import filetype
from threading import Thread
from time import sleep
import traceback


class AnyShare(flask.Flask):
	def __init__(self):
		flask.Flask.__init__(self, "AnyShare")
		self.share_type = None
		self.file = None
		self.was_downloaded = False
		self.was_uploaded = False
		self.file_dir = os.path.join(os.path.expanduser("~"), "any_share_files")
		self.stop_all_services = False
		self.port = 5000
		self.is_reset = False
		self.start_success = False

		if not os.path.isdir(self.file_dir):
			os.mkdir(self.file_dir)

	def reset(self):
		self.is_reset = True
		self.share_type = None
		self.file = None
		self.was_downloaded = False
		self.was_uploaded = False
		self.stop_all_services = False
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
		@self.route("/", methods=["POST", "GET"])
		def main_page():
			if flask.request.method == 'POST':
				self.share_type = flask.request.values.get('share_type')

				if self.share_type == "send":
					return flask.redirect(flask.url_for("start"))
				elif self.share_type == "receive":
					Thread(target=self.check_upload_status).start()
					return flask.redirect(flask.url_for("share"))
				elif self.share_type == "exit":
					self.stop_all_services = True
					Thread(target=self.exit_delay).start()
					return """
					<h2>Thanks For Using AnyShare!</h2>
					<h3>Shutting down..</h3>
					"""

			else:
				header = "Welcome to AnyShare!"
				if self.is_reset:
					header = "AnyShare Again!"
				return f"""
					<html>
					<body>
					<h2>{header}</h2>
					<h3>Selected a share type to get started</h3>
					<form action = "http://{self.get_local_ip()}:{self.port}/" method = "POST"
					enctype = "multipart/form-data">
					<input type = "hidden" name = "share_type" value="send" />
					<input type = "submit" value="Send"/>
					</form>
					<form action = "http://{self.get_local_ip()}:{self.port}/" method = "POST"
					enctype = "multipart/form-data">
					<input type = "hidden" name = "share_type" value="receive" />
					<input type = "submit" value="Receive"/>
					</form>
					<form action = "http://{self.get_local_ip()}:{self.port}/" method = "POST"
					enctype = "multipart/form-data">
					<input type = "hidden" name = "share_type" value="exit" />
					<input type = "submit" value="Exit"/>
					</form>
					</body>
					</html>
				"""

		@self.route("/upload/", methods=["POST"])
		def upload_file():
			f = flask.request.files['file']

			f.save(os.path.join(self.file_dir, f.filename))
			self.was_uploaded = True
			self.file = f.filename

			if self.stop_all_services:
				return "Any Drop Complete, re-start to send again"

			if self.share_type == "send":
				return flask.redirect(flask.url_for("share"))
			elif self.share_type == "receive":
				return "File sent!"

		@self.route("/share/", methods=["GET"])
		def share():
			print(f"Generating QR code for share_type: {self.share_type}")

			ip_address = self.get_local_ip()

			qr_path = os.path.join(self.file_dir, f"qr_{self.port}.svg")

			if self.share_type == "send":
				url = pyqrcode.create(f"http://{ip_address}:{self.port}/download/")
				url.svg(qr_path, scale=15)
				Thread(target=self.check_download_status).start()
			elif self.share_type == "receive":
				url = pyqrcode.create(f"http://{ip_address}:{self.port}/start/")
				url.svg(qr_path, scale=15)

			if self.stop_all_services:
				return "Any Drop Complete, re-start to send again"

			return flask.send_file(qr_path, cache_timeout=1)

		@self.route("/start/")
		def start():
			if self.stop_all_services:
				return "Any Drop Complete, re-start to send again"

			return f"""
				<html>
				<body>
				<form action = "http://{self.get_local_ip()}:{self.port}/upload/" method = "POST"
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
				return "Any Drop Complete, re-start to send again"

			if self.file:
				self.was_downloaded = True
				self.stop_all_services = True
				print("Setting download status to True")
				file_path = os.path.join(self.file_dir, self.file)
				return flask.send_file(file_path, as_attachment=filetype.is_video(file_path), cache_timeout=1)
			else:
				return "Waiting for file upload"

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
				sleep(15)
				print("cleaning up!")
				for f in os.listdir(self.file_dir):
					os.remove(os.path.join(self.file_dir, f))
				print("Any Drop Complete!")
				self.reset()
				return
			print("No download detected")
			sleep(1)

	def check_upload_status(self):
		while True:
			if self.was_uploaded:
				print("Upload detected - opening download page")
				webbrowser.open_new_tab(f"http://localhost:{self.port}/download/")
				sleep(3)
				self.stop_all_services = True
				sleep(15)
				print("cleaning up!")
				for f in os.listdir(self.file_dir):
					os.remove(os.path.join(self.file_dir, f))
				print("Any Drop Complete!")
				self.reset()
				return
			print("No upload detected")
			sleep(1)

	def exit_delay(self):
		sleep(5)
		os._exit(1)


AnyShare().run()
