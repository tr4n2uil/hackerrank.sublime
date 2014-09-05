import sublime, sublime_plugin
import urllib, urllib2, threading
import json, time, random, hashlib
import sys, os, re
import Cookie


# in memory cookie storage
cookie = False


# HR Sublime Plugin Class
class HackerRankCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		global cookie

		settings = sublime.load_settings("HackerRank.sublime-settings")
		string = self.view.substr(sublime.Region(0, self.view.size()))

		sublime.active_window().run_command("show_panel", {"panel": "console", "toggle": True})

		# start HR API thread
		thread = HackerRankApiCall(settings.get("username"), settings.get("password"), string, self.view.file_name())
		thread.start()



# HR Api Call Manager Thread
class HackerRankApiCall(threading.Thread):
	def __init__(self, username, password, string, problem):
		self.username = username
		self.password = password
		self.original = string
		self.problem = problem

		self.result = None
		threading.Thread.__init__(self)


	# log status messages
	def append(self, string):
		print string


	# thread runner
	def run(self):
		self.append("\n\n\n\n")
		if not cookie:
			self.append("\nConnecting to HackerRank servers ...")
			
			csrf = get_csrf('https://www.hackerrank.com/login', None)
			print "Logging in to HackerRank servers ..."
			if login(self.username, self.password, csrf):
				self.api()

		else:
			self.api()


	# thread api invoker
	def api(self):
		try:
			global cookie
			self.append("\nFetching Problem ...")

			problem = os.path.basename(self.problem).split('.')[0]
			self.append(problem)

			# get csrf for problem
			csrf = get_csrf('https://www.hackerrank.com/challenges/' + problem, cookie)

			# submit code
			self.append("\nSubmitting Code ...")
			data = {'code': self.original, 'language':'c', 'customtestcase':False}
			request = urllib2.Request('https://www.hackerrank.com/rest/contests/master/challenges/'+problem+'/compile_tests')
			request.add_header('Content-Type', 'application/json')
			request.add_header('Cookie', cookie)
			request.add_header('X-CSRF-Token', csrf)

			http_file = urllib2.urlopen(request, json.dumps(data))
			self.result = http_file.read()

			# print self.result
			self.result = json.loads(self.result)
			status = self.result['status']
			model = self.result['model']

			self.append("Fetching Results: " + str(model['id']) + "\n")

			# check compilation status
			compiled = 0
			while not compiled:
				request = urllib2.Request('https://www.hackerrank.com/rest/contests/master/challenges/'+problem+'/compile_tests/' + str(model['id']) + "?_="+str(time.time()*1000))
				request.add_header('Cookie', cookie)				

				http_file = urllib2.urlopen(request)
				self.result = http_file.read()

				self.result = json.loads(self.result)
				# print self.result
				status = self.result['status']
				model = self.result['model']

				time.sleep(1)
				compiled = model['status']
				self.append(model['status_string'])
				if 'compilemessage' in model and model['compilemessage']:
					self.append(model['compilemessage'])
				if 'time' in model and model['time'] and 'testcase_message' in model and model['testcase_message']:
					self.append("\nTest Case Execution Times:")
					for i in range(0, len(model['time'])):
						self.append('#' + str(i+1) + ": " + str(model['time'][i]) + " (" + model['testcase_message'][i] +")" )

			return

		# handle exceptions
		except (urllib2.HTTPError) as (e):
			err = '%s: HTTP error %s contacting API' % (__name__, str(e.code))
			cookie = False
		except (urllib2.URLError) as (e):
			err = '%s: URL error %s contacting API' % (__name__, str(e.reason))
			cookie = False

		print err
		sublime.error_message(err)
		self.result = False



# HR auth login helper
def login(username, password, csrf):
	global cookie

	data = urllib.urlencode({'login': username, 'password':password, 'remember_me': False, 'contest_crp': "", 'fallback': True })
	request = urllib2.Request('https://www.hackerrank.com/auth/login')
	request.add_header('X-CSRF-Token', csrf)

	http_file = urllib2.urlopen(request, data, timeout=5)
	result = json.loads(http_file.read())

	# read cookie data
	if result['status']:	
		headers = http_file.info()
		ck = Cookie.SimpleCookie(headers['Set-Cookie'])
		cookie = "_hackerrank_session=" + ck['_hackerrank_session'].value + ";"

		print "You are successfully connected to HackerRank servers: "
		return 1
	else:
		print "Error connecting to HackerRank servers"
		return 0



# HR URL obtain CSRF helper
def get_csrf(url, cookie):
	request = urllib2.Request(url)
	#request.add_header('User-Agent', 'Sublime HackerRank')
	if cookie:
		request.add_header('Cookie', cookie)

	http_file = urllib2.urlopen(request, timeout=5)
	result = http_file.read()

	# regex csrf token
	match = re.match(r'[\w\W]*?<meta content="([^\"]+?)" name="csrf-token"[\w\W]*?', result)
	if match:
		return match.group(1)
	else:
		return None



