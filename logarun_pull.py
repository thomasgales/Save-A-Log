# -*- coding: utf-8 -*-

# Logarun Data Extraction script
import argparse
import csv
from datetime import datetime, timedelta

from getpass import getpass
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

import re
import sys

from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
try:
    # For Python 3.0 and later
    from urllib.request import urlopen
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen


def main():
	parser = argparse.ArgumentParser(description="Query logarun.com for information about a user's training history.")
	parser.add_argument('username', help='Username to query')
	parser.add_argument('-d', '--daysBack', help='Number of days to go back, from today', default=1, type=int)
	args=parser.parse_args()

	# Import username from command line
	if args.username == "" or args.username is None:
		print("Terminating. You need to supply a username.")
		sys.exit()
	print("username = " + args.username)
	print('days back =', args.daysBack)
	current_day = datetime.today()

	password = getpass("Password (if account is public, leave blank):")


	# BUILD URL
	# A Logarun URl looks like:
	# http://www.logarun.com/calendars/<username>/<year>/<month>/<day>
	# For example: http://www.logarun.com/calendars/edbrodeur/2017/06/18
	base_URL = "http://www.logarun.com/calendars/"

	# args.daysBack = 50
	index = pd.date_range(current_day - timedelta(days=args.daysBack), periods=args.daysBack, freq='D')
	
	headers = ["Date", "Log Title", "Log Note", "Activity", "Activity Distance", "Activity Type", "Activity Time", "Activity Pace", "Comments"]
	df = pd.DataFrame(columns=headers)

	driver = None
	if password != '':
		driver = attempt_login(args.username, password)
		if not logged_in(driver):
			print("Login failed. Are you sure your username and password are correct?")
			driver.quit()
			return

	while args.daysBack >= 0:

		url_query = base_URL + args.username + date_format(current_day)
		print("We will query: " + url_query)

		soup = None
		# Paging logarun.com... this is what takes awhile
		if (password != ''):
			driver.get(url_query)
			soup = BeautifulSoup(driver.page_source, 'html.parser')
		else:
			try:
				page = urlopen(url_query)
				soup = BeautifulSoup(page, 'html.parser')
			except URLError:
				print('error was ' + URLError)
		
		try:
			df.append(get_activity(str("Bike"), soup, current_day))
		except TypeError:
			pass
			# print("bike didn't happen that day")

		try:
			df = df.append(get_activity(str("Run"), soup, current_day))
		except TypeError:
			pass
			#print("run didn't happen that day")

		try:
			df.append(get_activity(str("Swim"), soup, current_day))
		except TypeError:
			#print("swim didn't happen that day")
			pass

		try:
			df.append(get_activity(str("Elliptical"), soup, current_day))
		except TypeError:
			pass
			#print("elliptical didn't happen that day")
		
		# df.append(grab_comments(soup, current_day))
		df = pd.concat([df, grab_comments(soup, current_day)], axis = 0, ignore_index = True)

		args.daysBack -= 1
		current_day = subtract_day(current_day)

	if password != '':
		driver.quit()
	df.to_csv("myLog.csv", index = False)
	print('Output log to myLog.csv.')


"""Utility Functions"""
def date_format(date):
	"""Converts a Date Object to Logarun URL Format"""

	# retURL = "/%s/%s/%s" % (date.year, date.month, date.day) # not clean
	return date.strftime("/%Y/%m/%d")  # much cleaner


def subtract_day(date):
	"""Converts a Date Object to Logarun URL Format"""

	retDate = date - timedelta(days=1)
	return retDate

def grab_comments(soup, date):
	comments = soup.find('div', attrs={'class': 'app comments'})
	list_of_comments = []
	dates = []
	for line in comments.findAll('li'):
		# When user is logged in, logarun includes a <li> tag with class='add' for the "add comment" button.
		# For actual comments, logarun does not include a class attribute for the <li> tag.
		addComment = line.get('class')
		if (addComment is not None and line.get('class')[0] == 'add'):
			continue
		author = line.find('a').text
		comment = line.find_all('p')[-1].text
		full_comment = author + ': ' + comment
		list_of_comments.append(full_comment)
		dates.append(date_format(date))

	df = pd.DataFrame({
		'Date': dates,
		'Comments': list_of_comments
		})
	return df

