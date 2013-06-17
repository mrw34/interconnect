import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))

import json
from ttp import ttp
import urllib
import urllib2
from datetime import datetime
import time
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import db
import random
import cgi
import uuid

class UserPrefs(db.Model):
  id = db.StringProperty()
  following = db.StringListProperty()

class Config(db.Model):
  id = db.StringProperty(default=uuid.uuid4().urn, required=True)
  access_token = db.StringProperty(default=os.environ['ACCESS_TOKEN'], required=True)

def get_created_at(tweet):
  return datetime.strptime(tweet['created_at'], '%a %b %d %H:%M:%S +0000 %Y')

feed_header="""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Twitter</title>
  <updated>%sZ</updated>
  <author>
    <name>Interconnected</name>
  </author>
  <id>%s</id>"""
feed_footer="</feed>"

entry="""  <entry>
    <title>%s (%s)</title>
    <link href="https://twitter.com/%s/status/%s"/>
    <id>tag:twitter.com,%s:%s</id>
    <updated>%sZ</updated>
    <content type="html"><![CDATA[%s]]></content>
  </entry>"""

config = Config.all().get()
if not config:
  config = Config()
  config.put()

headers = {'Authorization': 'Bearer ' + config.access_token}

p = ttp.Parser()

if os.environ['PATH_INFO'].endswith('.atom'):
  all_tweets = []
  for screen_name in UserPrefs.all().get().following:
    tweets = memcache.get(screen_name)
    if tweets is None:    
      data = {'screen_name': screen_name}
      url = 'https://api.twitter.com/1.1/statuses/user_timeline.json?%s' % urllib.urlencode(data)
      req = urllib2.Request(url, headers=headers)
      tweets = json.load(urllib2.urlopen(req))
      memcache.add(screen_name, tweets, 60 * (30 + random.randint(0, 29)))
    all_tweets.extend(tweets)
  all_tweets = sorted(all_tweets, key=get_created_at, reverse=True)

  print 'Content-Type: application/atom+xml'
  print
  print feed_header % (get_created_at(all_tweets[0]).isoformat(), config.id)
  for tweet in sorted(all_tweets, key=get_created_at, reverse=True):
    print entry % (tweet['user']['name'], tweet['user']['screen_name'], tweet['user']['screen_name'], tweet['id_str'], get_created_at(tweet).date().isoformat(), tweet['id_str'], get_created_at(tweet).isoformat(), tweet['text'].encode('ascii', 'replace'))
  print feed_footer
else:
  user = users.get_current_user()
  userprefs = db.Query(UserPrefs).filter('id =', user.user_id()).get()
  if not userprefs:
    userprefs = UserPrefs(id=user.user_id())

  if os.environ['REQUEST_METHOD'] == 'POST':
    fields = cgi.FieldStorage()
    screen_name = unicode(fields['screen_name'].value)
    if 'append' == fields['action'].value:
      if not screen_name in userprefs.following:
        userprefs.following.append(screen_name)
    else:
      userprefs.following.remove(screen_name)
    userprefs.put()

  print 'Content-Type: text/html'
  print
  print '<!DOCTYPE html>'
  print '<title>Interconnected</title>'
  print '<ul>'
  print '<li><form method="post"><input type="hidden" name="action" value="append"><input name="screen_name"></form>'
  for screen_name in sorted(userprefs.following, key=unicode.lower):
    print '<li>%s <form method="post" style="display: inline"><input type="hidden" name="screen_name" value="%s"><button name="action" type="submit" value="remove">Remove</button></form>' % (screen_name, screen_name)
  print '</ul>'
