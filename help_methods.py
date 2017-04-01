import ilearn_scrape
import iblack_scrape
import requests
import json
from datetime import datetime, timedelta
from Crypto.Cipher import AES  # pip pycrypto
import base64
import credentials
import math

AES_key = credentials.Credentials().key


def add_padding(text):
    """Adds padding from AES encryption. Used in decrypt()"""
    return text + (16 - len(text) % 16) * chr(16 - len(text) % 16)


def encrypt(data):
    """Encrypts with AES-256-CBC"""
    iv = 16 * '\x00'  # init vector
    obj = AES.new(AES_key, AES.MODE_CBC, iv)
    data = base64.b64encode(obj.encrypt(add_padding(data)))
    return data


def remove_padding(text):
    """Removers padding from AES encryption. Used in decrypt()"""
    return text[0:-ord(text[-1])]


def decrypt(encoded):
    """Decrypts with AES-256-CBC"""
    iv = 16 * '\x00'  # init vector
    obj = AES.new(AES_key, AES.MODE_CBC, iv)
    data = obj.decrypt(base64.b64decode(encoded))
    return remove_padding(str(data.decode()))


def add_default_reminders(user_id, assignments, db):
    """Adds all deadlines to db, if the do not already exist there"""
    for assignment in assignments:
        if db.user_subscribed_to_course(user_id, assignment[0]):
            db.add_reminder(assignment[1], assignment[2], 1, user_id)


def search_reminders(db):  # pragma: no cover
    """Returns all reminders for the next hours, in format [datetime.datetime, user_id, message, course_made]"""
    listing = db.get_all_reminders()
    min_ago = datetime.now() - timedelta(minutes=3)
    min_til = datetime.now() + timedelta(minutes=3)
    current = []
    app = current.append
    for line in listing:
        if min_ago < line[0] < min_til:
            app(line)
            db.delete_reminder(line[4])
    return current


def get_course_exam_date(course_code):
    """Returns the exam date of the given course. Sorted and split with ', '"""
    try:
        info = requests.get('http://www.ime.ntnu.no/api/course/' + course_code).json()
    except json.decoder.JSONDecodeError:  # course does not exist in ime api
        return "Was unable to retrieve exam date for " + course_code
    now = datetime.now()
    if 1 < now.month < 7:  # pragma: no cover
        start = datetime(now.year, 1, 1)
        end = datetime(now.year, 6, 30)
    else:  # pragma: no cover
        start = datetime(now.year, 7, 1)
        end = datetime(now.year, 12, 31)
    exam_dates = set()
    try:
        for i in range(len(info["course"]["assessment"])):
            if "date" in info["course"]["assessment"][i]:
                exam_date = datetime.strptime(info["course"]["assessment"][i]["date"], "%Y-%m-%d")
                if start < exam_date < end:
                    exam_dates.add(exam_date.strftime("%Y-%m-%d"))
    except KeyError:  # Catch if date does not exist, or assessment does not exist
        pass
    return ", ".join(sorted(exam_dates))


def get_user_info(access_token, user_id):
    """Get user info from profile, returns [firstname, lastname, picture]"""
    user_details_url = "https://graph.facebook.com/v2.8/" + str(user_id)
    user_details_params = {'fields': 'first_name,last_name,profile_pic', 'access_token': access_token}
    user_details = requests.get(user_details_url, user_details_params).json()
    print(user_details)
    lastname = user_details['last_name']
    firstname = user_details['first_name']
    picture = user_details['profile_pic']
    return firstname, lastname, picture


supported_commands = ('help get deadline', 'set reminder', 'help unsubscribe', 'help delete reminder', 'set classes',
                      'set class', 'course', 'help deadline', 'delete me', 'deadline', 'developer requests',
                      'help get exam', 'get exams', 'get', 'set', 'get deadlines', 'help get exams', 'get reminder',
                      'get link', 'help get', 'help get default', 'help set reminder', 'links', 'get reminders',
                      'unsubscribe', 'developer announcement', 'hint', 'get exam', 'profile', 'delete reminders',
                      'subscribed', 'help delete me', 'developer users', 'help bug', 'get links', 'login',
                      'get classes', 'help help', 'get class', 'help get reminder', 'delete', 'get default-time',
                      'help delete reminders', 'delete reminder', 'set reminders', 'set default-time',
                      'help get reminders', 'help get link', 'deadlines', 'help reminders', 'get subscribe',
                      'help request', 'bug', 'help', 'help set', 'subscribe', 'exams', 'developer id',
                      'developer request', 'get subscribed', 'help get default-time', 'help get subscribe',
                      'help reminder', 'help set default-time', 'developer bug', 'help deadlines', 'developer user',
                      'developer bugs', 'get courses', 'link', 'help delete', 'set default', 'get profile',
                      'get default', 'request', 'get deadline', 'help subscribe', 'classes', 'exam', 'help login',
                      'help set reminders', 'help set default', 'set course', 'help get subscribed', 'courses',
                      'get course', 'help get deadlines', 'set courses', 'help get links', "subscribe announcement",
                      "subscribe announcements","unsubscribe announcement", "unsubscribe announcements")


