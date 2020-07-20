import os
import argparse
import flask
import pyqrcode
import socket
import webbrowser
import filetype
from threading import Thread
from time import sleep
import traceback


class AnyShare(flask.Flask):
	def __init__(self, share_type):
		flask.Flask.__init__(self, "AnyShare")
		self.share_type = share_type
		self.file = None
		self.was_downloaded = False
		self.was_uploaded = False
		self.file_dir = "any_drop_files"
		self.stop_all_services = False
		self.port = 5000

	def run(self):
		self.register_services()
		self.open_start_page()

		while True:
			try:
				flask.Flask.run(
					self,
					host="0.0.0.0",
					port=self.port,
					debug=False,
					use_reloader=False
				)
			except:
				traceback.print_exc()
				self.port += 1

	def register_services(self):
		@self.route("/upload/", methods=["POST"])
		def upload_file():
			f = flask.request.files['file']

			if not os.path.isdir(self.file_dir):
				os.mkdir(self.file_dir)

			f.save(os.path.join(self.file_dir, f.filename))
			self.was_uploaded = True
			self.file = f.filename

			if self.stop_all_services:
				return "Any Drop Complete, re-start to send again"

			if self.share_type == "send":
				return flask.redirect(flask.url_for("share"))
			elif self.share_type == "receive":
				return "File sent!"

	def open_start_page(self):
		if self.share_type == "send":
			webbrowser.open_new_tab(f"http://localhost:{self.port}/start/")
		elif self.share_type == "receive":
			Thread(target=self.check_upload_status).start()
			webbrowser.open_new_tab(f"http://localhost:{self.port}/share/")
		else:
			print(f"Invalid share_type: {self.share_type}")
			exit()

		@self.route("/share/", methods=["GET"])
		def share():
			print(f"Generating QR code for share_type: {self.share_type}")

			ip_address = self.get_local_ip()

			qr_path = os.path.join(self.file_dir, "qr.svg")

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
		def main():
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
				os._exit(1)
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
				os._exit(1)
			print("No upload detected")
			sleep(1)


arg_handler = argparse.ArgumentParser()
arg_handler.add_argument(
	"share_type",
	help="The share type for this run of Any Drop: "
		 "use 'send' to share files from you to others"
		 " or 'receive' to get have files shared to you",
	choices=["send", "receive"],
	default="send",
	nargs='?'
)

type = arg_handler.parse_args().share_type

AnyShare(share_type=type).run()