def get_activity(activity_string, soup, date):
	"""pull an activity from a day.	
	activity_string: "Run", "Bike", "Elliptical", etc.
	"""
	if not isinstance(activity_string, str):
		print("error! Didn't pass a string to get_activity")
		print('you passed:')
		print(type(activity_string))
		sys.exit()

	log_title = soup.find('tr', attrs={'class': 'editTblDayTitle'}).get_text()
	log_note = soup.find('p', attrs={'id': 'ctl00_Content_c_note_c_note'}).get_text()
	
	regExString = "app %s.*" % activity_string
	activity_boxes = soup.findAll(attrs={'class': re.compile(regExString)})
	if activity_boxes:
		activity_distances = []
		activity_types = []
		activity_paces = []
		activity_times = []
		raw_HTML_activity_distances = []
		raw_HTML_activity_types = []
		raw_HTML_activity_paces = []
		raw_HTML_activity_times = []
		index_date = []
		for item in activity_boxes:  # for each bike that day
			raw_HTML_activity_types += (item.findAll(attrs={'id': re.compile("ctl01_c_value")}))
			raw_HTML_activity_distances += (item.findAll(attrs={'id': re.compile("ctl00_c_value")}))
			raw_HTML_activity_times += (item.findAll(attrs={'id': re.compile("ctl02_c_value")}))
			raw_HTML_activity_paces += (item.findAll(attrs={'id': re.compile("ctl03_c_value")}))
		# Seems like a dumb way to grab this all but
		for span in raw_HTML_activity_distances:
			activity_distances.append(float(span.text))
		for i in raw_HTML_activity_types:
			# cleanedText = i.text.replace("(s)", "s")
			activity_types.append(i.text.replace("(s)", "s"))
		for i in raw_HTML_activity_times:
			activity_times.append(i.text) 
		for i in raw_HTML_activity_paces:
			activity_paces.append(i.text)
		index_date.append(date)
		#TODO: MOVE UP
		df = pd.DataFrame({
			'Date' : date_format(date),
			'Log Title' : log_title,
			'Log Note' : log_note,
			'Activity': activity_string,
			'Activity Distance' : activity_distances,
			'Activity Type' : activity_types,
			'Activity Time' : activity_times,
			'Activity Pace' : activity_paces}) 
		return df

	else:
		return 0


def logged_in(driver):
	"""
	Checks if a user is logged in.

	:param driver: webdriver. Function will test if driver is logged into logarun.
	:returns: True if logged in, false otherwise.
	"""
	driver.get("http://www.logarun.com")
	soup = BeautifulSoup(driver.page_source, 'html.parser')
	searchBar = soup.find('div', attrs={'class': 'topRight'})
	for element in searchBar.findAll('a'):
		title = element.get('title')
		if (title is not None and title == 'Log into your account.'):
			return False
	return True


def attempt_login(username, password):
	"""
	-Credit to https://github.com/adzienis/Lazy_Runner for this function. For some odd
		reason, their python script goes from strava TO logarun...
	-For some reason webdriver is able to understand logarun's mangled HTML (missing closing tags)
		but Mechanize could not. 

	:returns: webdriver. May or may not be successfully logged into logarun.
	"""
	options = Options()
	options.headless = True
	driver = webdriver.Firefox(options=options)
	driver.get("http://www.logarun.com/logon.aspx")
	driver.find_element_by_id("LoginName").send_keys(username)
	driver.find_element_by_id("Password").send_keys(password)
	driver.find_element_by_id("LoginNow").click()
	return driver

	
if __name__ == "__main__":
	main()