def get_most_similar_command(user_input):
    """Uses edit distance to calculate which command user most likely was trying to type in case of typo. 
    Needs a test."""
    min_change = math.inf
    most_similar_cmd = ""
    for cmd in supported_commands:
        distance = edit_distance(cmd, user_input)
        if distance < min_change:
            min_change = distance
            most_similar_cmd = cmd
        elif distance == min_change:
            if user_input[0] in ("q", "w", "e", "a", "s", "d", "z",) and cmd[0] == "s":
                min_change = distance
                most_similar_cmd = cmd
            elif user_input[0] in ("r", "t", "y", "f", "g", "h", "c", "v", "b") and cmd[0] == "g":
                min_change = distance
                most_similar_cmd = cmd
    return most_similar_cmd


def edit_distance(s1, s2):
    """Calculates minimum amount of change necessary to change one string into another, using the 
    Levenshtein algorithm. Made by Stackoverflow user Santosh."""
    m = len(s1) + 1
    n = len(s2) + 1
    tbl = {}
    for i in range(m):
        tbl[i, 0] = i
    for j in range(n):
        tbl[0, j] = j
    for i in range(1, m):
        for j in range(1, n):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            tbl[i, j] = min(tbl[i, j - 1] + 1, tbl[i - 1, j] + 1, tbl[i - 1, j - 1] + cost)
    return tbl[i, j]


def IL_scrape(user_id, course, until, db):
    """Scrapes It'slearing, and updates database. Returns a formatted reply message with deadlines"""
    try:
        course = course.upper()
        result = db.get_credential(user_id)
        info = ilearn_scrape.scrape(result[1], decrypt(result[2]))
        msg = ""
        max_day = int(until.split("/")[0])
        max_month = int(until.split("/")[1])
        current = datetime.now()
        # Max time it should get deadlines to
        reminders_to_set = []
        defaulttime = db.get_defaulttime(user_id)
        if course == "ALL":
            for line in info:  # pragma: no cover
                due_day = int(line[3].split(".")[0])
                due_month = int(line[3].split(".")[1])
                due_year = int(line[3].split(".")[2])
                if max_month > due_month or (
                                max_month == due_month and max_day >= due_day):  # Before max deadlines, may need fix in limit zones
                    day, month, year = line[3].split(".")
                    if current < datetime(due_year, due_month, due_day) - timedelta(days=defaulttime):
                        reminders_to_set.append(
                            (line[1], line[0] + " in " + line[1], "{}-{}-{}".format(year, month, day) + " 12:00:00"))
                    msg += line[0] + "\nin " + line[1] + " " + line[2] + "\nDue date: " + line[3] + " " + line[
                        4] + "\n\n"  # Format to default ###NOTE### does support time as line[4]
            db.delete_all_coursemade_reminders(user_id)  # Clears database of old reminders from classes
            add_default_reminders(user_id, reminders_to_set, db)
        else:
            for line in info:  # pragma: no cover
                due_day = int(line[3].split(".")[0])
                due_month = int(line[3].split(".")[1])
                if line[1] == course and (max_month > due_month or (
                                max_month == due_month and max_day >= due_day)):  # Before  max deadlines and correct course
                    msg += line[0] + "\nin " + line[1] + " " + line[2] + "\nDue date: " + line[3] + " " + line[
                        4] + "\n\n"  # Format to default ###NOTE### does support time as line[4]
    except IndexError:
        msg = "SQLerror"
    return msg


def BB_scrape(user_id, course, until, db):
    """Scrapes Blackboard, and updates database. Returns a formatted reply message with deadlines"""
    try:
        course = course.upper()
        result = db.get_credential(user_id)
        info = iblack_scrape.scrape(result[1], decrypt(result[2]))
        msg = ""
        max_day = int(until.split("/")[0])
        max_month = int(until.split("/")[1])
        current = datetime.now()
        default_time = db.get_defaulttime(user_id)
        # Max time it should get deadlines to
        reminders_to_set = []
        if course == "ALL":
            for line in info:  # pragma: no cover
                due_day = int(line[3].split(".")[0])
                due_month = int(line[3].split(".")[1])
                due_year = int("20" + line[3].split(".")[2])
                if max_month > due_month or (max_month == due_month and max_day >= due_day):  # Before max deadlines
                    day, month, year = line[3].split(".")
                    if current < datetime(due_year, due_month, due_day) - timedelta(days=default_time):
                        reminders_to_set.append(
                            (line[1], line[0] + " in " + line[1], "20{}-{}-{}".format(year, month, day) + " 12:00:00"))
                    msg += line[0] + "\nin " + line[1] + " " + line[2] + "\nDue date: " + line[
                        3] + "\n\n"  # Format to default ###NOTE### do NOT support time as line[4]
            add_default_reminders(user_id, reminders_to_set, db)
        else:
            for line in info:  # pragma: no cover
                due_day = int(line[3].split(".")[0])
                due_month = int(line[3].split(".")[1])
                if line[1] == course and (max_month > due_month or (
                                max_month == due_month and max_day >= due_day)):  # Before max deadlines and correct course
                    msg += line[0] + "\nin " + line[1] + " " + line[2] + "\nDue date: " + line[
                        3] + "\n\n"  # Format to default ###NOTE### do NOT support time as line[4]
    except IndexError:
        msg = "SQLerror"
    return msg
